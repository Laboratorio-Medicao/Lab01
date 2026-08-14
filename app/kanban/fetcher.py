import logging

from kanban.models import KanbanItem
from kanban.query import KANBAN_SNAPSHOT_QUERY, build_variables

logger = logging.getLogger(__name__)


def _extract_field_map(field_value_nodes):
    """Retorna {nome_do_campo: valor} ignorando nós sem campo associado."""
    result = {}
    for node in field_value_nodes:
        field = node.get("field")
        if not field:
            continue
        name = field.get("name", "")
        value = node.get("text") or node.get("name")
        if name and value:
            result[name] = value
    return result


def _parse_item(node):
    """Converte um nó da API em KanbanItem; retorna None para rascunhos sem issue."""
    content = node.get("content")
    if not content:
        return None

    field_map = _extract_field_map(node.get("fieldValues", {}).get("nodes", []))

    return KanbanItem(
        number=content.get("number"),
        title=content.get("title", ""),
        status=field_map.get("Status", ""),
        assignees=tuple(a["login"] for a in content.get("assignees", {}).get("nodes", [])),
        labels=tuple(lb["name"] for lb in content.get("labels", {}).get("nodes", [])),
    )


class KanbanFetcher:
    def __init__(self, client, org, project_number):
        self._client = client
        self._org = org
        self._project_number = project_number

    def fetch_all(self):
        items = []
        cursor = None

        while True:
            page, has_next, cursor = self._fetch_page(cursor)
            items.extend(page)
            logger.info("página coletada: %s itens (total=%s)", len(page), len(items))
            if not has_next:
                break

        return items

    def _fetch_page(self, after):
        data = self._client.execute(
            KANBAN_SNAPSHOT_QUERY,
            variables=build_variables(self._org, self._project_number, after),
        )

        items_data = data["organization"]["projectV2"]["items"]
        page_info = items_data["pageInfo"]

        parsed = []
        for node in items_data["nodes"]:
            item = _parse_item(node)
            if item is not None:
                parsed.append(item)

        return parsed, page_info["hasNextPage"], page_info.get("endCursor")

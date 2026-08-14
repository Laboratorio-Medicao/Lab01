import pytest

from kanban.fetcher import KanbanFetcher, _extract_field_map, _parse_item
from kanban.models import KanbanItem


def field_text(field_name, text):
    return {"text": text, "field": {"name": field_name}}


def field_select(field_name, option_name):
    return {"name": option_name, "field": {"name": field_name}}


def issue_node(number=42, title="Minha issue", status="Done", assignees=None, labels=None):
    return {
        "fieldValues": {
            "nodes": [
                {},
                field_text("Title", title),
                field_select("Status", status),
            ]
        },
        "content": {
            "number": number,
            "title": title,
            "assignees": {"nodes": [{"login": a} for a in (assignees or [])]},
            "labels": {"nodes": [{"name": lb} for lb in (labels or [])]},
        },
    }


def page_response(nodes, has_next=False, end_cursor=None):
    return {
        "organization": {
            "projectV2": {
                "items": {
                    "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                    "nodes": nodes,
                }
            }
        }
    }


class FakeClient:
    def __init__(self, responses):
        self._responses = iter(responses)

    def execute(self, query, variables=None):
        return next(self._responses)


# --- _extract_field_map ---

def test_extract_field_map_returns_text_and_select_values():
    nodes = [
        {},
        field_text("Title", "meu título"),
        field_select("Status", "In progress"),
    ]
    result = _extract_field_map(nodes)

    assert result == {"Title": "meu título", "Status": "In progress"}


def test_extract_field_map_ignores_empty_nodes():
    result = _extract_field_map([{}, {}, {}])

    assert result == {}


def test_extract_field_map_handles_empty_list():
    assert _extract_field_map([]) == {}


# --- _parse_item ---

def test_parse_item_maps_all_fields():
    node = issue_node(number=10, title="Foo", status="Done", assignees=["alice"], labels=["bug"])
    item = _parse_item(node)

    assert item == KanbanItem(
        number=10,
        title="Foo",
        status="Done",
        assignees=("alice",),
        labels=("bug",),
    )


def test_parse_item_returns_none_when_content_is_missing():
    node = {"fieldValues": {"nodes": []}, "content": None}
    assert _parse_item(node) is None


def test_parse_item_returns_none_for_empty_content_dict():
    # dict vazio é falsy em Python — tratado como ausência de conteúdo
    node = {"fieldValues": {"nodes": []}, "content": {}}
    assert _parse_item(node) is None


def test_parse_item_handles_multiple_assignees_and_labels():
    node = issue_node(assignees=["alice", "bob"], labels=["bug", "enhancement"])
    item = _parse_item(node)

    assert item.assignees == ("alice", "bob")
    assert item.labels == ("bug", "enhancement")


# --- KanbanFetcher.fetch_all ---

def test_fetch_all_returns_items_from_single_page():
    nodes = [issue_node(number=1, title="Issue 1", status="Done")]
    client = FakeClient([page_response(nodes, has_next=False)])

    fetcher = KanbanFetcher(client, org="MyOrg", project_number=1)
    items = fetcher.fetch_all()

    assert len(items) == 1
    assert items[0].number == 1


def test_fetch_all_accumulates_items_across_pages():
    page1 = page_response([issue_node(number=1)], has_next=True, end_cursor="cursor1")
    page2 = page_response([issue_node(number=2)], has_next=False)
    client = FakeClient([page1, page2])

    fetcher = KanbanFetcher(client, org="MyOrg", project_number=1)
    items = fetcher.fetch_all()

    assert len(items) == 2
    assert {item.number for item in items} == {1, 2}


def test_fetch_all_skips_nodes_without_content():
    nodes = [
        {"fieldValues": {"nodes": []}, "content": None},
        issue_node(number=5, title="Real issue"),
    ]
    client = FakeClient([page_response(nodes, has_next=False)])

    fetcher = KanbanFetcher(client, org="MyOrg", project_number=1)
    items = fetcher.fetch_all()

    assert len(items) == 1
    assert items[0].number == 5


def test_fetch_all_returns_empty_list_when_no_items():
    client = FakeClient([page_response([], has_next=False)])

    fetcher = KanbanFetcher(client, org="MyOrg", project_number=1)
    items = fetcher.fetch_all()

    assert items == []

import argparse
import json
import logging

from src.config import get_github_token
from src.db import (
    get_collection_state,
    get_connection,
    init_db,
    save_collection_state,
    upsert_repositories,
)
from src.github_client import GitHubGraphQLClient
from src.queries import (
    MAX_GITHUB_SEARCH_PAGE_SIZE,
    REPOSITORY_SEARCH_QUERY,
    TOP_STARRED_REPOSITORIES_SEARCH_QUERY,
)

logger = logging.getLogger(__name__)


def parse_repository_node(node):
    owner = node["owner"]["login"]
    language = node["primaryLanguage"]
    return {
        "id": node["id"],
        "name": node["name"],
        "owner": owner,
        "stargazer_count": node["stargazerCount"],
        "created_at": node["createdAt"],
        "pushed_at": node["pushedAt"],
        "primary_language": language["name"] if language else None,
        "merged_pull_requests": node["mergedPullRequests"]["totalCount"],
        "releases_count": node["releases"]["totalCount"],
        "open_issues": node["openIssues"]["totalCount"],
        "closed_issues": node["closedIssues"]["totalCount"],
        "raw_json": json.dumps(node, ensure_ascii=False),
    }


def collect_page(client, connection, per_page):
    state = get_collection_state(connection)
    cursor = state["cursor"]
    logger.info(
        "iniciando coleta a partir do cursor=%s (total já coletado=%s)",
        cursor,
        state["total_collected"],
    )

    data = client.execute(
        REPOSITORY_SEARCH_QUERY,
        variables={
            "searchQuery": TOP_STARRED_REPOSITORIES_SEARCH_QUERY,
            "perPage": per_page,
            "after": cursor,
        },
    )

    search = data["search"]
    repository_nodes = [node for node in search["nodes"] if node is not None]
    repositories = [parse_repository_node(node) for node in repository_nodes]
    upsert_repositories(connection, repositories)

    new_cursor = search["pageInfo"]["endCursor"]
    total_collected = state["total_collected"] + len(repositories)
    save_collection_state(connection, new_cursor, total_collected)

    logger.info(
        "página coletada: %s repos (total acumulado=%s, hasNextPage=%s, repositoryCount=%s)",
        len(repositories),
        total_collected,
        search["pageInfo"]["hasNextPage"],
        search["repositoryCount"],
    )
    return repositories


def _page_size(raw_value):
    parsed_value = int(raw_value)
    if not 1 <= parsed_value <= MAX_GITHUB_SEARCH_PAGE_SIZE:
        raise argparse.ArgumentTypeError(
            f"--per-page deve estar entre 1 e {MAX_GITHUB_SEARCH_PAGE_SIZE} "
            "(limite da API GraphQL do GitHub)"
        )
    return parsed_value


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Coleta repositórios populares do GitHub via GraphQL."
    )
    parser.add_argument("--per-page", type=_page_size, default=10)
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args = build_arg_parser().parse_args()
    token = get_github_token()
    client = GitHubGraphQLClient(token)
    connection = get_connection()
    init_db(connection)

    try:
        repositories = collect_page(client, connection, args.per_page)
        for repository in repositories:
            logger.info(
                "  %s/%s — %s stars",
                repository["owner"],
                repository["name"],
                repository["stargazer_count"],
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

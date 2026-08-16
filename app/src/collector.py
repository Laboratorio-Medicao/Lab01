import argparse
import json
import logging
import time

from src.config import get_github_token
from src.storage import (
    get_collection_state,
    get_connection,
    init_db,
    save_collection_state,
    upsert_repositories,
)
from src.client import GitHubGraphQLClient, GraphQLRequestError
from src.errors import RateLimitReached
from src.query import (
    MAX_GITHUB_SEARCH_PAGE_SIZE,
    REPOSITORY_SEARCH_QUERY,
    TOP_STARRED_REPOSITORIES_SEARCH_QUERY,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 25
MIN_BATCH_SIZE = 5
BATCH_DELAY_SECONDS = 1.0


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
        "is_fork": int(node["isFork"]),
        "is_archived": int(node["isArchived"]),
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


def collect_total(client, connection, total, batch_size):
    current_batch_size = batch_size
    while True:
        total_collected = get_collection_state(connection)["total_collected"]
        if total_collected >= total:
            break

        page_size = min(current_batch_size, total - total_collected)
        try:
            repositories = collect_page(client, connection, page_size)
        except RateLimitReached as error:
            sleep_seconds = error.seconds_until_reset()
            logger.warning(
                "rate limit atingido; dormindo %.0fs até %s",
                sleep_seconds,
                error.reset_at,
            )
            time.sleep(sleep_seconds)
            continue
        except GraphQLRequestError as error:
            if not error.retryable or current_batch_size <= MIN_BATCH_SIZE:
                raise
            current_batch_size = max(current_batch_size // 2, MIN_BATCH_SIZE)
            logger.warning(
                "página com perPage=%s falhou de forma retomável (%s); "
                "reduzindo tamanho de lote para %s e tentando novamente",
                page_size,
                error,
                current_batch_size,
            )
            continue

        if not repositories:
            logger.warning(
                "página vazia retornada antes de atingir a meta (total_collected=%s, meta=%s); "
                "encerrando (provável fim dos resultados da busca)",
                total_collected,
                total,
            )
            break

        if get_collection_state(connection)["total_collected"] < total:
            time.sleep(BATCH_DELAY_SECONDS)

    return get_collection_state(connection)["total_collected"]


def _page_size(raw_value):
    parsed_value = int(raw_value)
    if not 1 <= parsed_value <= MAX_GITHUB_SEARCH_PAGE_SIZE:
        raise argparse.ArgumentTypeError(
            f"--per-page deve estar entre 1 e {MAX_GITHUB_SEARCH_PAGE_SIZE} "
            "(limite da API GraphQL do GitHub)"
        )
    return parsed_value


def _total(raw_value):
    parsed_value = int(raw_value)
    if parsed_value < 1:
        raise argparse.ArgumentTypeError("--total deve ser maior ou igual a 1")
    return parsed_value


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Coleta repositórios populares do GitHub via GraphQL."
    )
    parser.add_argument("--per-page", type=_page_size, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--total",
        type=_total,
        default=None,
        help=(
            "quantidade total de repositórios a coletar, buscando em lotes de "
            "--per-page até atingir a meta (ex.: --total 100, --total 1000). "
            "Se omitido, coleta uma única página."
        ),
    )
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args = build_arg_parser().parse_args()
    token = get_github_token()
    client = GitHubGraphQLClient(token)
    connection = get_connection()
    init_db(connection)

    try:
        if args.total is not None:
            total_collected = collect_total(client, connection, args.total, args.per_page)
            logger.info(
                "coleta finalizada: total_collected=%s (meta=%s)", total_collected, args.total
            )
        else:
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

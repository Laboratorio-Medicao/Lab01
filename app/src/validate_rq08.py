from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from src import storage
from src.config import get_github_token
from src.metrics import compute_fork_star_ratio
from src.rest_client import RestClient, RestNotFoundError
from src.storage import get_connection

DEFAULT_SAMPLE_SIZE = 8
CANDIDATE_POOL_MULTIPLIER = 3
MIN_SAMPLE_SIZE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "validacoes" / "validacao-rq08.md"


@dataclass
class ValidationResult:
    repo: str
    fork_count_query: int
    fork_count_rest: int | None
    fork_star_ratio: float | None
    matches: bool


class InsufficientSampleError(RuntimeError):
    pass


def fetch_candidate_pool(connection, pool_size):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT owner, name, fork_count, stargazer_count
            FROM {storage.REPOSITORIES_TABLE}
            WHERE fork_count = 0
            ORDER BY stargazer_count ASC
            LIMIT %s
            """,
            (pool_size,),
        )
        zero_fork_rows = cursor.fetchall()

        cursor.execute(
            f"""
            SELECT owner, name, fork_count, stargazer_count
            FROM {storage.REPOSITORIES_TABLE}
            WHERE fork_count > 0
            ORDER BY fork_count ASC, stargazer_count ASC
            LIMIT %s
            """,
            (pool_size,),
        )
        non_zero_fork_rows = cursor.fetchall()

    interleaved_rows = [
        row
        for pair in zip_longest(non_zero_fork_rows, zero_fork_rows)
        for row in pair
        if row is not None
    ]

    return [
        {
            "owner": owner,
            "name": name,
            "fork_count": fork_count,
            "stargazer_count": stargazer_count,
        }
        for owner, name, fork_count, stargazer_count in interleaved_rows[:pool_size]
    ]


def fetch_rest_forks_count(owner, name, client):
    data = client.get(f"https://api.github.com/repos/{owner}/{name}")
    return data.get("forks_count")


def validate_candidates(candidates, sample_size, client):
    results = []
    skipped = []

    for repo in candidates:
        if len(results) >= sample_size:
            break

        label = f"{repo['owner']}/{repo['name']}"
        try:
            rest_forks_count = fetch_rest_forks_count(repo["owner"], repo["name"], client)
        except RestNotFoundError:
            skipped.append(label)
            continue

        matches = repo["fork_count"] == rest_forks_count
        fork_star_ratio = compute_fork_star_ratio(repo["fork_count"], repo["stargazer_count"])

        results.append(
            ValidationResult(
                repo=label,
                fork_count_query=repo["fork_count"],
                fork_count_rest=rest_forks_count,
                fork_star_ratio=fork_star_ratio,
                matches=matches,
            )
        )

    return results, skipped


def ensure_minimum_sample(results, minimum=MIN_SAMPLE_SIZE):
    if len(results) < minimum:
        raise InsufficientSampleError(
            f"apenas {len(results)} repositório(s) validado(s) com sucesso "
            f"(mínimo exigido: {minimum}). Aumente --sample-size ou revise os "
            "repositórios pulados por 404."
        )


def _fmt(value):
    return "null" if value is None else str(value)


def render_markdown_table(results):
    header = (
        "| Repositório | `forkCount` (query) | `forks_count` (REST) | Bate? | "
        "`fork_star_ratio` |\n"
        "|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        check = "✅" if r.matches else "❌"
        rows.append(
            f"| {r.repo} | {r.fork_count_query} | {_fmt(r.fork_count_rest)} | {check} | "
            f"{_fmt(r.fork_star_ratio)} |"
        )
    return header + "\n".join(rows) + "\n"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Valida RQ08 (bônus) cruzando fork_count com a API REST do GitHub."
    )
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    return parser


def main():
    args = build_arg_parser().parse_args()
    token = get_github_token()
    client = RestClient(token)
    connection = get_connection()

    try:
        candidates = fetch_candidate_pool(
            connection, args.sample_size * CANDIDATE_POOL_MULTIPLIER
        )
        if not candidates:
            raise RuntimeError("nenhum repositório encontrado no banco — rode o coletor antes")

        results, skipped = validate_candidates(candidates, args.sample_size, client)
    finally:
        connection.close()

    if skipped:
        print(
            f"{len(skipped)} repositório(s) pulado(s) por 404 na REST API: "
            f"{', '.join(skipped)}\n"
        )

    ensure_minimum_sample(results)

    table = render_markdown_table(results)
    print(table)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(table, encoding="utf-8")
    print(f"Tabela salva em {OUTPUT_PATH}")

    mismatches = [r for r in results if not r.matches]
    if mismatches:
        print(f"\nATENÇÃO: {len(mismatches)} repositório(s) com divergência — ver coluna 'Bate?'")


if __name__ == "__main__":
    main()

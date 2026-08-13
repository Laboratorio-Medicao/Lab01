from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from src import storage
from src.config import get_github_token
from src.rest_client import RestClient, RestNotFoundError
from src.storage import get_connection

DEFAULT_SAMPLE_SIZE = 8
CANDIDATE_POOL_MULTIPLIER = 3
MIN_SAMPLE_SIZE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "validacao-rq03-rq04.md"


@dataclass
class ValidationResult:
    repo: str
    releases_query: int
    releases_rest: int
    pushed_at_query: str | None
    pushed_at_rest: str | None
    releases_matches: bool
    pushed_at_matches: bool

    @property
    def matches(self):
        return self.releases_matches and self.pushed_at_matches


class InsufficientSampleError(RuntimeError):
    pass


def fetch_candidate_pool(connection, pool_size):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT owner, name, releases_count, pushed_at
            FROM {storage.REPOSITORIES_TABLE}
            WHERE releases_count = 0
            ORDER BY pushed_at ASC
            LIMIT %s
            """,
            (pool_size,),
        )
        zero_releases_rows = cursor.fetchall()

        cursor.execute(
            f"""
            SELECT owner, name, releases_count, pushed_at
            FROM {storage.REPOSITORIES_TABLE}
            WHERE releases_count > 0
            ORDER BY releases_count ASC, pushed_at ASC
            LIMIT %s
            """,
            (pool_size,),
        )
        non_zero_releases_rows = cursor.fetchall()

    interleaved_rows = [
        row
        for pair in zip_longest(non_zero_releases_rows, zero_releases_rows)
        for row in pair
        if row is not None
    ]

    return [
        {
            "owner": owner,
            "name": name,
            "releases_count": releases_count,
            "pushed_at": pushed_at,
        }
        for owner, name, releases_count, pushed_at in interleaved_rows[:pool_size]
    ]


def fetch_rest_repo_data(owner, name, client):
    data = client.get(f"https://api.github.com/repos/{owner}/{name}")
    return {
        "pushed_at": data.get("pushed_at"),
    }


def fetch_rest_releases_count(owner, name, client):
    releases = client.get_all_pages(f"https://api.github.com/repos/{owner}/{name}/releases")
    return len(releases)


def validate_candidates(candidates, sample_size, client):
    results = []
    skipped = []

    for repo in candidates:
        if len(results) >= sample_size:
            break

        label = f"{repo['owner']}/{repo['name']}"
        try:
            rest_repo_data = fetch_rest_repo_data(repo["owner"], repo["name"], client)
            rest_releases_count = fetch_rest_releases_count(repo["owner"], repo["name"], client)
        except RestNotFoundError:
            skipped.append(label)
            continue

        releases_matches = repo["releases_count"] == rest_releases_count
        pushed_at_matches = repo["pushed_at"] == rest_repo_data["pushed_at"]

        results.append(
            ValidationResult(
                repo=label,
                releases_query=repo["releases_count"],
                releases_rest=rest_releases_count,
                pushed_at_query=repo["pushed_at"],
                pushed_at_rest=rest_repo_data["pushed_at"],
                releases_matches=releases_matches,
                pushed_at_matches=pushed_at_matches,
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
        "| Repositório | `releases_count` (query) | `releases` (REST) | Bate? | "
        "`pushed_at` (query) | `pushed_at` (REST) | Bate? |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        releases_check = "✅" if r.releases_matches else "❌"
        pushed_at_check = "✅" if r.pushed_at_matches else "❌"
        rows.append(
            f"| {r.repo} | {r.releases_query} | {r.releases_rest} | {releases_check} | "
            f"{_fmt(r.pushed_at_query)} | {_fmt(r.pushed_at_rest)} | {pushed_at_check} |"
        )
    return header + "\n".join(rows) + "\n"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Valida RQ03/RQ04 cruzando dados coletados com a API REST do GitHub."
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
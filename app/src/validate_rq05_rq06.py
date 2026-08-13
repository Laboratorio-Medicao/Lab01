from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from src import storage
from src.config import get_github_token
from src.metrics import compute_closed_issues_ratio
from src.rest_client import RestClient, RestNotFoundError
from src.storage import get_connection

DEFAULT_SAMPLE_SIZE = 8
CANDIDATE_POOL_MULTIPLIER = 3
MIN_SAMPLE_SIZE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "validacao-rq05-rq06.md"


@dataclass
class ValidationResult:
    repo: str
    language_query: str | None
    language_rest: str | None
    open_issues_query: int
    open_issues_rest: int
    closed_issues_query: int
    closed_issues_rest: int
    zero_issues: bool
    language_matches: bool
    issues_match: bool
    closed_issues_ratio_query: float | None = None
    closed_issues_ratio_rest: float | None = None

    @property
    def matches(self):
        return self.language_matches and self.issues_match


class InsufficientSampleError(RuntimeError):
    pass


def fetch_candidate_pool(connection, pool_size):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT owner, name, primary_language, open_issues, closed_issues FROM (
                SELECT owner, name, primary_language, open_issues, closed_issues
                FROM {storage.REPOSITORIES_TABLE}
                WHERE (open_issues + closed_issues) = 0
                LIMIT 1
            ) AS zero_issues_repo

            UNION ALL

            SELECT owner, name, primary_language, open_issues, closed_issues FROM (
                SELECT owner, name, primary_language, open_issues, closed_issues
                FROM {storage.REPOSITORIES_TABLE}
                WHERE (open_issues + closed_issues) > 0
                ORDER BY (open_issues + closed_issues) ASC
                LIMIT %s
            ) AS non_zero_issues_pool
            """,
            (pool_size - 1,),
        )
        rows = cursor.fetchall()
    return [
        {
            "owner": owner,
            "name": name,
            "primary_language": primary_language,
            "open_issues": open_issues,
            "closed_issues": closed_issues,
        }
        for owner, name, primary_language, open_issues, closed_issues in rows
    ]


def fetch_rest_repo_data(owner, name, client):
    data = client.get(f"https://api.github.com/repos/{owner}/{name}")
    return {
        "language": data.get("language"),
    }


def fetch_rest_open_issues_count(owner, name, client):
    items = client.get_all_pages(
        f"https://api.github.com/repos/{owner}/{name}/issues?state=open"
    )
    return sum(1 for item in items if "pull_request" not in item)


def fetch_rest_closed_issues_count(owner, name, client):
    items = client.get_all_pages(
        f"https://api.github.com/repos/{owner}/{name}/issues?state=closed"
    )
    return sum(1 for item in items if "pull_request" not in item)


def validate_candidates(candidates, sample_size, client):
    results = []
    skipped = []

    for repo in candidates:
        if len(results) >= sample_size:
            break

        label = f"{repo['owner']}/{repo['name']}"
        try:
            rest_data = fetch_rest_repo_data(repo["owner"], repo["name"], client)
            rest_open = fetch_rest_open_issues_count(repo["owner"], repo["name"], client)
            rest_closed = fetch_rest_closed_issues_count(repo["owner"], repo["name"], client)
        except RestNotFoundError:
            skipped.append(label)
            continue

        zero_issues = (repo["open_issues"] + repo["closed_issues"]) == 0

        lang_query = repo["primary_language"] or None
        lang_rest = rest_data["language"] or None

        open_issues_matches = repo["open_issues"] == rest_open
        closed_issues_matches = repo["closed_issues"] == rest_closed

        results.append(ValidationResult(
            repo=label,
            language_query=lang_query,
            language_rest=lang_rest,
            open_issues_query=repo["open_issues"],
            open_issues_rest=rest_open,
            closed_issues_query=repo["closed_issues"],
            closed_issues_rest=rest_closed,
            zero_issues=zero_issues,
            language_matches=lang_query == lang_rest,
            issues_match=open_issues_matches and closed_issues_matches,
            closed_issues_ratio_query=compute_closed_issues_ratio(
                repo["open_issues"], repo["closed_issues"]
            ),
            closed_issues_ratio_rest=compute_closed_issues_ratio(rest_open, rest_closed),
        ))

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
        "| Repositório "
        "| `primaryLanguage` (query) | `language` (REST) "
        "| `openIssues` (query) | issues abertas (REST) "
        "| `closedIssues` (query) | issues fechadas (REST) "
        "| Razão fechadas/total (query) | Razão fechadas/total (REST) "
        "| Zero issues? | Linguagem bate? | Issues batem? |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        lang_check = "✅" if r.language_matches else "❌"
        issues_check = "✅" if r.issues_match else "❌"
        zero_flag = "⚠️ sim" if r.zero_issues else "não"
        rows.append(
            f"| {r.repo} "
            f"| {_fmt(r.language_query)} | {_fmt(r.language_rest)} "
            f"| {r.open_issues_query} | {r.open_issues_rest} "
            f"| {r.closed_issues_query} | {r.closed_issues_rest} "
            f"| {_fmt(r.closed_issues_ratio_query)} | {_fmt(r.closed_issues_ratio_rest)} "
            f"| {zero_flag} | {lang_check} | {issues_check} |"
        )
    return header + "\n".join(rows) + "\n"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Valida RQ05/RQ06 cruzando dados coletados com a API REST do GitHub."
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
            raise RuntimeError(
                "nenhum repositório encontrado no banco — rode o coletor antes"
            )
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
        print(f"\nATENÇÃO: {len(mismatches)} repositório(s) com divergência — ver coluna bate?")


if __name__ == "__main__":
    main()

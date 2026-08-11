import argparse
from pathlib import Path

from src import storage
from src.config import get_github_token
from src.rest_client import RestClient, RestNotFoundError
from src.storage import get_connection
from src.validate_rq01_rq02 import compute_age_years

DEFAULT_SAMPLE_SIZE = 8
CANDIDATE_POOL_MULTIPLIER = 3
MIN_SAMPLE_SIZE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "validacao-rq08.md"


class InsufficientSampleError(RuntimeError):
    pass


def fetch_candidate_pool(connection, pool_size):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT owner, name, stargazer_count, created_at, collected_at,
                   merged_pull_requests, releases_count, closed_issues
            FROM {storage.REPOSITORIES_TABLE}
            ORDER BY releases_count ASC
            LIMIT %s
            """,
            (pool_size,),
        )
        rows = cursor.fetchall()
    return [
        {
            "owner": owner,
            "name": name,
            "stargazer_count": stargazer_count,
            "created_at": created_at,
            "collected_at": collected_at,
            "merged_pull_requests": merged_pull_requests,
            "releases_count": releases_count,
            "closed_issues": closed_issues,
        }
        for (
            owner,
            name,
            stargazer_count,
            created_at,
            collected_at,
            merged_pull_requests,
            releases_count,
            closed_issues,
        ) in rows
    ]


def fetch_rest_releases_count(owner, name, client):
    releases = client.get_all_pages(
        f"https://api.github.com/repos/{owner}/{name}/releases"
    )
    return len(releases)


def compute_star_velocity(stargazer_count, age_years):
    return round(stargazer_count / age_years, 1)


def compute_engagement_score(merged_pull_requests, releases_count, closed_issues, age_years):
    return round((merged_pull_requests + releases_count + closed_issues) / age_years, 1)


def validate_candidates(candidates, sample_size, client):
    results = []
    skipped = []
    for repo in candidates:
        if len(results) >= sample_size:
            break

        label = f"{repo['owner']}/{repo['name']}"
        try:
            rest_releases_count = fetch_rest_releases_count(repo["owner"], repo["name"], client)
        except RestNotFoundError:
            skipped.append(label)
            continue

        age_years = compute_age_years(repo["created_at"], repo["collected_at"])
        star_velocity = compute_star_velocity(repo["stargazer_count"], age_years)
        engagement_score = compute_engagement_score(
            repo["merged_pull_requests"], repo["releases_count"], repo["closed_issues"], age_years
        )
        releases_matches = repo["releases_count"] == rest_releases_count

        results.append(
            {
                "repo": label,
                "age_years": age_years,
                "star_velocity": star_velocity,
                "engagement_score": engagement_score,
                "releases_query": repo["releases_count"],
                "releases_rest": rest_releases_count,
                "matches": releases_matches,
            }
        )
    return results, skipped


def ensure_minimum_sample(results, minimum=MIN_SAMPLE_SIZE):
    if len(results) < minimum:
        raise InsufficientSampleError(
            f"apenas {len(results)} repositório(s) validado(s) com sucesso "
            f"(mínimo exigido: {minimum}). Aumente --sample-size ou revise os "
            "repositórios pulados por 404."
        )


def render_markdown_table(results):
    header = (
        "| Repositório | Idade (anos) | Releases (query) | Releases (REST) | "
        "razão_estrelas | score_engajamento | Bate? |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        check = "✅" if r["matches"] else "❌"
        rows.append(
            f"| {r['repo']} | {r['age_years']} | {r['releases_query']} | {r['releases_rest']} | "
            f"{r['star_velocity']} | {r['engagement_score']} | {check} |"
        )
    return header + "\n".join(rows) + "\n"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Valida RQ08 cruzando releases_count com a API REST do GitHub."
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
            f"{len(skipped)} repositório(s) pulado(s) por indisponibilidade da "
            f"listagem REST /releases: {', '.join(skipped)}\n"
        )

    ensure_minimum_sample(results)

    table = render_markdown_table(results)
    print(table)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(table, encoding="utf-8")
    print(f"Tabela salva em {OUTPUT_PATH}")

    mismatches = [r for r in results if not r["matches"]]
    if mismatches:
        print(f"\nATENÇÃO: {len(mismatches)} repositório(s) com divergência — ver coluna 'Bate?'")


if __name__ == "__main__":
    main()

"""Valida RQ01 (idade do repositório) e RQ02 (PRs merged) contra fontes
independentes da API REST/Search do GitHub, para uma amostra dos repositórios
já coletados no Postgres (Supabase).

Uso:
    python -m src.validate_rq01_rq02 [--sample-size N]

Gera uma tabela Markdown (seção 5 da especificação da issue #4) em stdout e em
docs/validacao-rq01-rq02.md, pronta para ser colada como comentário na issue.

Fórmula de idade (decisão registrada em docs/metodologia.md):
    idade_em_anos = (collected_at_UTC - created_at) / 365.25 dias
`collected_at` é o timestamp UTC salvo por linha no momento da coleta (não a
data em que este script de validação roda), garantindo reprodutibilidade.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from src import storage
from src.config import get_github_token
from src.rest_client import RestClient, RestNotFoundError
from src.storage import get_connection

DAYS_PER_YEAR = 365.25
DEFAULT_SAMPLE_SIZE = 8
CANDIDATE_POOL_MULTIPLIER = 3
# Mínimo exigido pela seção 5 da especificação da issue #4 ("mínimo de 5
# repositórios preenchidos"). Ver ensure_minimum_sample().
MIN_SAMPLE_SIZE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "validacao-rq01-rq02.md"


class InsufficientSampleError(RuntimeError):
    pass


def _parse_iso8601(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def compute_age_years(created_at, collected_at):
    created = _parse_iso8601(created_at)
    collected = datetime.strptime(collected_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    age_days = (collected - created).total_seconds() / 86400
    return round(age_days / DAYS_PER_YEAR, 1)


def fetch_candidate_pool(connection, pool_size):
    # Ordenado por merged_pull_requests ASC (não por estrelas): a conferência cruzada
    # pagina manualmente os PRs merged via REST, o que é inviável em tempo hábil para
    # repositórios com dezenas de milhares de PRs. Repos com poucas merged PRs (incluindo
    # o caso de 0, ex.: torvalds/linux, que não usa PRs do GitHub) ainda são repositórios
    # reais do top-estrelas coletado, e cobrem o caso de nulo/zero da seção 3.5 da spec.
    # O pool é maior que a amostra final porque alguns repositórios têm a listagem REST
    # de /pulls indisponível (has_issues=false) e são pulados — ver fetch_merged_pr_count.
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT owner, name, created_at, merged_pull_requests, collected_at
            FROM {storage.REPOSITORIES_TABLE}
            ORDER BY merged_pull_requests ASC
            LIMIT %s
            """,
            (pool_size,),
        )
        rows = cursor.fetchall()
    return [
        {
            "owner": owner,
            "name": name,
            "created_at": created_at,
            "merged_pull_requests": merged_pull_requests,
            "collected_at": collected_at,
        }
        for owner, name, created_at, merged_pull_requests, collected_at in rows
    ]


def fetch_rest_created_at(owner, name, client):
    data = client.get(f"https://api.github.com/repos/{owner}/{name}")
    return data["created_at"]


def fetch_merged_pr_count_via_rest_pagination(owner, name, client):
    """Conta PRs merged paginando /pulls?state=closed e checando merged_at.

    Mais lento que a Search API, mas evita a defasagem de indexação conhecida
    da Search API (ver docs/metodologia.md) — é a fonte da verdade para a
    conferência cruzada, não uma estimativa.
    """
    pulls = client.get_all_pages(
        f"https://api.github.com/repos/{owner}/{name}/pulls?state=closed"
    )
    return sum(1 for pr in pulls if pr.get("merged_at") is not None)


def validate_candidates(candidates, sample_size, client):
    results = []
    skipped = []
    for repo in candidates:
        if len(results) >= sample_size:
            break

        label = f"{repo['owner']}/{repo['name']}"
        try:
            rest_created_at = fetch_rest_created_at(repo["owner"], repo["name"], client)
            rest_merged_count = fetch_merged_pr_count_via_rest_pagination(
                repo["owner"], repo["name"], client
            )
        except RestNotFoundError:
            # Observado em ao menos um repositório da amostra (has_issues=false no
            # REST): a listagem /pulls retorna 404 mesmo com o repositório existindo
            # e tendo PRs merged reais (confirmados via GraphQL). Pulamos para o
            # próximo candidato em vez de contar como divergência de dado.
            skipped.append(label)
            continue

        age_years = compute_age_years(repo["created_at"], repo["collected_at"])
        created_at_matches = repo["created_at"] == rest_created_at
        merged_matches = repo["merged_pull_requests"] == rest_merged_count

        results.append(
            {
                "repo": label,
                "created_at_query": repo["created_at"],
                "created_at_rest": rest_created_at,
                "age_years": age_years,
                "merged_query": repo["merged_pull_requests"],
                "merged_rest": rest_merged_count,
                "matches": created_at_matches and merged_matches,
            }
        )
    return results, skipped


def ensure_minimum_sample(results, minimum=MIN_SAMPLE_SIZE):
    if len(results) < minimum:
        raise InsufficientSampleError(
            f"apenas {len(results)} repositório(s) validado(s) com sucesso "
            f"(mínimo exigido pela spec da issue #4: {minimum}). Aumente "
            "--sample-size ou revise os repositórios pulados por 404."
        )


def render_markdown_table(results):
    header = (
        "| Repositório | `createdAt` (query) | `created_at` (REST API) | "
        "Idade calculada (anos) | PRs merged (query) | PRs merged (paginação REST) | Bate? |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        check = "✅" if r["matches"] else "❌"
        rows.append(
            f"| {r['repo']} | {r['created_at_query']} | {r['created_at_rest']} | "
            f"{r['age_years']} | {r['merged_query']} | {r['merged_rest']} | {check} |"
        )
    return header + "\n".join(rows) + "\n"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Valida RQ01/RQ02 cruzando dados coletados com a API REST/Search do GitHub."
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
            f"listagem REST /pulls (ex.: has_issues=false): {', '.join(skipped)}\n"
        )

    ensure_minimum_sample(results)

    table = render_markdown_table(results)
    print(table)

    OUTPUT_PATH.write_text(table, encoding="utf-8")
    print(f"\nTabela salva em {OUTPUT_PATH}")

    mismatches = [r for r in results if not r["matches"]]
    if mismatches:
        print(f"\nATENÇÃO: {len(mismatches)} repositório(s) com divergência — ver coluna 'Bate?'")


if __name__ == "__main__":
    main()

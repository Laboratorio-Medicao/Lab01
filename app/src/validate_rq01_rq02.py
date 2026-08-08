"""Valida RQ01 (idade do repositório) e RQ02 (PRs merged) contra fontes
independentes da API REST/Search do GitHub, para uma amostra dos repositórios
já coletados em data/repos.db.

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
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.config import get_github_token
from src.db import get_connection

DAYS_PER_YEAR = 365.25
DEFAULT_SAMPLE_SIZE = 8
CANDIDATE_POOL_MULTIPLIER = 3
# Mínimo exigido pela seção 5 da especificação da issue #4 ("mínimo de 5
# repositórios preenchidos"). Ver ensure_minimum_sample().
MIN_SAMPLE_SIZE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "validacao-rq01-rq02.md"

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_SERVER_ERROR_CODES = {500, 502, 503, 504}
RETRYABLE_THROTTLING_CODES = {403, 429}


class RestNotFoundError(RuntimeError):
    pass


class InsufficientSampleError(RuntimeError):
    pass


class _RetryableTransportError(RuntimeError):
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


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
    rows = connection.execute(
        """
        SELECT owner, name, created_at, merged_pull_requests, collected_at
        FROM repositories
        ORDER BY merged_pull_requests ASC
        LIMIT ?
        """,
        (pool_size,),
    ).fetchall()
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


def _rest_get(url, token, max_attempts=DEFAULT_MAX_ATTEMPTS):
    """GET com retry/backoff para 5xx e 403/429 (mesmo padrão de retry do
    GitHubGraphQLClient em github_client.py, adaptado para REST). 404 nunca é
    retentável — vira RestNotFoundError imediatamente (ver validate_candidates)."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return _rest_get_once(url, token)
        except _RetryableTransportError as error:
            last_error = error
            if attempt == max_attempts:
                break
            delay_seconds = error.retry_after_seconds
            if delay_seconds is None:
                delay_seconds = DEFAULT_RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            time.sleep(delay_seconds)
    raise RuntimeError(str(last_error)) from last_error


def _rest_get_once(url, token):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "lab01-validation-script",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        if error.code == 404:
            raise RestNotFoundError(f"HTTP 404 em {url}: {body}") from error

        retry_after_seconds = _parse_retry_after_header(error.headers)
        is_server_error = error.code in RETRYABLE_SERVER_ERROR_CODES
        is_throttled = error.code in RETRYABLE_THROTTLING_CODES and (
            error.code == 429 or retry_after_seconds is not None
        )
        message = f"HTTP {error.code} em {url}: {body}"
        if is_server_error or is_throttled:
            raise _RetryableTransportError(message, retry_after_seconds=retry_after_seconds) from error
        raise RuntimeError(message) from error


def _parse_retry_after_header(headers):
    if not headers:
        return None
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 1.0)
    except (TypeError, ValueError):
        return None


def fetch_rest_created_at(owner, name, token):
    data = _rest_get(f"https://api.github.com/repos/{owner}/{name}", token)
    return data["created_at"]


def fetch_merged_pr_count_via_rest_pagination(owner, name, token):
    """Conta PRs merged paginando /pulls?state=closed e checando merged_at.

    Mais lento que a Search API, mas evita a defasagem de indexação conhecida
    da Search API (ver docs/metodologia.md) — é a fonte da verdade para a
    conferência cruzada, não uma estimativa.
    """
    merged_count = 0
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{owner}/{name}/pulls"
            f"?state=closed&per_page=100&page={page}"
        )
        page_data = _rest_get(url, token)
        if not page_data:
            break
        merged_count += sum(1 for pr in page_data if pr.get("merged_at") is not None)
        if len(page_data) < 100:
            break
        page += 1
    return merged_count


def validate_candidates(candidates, sample_size, token):
    results = []
    skipped = []
    for repo in candidates:
        if len(results) >= sample_size:
            break

        label = f"{repo['owner']}/{repo['name']}"
        try:
            rest_created_at = fetch_rest_created_at(repo["owner"], repo["name"], token)
            rest_merged_count = fetch_merged_pr_count_via_rest_pagination(
                repo["owner"], repo["name"], token
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
    connection = get_connection()

    try:
        candidates = fetch_candidate_pool(
            connection, args.sample_size * CANDIDATE_POOL_MULTIPLIER
        )
        if not candidates:
            raise RuntimeError("nenhum repositório encontrado em data/repos.db — rode o coletor antes")

        results, skipped = validate_candidates(candidates, args.sample_size, token)
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

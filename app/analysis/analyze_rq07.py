from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src import storage
from src.storage import get_connection

DEFAULT_TOP_LANGUAGES = 10
DEFAULT_MIN_REPOS = 10
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "analises" / "analise-rq07.md"


@dataclass
class LanguageStats:
    language: str
    repo_count: int
    median_prs: float
    median_releases: float
    median_days_since_push: float


def _days_since_push(pushed_at: str, collected_at: str) -> float:
    """Dias entre `pushed_at` e `collected_at` — a referência de "hoje" fixada

    no momento em que aquela linha foi coletada, não o instante em que este
    script é executado. Mesmo critério de reprodutibilidade documentado em
    `docs/metodologia.md` para RQ01 (idade): cada linha carrega sua própria
    referência temporal.
    """
    dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    reference = datetime.strptime(collected_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return (reference - dt).total_seconds() / 86400


def fetch_all_repos(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT primary_language, merged_pull_requests, releases_count, pushed_at, collected_at
            FROM {storage.REPOSITORIES_TABLE}
            WHERE primary_language IS NOT NULL
              AND primary_language != ''
              AND merged_pull_requests IS NOT NULL
              AND releases_count IS NOT NULL
              AND pushed_at IS NOT NULL
            """
        )
        return cursor.fetchall()


def compute_language_stats(rows, top_n, min_repos):
    from collections import defaultdict

    buckets: dict[str, list[tuple]] = defaultdict(list)
    for language, prs, releases, pushed_at, collected_at in rows:
        buckets[language].append((prs, releases, pushed_at, collected_at))

    stats = []
    for language, entries in buckets.items():
        if len(entries) < min_repos:
            continue
        prs_list = [e[0] for e in entries]
        releases_list = [e[1] for e in entries]
        days_list = [_days_since_push(e[2], e[3]) for e in entries]
        stats.append(LanguageStats(
            language=language,
            repo_count=len(entries),
            median_prs=statistics.median(prs_list),
            median_releases=statistics.median(releases_list),
            median_days_since_push=statistics.median(days_list),
        ))

    stats.sort(key=lambda s: s.repo_count, reverse=True)
    return stats[:top_n]


def _conclude(stats: list[LanguageStats]) -> str:
    if len(stats) < 2:
        return "Amostra insuficiente para conclusão.\n"

    top = stats[0]
    # Correlação de Spearman manual: rank de popularidade vs rank de cada métrica
    n = len(stats)
    ranks = list(range(1, n + 1))

    def spearman(values):
        sorted_vals = sorted(enumerate(values), key=lambda x: x[1], reverse=True)
        metric_ranks = [0] * n
        for rank, (idx, _) in enumerate(sorted_vals, 1):
            metric_ranks[idx] = rank
        d2 = sum((ranks[i] - metric_ranks[i]) ** 2 for i in range(n))
        return 1 - (6 * d2) / (n * (n ** 2 - 1))

    prs_vals = [s.median_prs for s in stats]
    rel_vals = [s.median_releases for s in stats]
    upd_vals = [-s.median_days_since_push for s in stats]  # menos dias = mais atualizado

    r_prs = spearman(prs_vals)
    r_rel = spearman(rel_vals)
    r_upd = spearman(upd_vals)

    def interpret(r):
        if r > 0.5:
            return "correlação positiva"
        if r < -0.5:
            return "correlação negativa"
        return "sem correlação clara"

    lines = [
        "\n## Conclusão RQ07\n",
        "A correlação de Spearman (ρ) mede se duas variáveis caminham juntas, variando de "
        "**-1 a 1**: valores próximos de **1** indicam que quanto mais popular a linguagem, "
        "maior a métrica; valores próximos de **-1** indicam o oposto; valores próximos de "
        "**0** indicam ausência de relação.\n",
        "Correlação entre popularidade da linguagem (nº de repos na amostra) e cada métrica:\n",
        f"- **PRs mergeadas por repo (RQ02):** ρ = {r_prs:.2f} → {interpret(r_prs)}",
        f"- **Releases por repo (RQ03):** ρ = {r_rel:.2f} → {interpret(r_rel)}",
        f"- **Frequência de atualização — dias desde último push (RQ04):** ρ = {r_upd:.2f} → {interpret(r_upd)}\n",
    ]

    verdicts = [interpret(r_prs), interpret(r_rel), interpret(r_upd)]
    if verdicts.count("correlação positiva") >= 2:
        lines.append("**Resposta:** Sim, linguagens mais populares tendem a receber mais contribuição, releases e atualizações.")
    elif verdicts.count("correlação negativa") >= 2:
        lines.append("**Resposta:** Não, linguagens mais populares não apresentam mais contribuição, releases ou atualizações.")
    else:
        lines.append("**Resposta:** Não há evidência consistente de que linguagens mais populares recebam mais contribuição, releases ou atualizações.")

    lines.append("")
    return "\n".join(lines)


def render_markdown(stats: list[LanguageStats]) -> str:
    lines = [
        "# Análise RQ07 — Linguagem vs. Contribuição, Releases e Atualização\n",
        "**Metodologia:** mediana por linguagem; linguagens ordenadas por número de "
        "repositórios na amostra (proxy de popularidade).\n",
        "| Linguagem | Nº de repos | Mediana de PRs mergeadas por repo (RQ02) "
        "| Mediana de releases por repo (RQ03) | Mediana de dias desde último push (RQ04) |",
        "|---|---|---|---|---|",
    ]
    for s in stats:
        lines.append(
            f"| {s.language} | {s.repo_count} "
            f"| {s.median_prs:.1f} | {s.median_releases:.1f} "
            f"| {s.median_days_since_push:.1f} |"
        )
    lines.append("")
    return "\n".join(lines) + _conclude(stats)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Análise RQ07: métricas de RQ02/RQ03/RQ04 por linguagem."
    )
    parser.add_argument(
        "--top", type=int, default=DEFAULT_TOP_LANGUAGES,
        help="Número de linguagens mais populares a exibir (padrão: %(default)s)"
    )
    parser.add_argument(
        "--min-repos", type=int, default=DEFAULT_MIN_REPOS,
        help="Mínimo de repositórios por linguagem para incluir (padrão: %(default)s)"
    )
    return parser


def main():
    args = build_arg_parser().parse_args()
    connection = get_connection()

    try:
        rows = fetch_all_repos(connection)
    finally:
        connection.close()

    if not rows:
        raise RuntimeError("nenhum repositório encontrado — rode o coletor antes")

    stats = compute_language_stats(rows, top_n=args.top, min_repos=args.min_repos)

    if not stats:
        raise RuntimeError(
            f"nenhuma linguagem com pelo menos {args.min_repos} repositórios — "
            "reduza --min-repos"
        )

    table = render_markdown(stats)
    print(table)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(table, encoding="utf-8")
    print(f"Análise salva em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src import storage
from src.storage import get_connection

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "analises" / "analise-rq03-rq04.md"
EXPECTED_TOTAL_ROWS = 1000


@dataclass
class NumericSummary:
    count: int
    mean: float
    median: float
    min_value: float
    q1: float
    q3: float
    max_value: float
    iqr: float


@dataclass
class OutlierSummary:
    lower_bound: float
    upper_bound: float
    count: int


@dataclass
class RQ03RQ04Analysis:
    total_rows: int
    releases_missing: int
    pushed_at_missing: int
    pushed_at_invalid: int
    pushed_at_future: int
    releases_summary: NumericSummary
    days_since_push_summary: NumericSummary
    releases_outliers: OutlierSummary
    days_since_push_outliers: OutlierSummary
    zero_releases_count: int
    very_old_push_count: int


def percentile_inc(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("lista vazia para cálculo de percentil")
    if p <= 0:
        return sorted_values[0]
    if p >= 1:
        return sorted_values[-1]

    n = len(sorted_values)
    rank = 1 + (n - 1) * p
    lower_idx = int(math.floor(rank)) - 1
    upper_idx = int(math.ceil(rank)) - 1
    if lower_idx == upper_idx:
        return sorted_values[lower_idx]

    lower_value = sorted_values[lower_idx]
    upper_value = sorted_values[upper_idx]
    frac = rank - math.floor(rank)
    return lower_value + frac * (upper_value - lower_value)


def summarize(values: list[float]) -> NumericSummary:
    if not values:
        raise ValueError("não há valores para sumarizar")

    sorted_values = sorted(values)
    q1 = percentile_inc(sorted_values, 0.25)
    median = percentile_inc(sorted_values, 0.50)
    q3 = percentile_inc(sorted_values, 0.75)
    return NumericSummary(
        count=len(values),
        mean=statistics.fmean(values),
        median=median,
        min_value=sorted_values[0],
        q1=q1,
        q3=q3,
        max_value=sorted_values[-1],
        iqr=q3 - q1,
    )


def compute_outlier_summary(values: list[float], summary: NumericSummary) -> OutlierSummary:
    lower_bound = summary.q1 - 1.5 * summary.iqr
    upper_bound = summary.q3 + 1.5 * summary.iqr
    count = sum(1 for value in values if value < lower_bound or value > upper_bound)
    return OutlierSummary(lower_bound=lower_bound, upper_bound=upper_bound, count=count)


def parse_iso_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_collected_at(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def fetch_rows(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT releases_count, pushed_at, collected_at
            FROM {storage.REPOSITORIES_TABLE}
            """
        )
        return cursor.fetchall()


def validate_total_rows(total_rows: int, expected_total: int = EXPECTED_TOTAL_ROWS) -> None:
    if total_rows != expected_total:
        raise RuntimeError(
            f"a análise RQ03/RQ04 exige exatamente {expected_total} repositórios; "
            f"foram encontrados {total_rows}"
        )


def run_analysis(rows) -> RQ03RQ04Analysis:
    """Calcula RQ03/RQ04 sobre `rows` de (releases_count, pushed_at, collected_at).

    RQ04 usa `collected_at` de cada linha como referência de "hoje" — não o
    instante em que este script é executado — pelo mesmo motivo já registrado
    em `docs/metodologia.md` para RQ01 (idade): garante que o resultado seja
    reproduzível independente de quando a análise é rodada, já que cada linha
    carrega sua própria referência temporal (fixada no momento da coleta).
    """
    releases_values: list[float] = []
    days_since_push_values: list[float] = []

    releases_missing = 0
    pushed_at_missing = 0
    pushed_at_invalid = 0
    pushed_at_future = 0
    zero_releases_count = 0
    very_old_push_count = 0

    for releases_count, pushed_at, collected_at in rows:
        if releases_count is None:
            releases_missing += 1
        else:
            releases = float(releases_count)
            releases_values.append(releases)
            if releases_count == 0:
                zero_releases_count += 1

        if pushed_at is None or str(pushed_at).strip() == "":
            pushed_at_missing += 1
            continue

        try:
            pushed_at_dt = parse_iso_utc(str(pushed_at))
        except ValueError:
            pushed_at_invalid += 1
            continue

        reference_date = parse_collected_at(str(collected_at))
        delta_days = (reference_date - pushed_at_dt).total_seconds() / 86400
        if delta_days < 0:
            pushed_at_future += 1
            continue

        days_since_push_values.append(delta_days)
        if delta_days >= 3650:
            very_old_push_count += 1

    if not releases_values:
        raise RuntimeError("todos os releases_count estão ausentes; análise de RQ03 inviável")
    if not days_since_push_values:
        raise RuntimeError("todos os pushed_at estão ausentes/inválidos/futuros; análise de RQ04 inviável")

    releases_summary = summarize(releases_values)
    days_summary = summarize(days_since_push_values)

    releases_outliers = compute_outlier_summary(releases_values, releases_summary)
    days_outliers = compute_outlier_summary(days_since_push_values, days_summary)

    return RQ03RQ04Analysis(
        total_rows=len(rows),
        releases_missing=releases_missing,
        pushed_at_missing=pushed_at_missing,
        pushed_at_invalid=pushed_at_invalid,
        pushed_at_future=pushed_at_future,
        releases_summary=releases_summary,
        days_since_push_summary=days_summary,
        releases_outliers=releases_outliers,
        days_since_push_outliers=days_outliers,
        zero_releases_count=zero_releases_count,
        very_old_push_count=very_old_push_count,
    )


def _pct(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return (part / total) * 100


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def build_hypothesis_block() -> str:
    return (
        "## Hipótese Informal (RQ03 e RQ04)\n\n"
        "**RQ03 (total de releases):** espera-se uma distribuição assimétrica à direita, "
        "com muitos repositórios populares tendo poucos releases formais (incluindo 0) e "
        "um grupo menor concentrando grande volume de releases. Isso acontece porque "
        "parte dos projetos adota entrega contínua sem versionamento frequente por release.\n\n"
        "**RQ04 (tempo desde última atualização):** espera-se concentração em valores baixos "
        "(dias ou poucas semanas), pois repositórios muito populares tendem a manter atividade "
        "contínua. Ainda assim, deve existir uma cauda de projetos estáveis/legados com "
        "último push antigo, inclusive alguns outliers.\n"
    )


def render_markdown(result: RQ03RQ04Analysis) -> str:
    rel = result.releases_summary
    dps = result.days_since_push_summary

    lines = [
        "# Análise Exploratória — RQ03 e RQ04 (1000 repositórios)\n",
        "Esta análise usa os dados completos da coleta (S02), sem nova validação REST amostral.",
        "Referência para RQ04: `collected_at` de cada repositório (não a data de execução "
        "deste script) — garante reprodutibilidade, mesmo critério já usado em RQ01.",
        "",
        "## Sumário Estatístico",
        "",
        "| Métrica | N válido | Média | Mediana | Mín | Q1 | Q3 | Máx | IQR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| `releases_count` (RQ03) | {rel.count} | {_fmt(rel.mean)} | {_fmt(rel.median)} | {_fmt(rel.min_value)} | {_fmt(rel.q1)} | {_fmt(rel.q3)} | {_fmt(rel.max_value)} | {_fmt(rel.iqr)} |",
        f"| `dias_desde_ultimo_push` (RQ04) | {dps.count} | {_fmt(dps.mean)} | {_fmt(dps.median)} | {_fmt(dps.min_value)} | {_fmt(dps.q1)} | {_fmt(dps.q3)} | {_fmt(dps.max_value)} | {_fmt(dps.iqr)} |",
        "",
        "## Valores Ausentes e Qualidade dos Campos",
        "",
        f"- Total de linhas analisadas: {result.total_rows}",
        f"- `releases_count` ausente: {result.releases_missing} ({_fmt(_pct(result.releases_missing, result.total_rows))}%)",
        f"- `pushed_at` ausente/vazio: {result.pushed_at_missing} ({_fmt(_pct(result.pushed_at_missing, result.total_rows))}%)",
        f"- `pushed_at` inválido: {result.pushed_at_invalid} ({_fmt(_pct(result.pushed_at_invalid, result.total_rows))}%)",
        f"- `pushed_at` no futuro: {result.pushed_at_future} ({_fmt(_pct(result.pushed_at_future, result.total_rows))}%)",
        "",
        "## Outliers (Regra IQR)",
        "",
        "| Campo | Limite inferior | Limite superior | Qtde de outliers | % do total válido |",
        "|---|---:|---:|---:|---:|",
        f"| `releases_count` | {_fmt(result.releases_outliers.lower_bound)} | {_fmt(result.releases_outliers.upper_bound)} | {result.releases_outliers.count} | {_fmt(_pct(result.releases_outliers.count, rel.count))}% |",
        f"| `dias_desde_ultimo_push` | {_fmt(result.days_since_push_outliers.lower_bound)} | {_fmt(result.days_since_push_outliers.upper_bound)} | {result.days_since_push_outliers.count} | {_fmt(_pct(result.days_since_push_outliers.count, dps.count))}% |",
        "",
        "## Sanidade da Distribuição",
        "",
        f"- Repositórios com `releases_count = 0`: {result.zero_releases_count} ({_fmt(_pct(result.zero_releases_count, rel.count))}% dos válidos de RQ03)",
        f"- Repositórios com último push muito antigo (>= 10 anos): {result.very_old_push_count} ({_fmt(_pct(result.very_old_push_count, dps.count))}% dos válidos de RQ04)",
        "- Interpretação esperada: RQ03 tende a ser assimétrica (cauda longa), e RQ04 tende a concentrar em baixa defasagem com poucos casos muito antigos.",
        "",
        build_hypothesis_block(),
    ]

    return "\n".join(lines)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Análise exploratória dos campos releases_count (RQ03) e pushed_at (RQ04)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="caminho do markdown de saída (padrão: docs/analises/analise-rq03-rq04.md)",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()

    connection = get_connection()
    try:
        rows = fetch_rows(connection)
    finally:
        connection.close()

    if not rows:
        raise RuntimeError("nenhum repositório encontrado no banco — rode o coletor antes")
    validate_total_rows(len(rows))

    result = run_analysis(rows)
    markdown = render_markdown(result)
    print(markdown)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"\nAnálise salva em {args.output}")


if __name__ == "__main__":
    main()

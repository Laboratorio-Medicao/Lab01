from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from pathlib import Path

from src import storage
from src.metrics import compute_age_years, compute_fork_star_ratio
from src.storage import get_connection

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "analises" / "analise-rq08.md"

STAR_FARMING_AGE_YEARS = 1.5
STAR_FARMING_STARGAZERS = 100_000


@dataclass
class FieldSummary:
    label: str
    n: int
    missing: int
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float
    mean: float
    outliers_low: list
    outliers_high: list

    @property
    def iqr(self) -> float:
        return self.q3 - self.q1

    @property
    def low_fence(self) -> float:
        return self.q1 - 1.5 * self.iqr

    @property
    def high_fence(self) -> float:
        return self.q3 + 1.5 * self.iqr


def fetch_rows(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, name, owner, fork_count, stargazer_count, created_at, collected_at
            FROM {storage.REPOSITORIES_TABLE}
            """
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _quantiles(values: list[float]) -> tuple[float, float, float]:
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, median, q3


def summarize(label: str, entries: list[tuple], total_rows: int) -> FieldSummary:
    """entries: list of (identifier_str, value) with value already non-null."""
    values = [v for _, v in entries]
    missing = total_rows - len(values)
    q1, median, q3 = _quantiles(values)
    iqr = q3 - q1
    low_fence = q1 - 1.5 * iqr
    high_fence = q3 + 1.5 * iqr
    outliers_low = sorted(
        [(ident, v) for ident, v in entries if v < low_fence],
        key=lambda pair: pair[1],
    )
    outliers_high = sorted(
        [(ident, v) for ident, v in entries if v > high_fence],
        key=lambda pair: pair[1],
        reverse=True,
    )
    return FieldSummary(
        label=label,
        n=len(values),
        missing=missing,
        minimum=min(values),
        q1=q1,
        median=median,
        q3=q3,
        maximum=max(values),
        mean=statistics.mean(values),
        outliers_low=outliers_low,
        outliers_high=outliers_high,
    )


def compute_missing_breakdown(rows: list[dict]) -> tuple[int, int, int]:
    """Retorna (fork_count_nulo, stargazer_zero, total_ausentes) — as duas causas
    distintas de `fork_star_ratio = None` documentadas em `compute_fork_star_ratio`."""
    fork_count_null = sum(1 for r in rows if r["fork_count"] is None)
    stargazer_zero = sum(
        1 for r in rows if r["fork_count"] is not None and r["stargazer_count"] == 0
    )
    return fork_count_null, stargazer_zero, fork_count_null + stargazer_zero


def compute_star_farming_comparison(rows: list[dict]) -> dict:
    star_farming_ratios = []
    rest_ratios = []

    for r in rows:
        ratio = compute_fork_star_ratio(r["fork_count"], r["stargazer_count"])
        if ratio is None or r["created_at"] is None or r["collected_at"] is None:
            continue
        age = compute_age_years(r["created_at"], str(r["collected_at"]))
        if age < STAR_FARMING_AGE_YEARS and r["stargazer_count"] > STAR_FARMING_STARGAZERS:
            star_farming_ratios.append(ratio)
        else:
            rest_ratios.append(ratio)

    return {
        "star_farming_n": len(star_farming_ratios),
        "star_farming_median": statistics.median(star_farming_ratios) if star_farming_ratios else None,
        "rest_n": len(rest_ratios),
        "rest_median": statistics.median(rest_ratios) if rest_ratios else None,
    }


def render_field_section(title: str, summary: FieldSummary) -> list[str]:
    lines = [
        f"## {title}\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| N (valores presentes) | {summary.n} |",
        f"| Valores ausentes | {summary.missing} |",
        f"| Mínimo | {summary.minimum:.4f} |",
        f"| 1º quartil (Q1) | {summary.q1:.4f} |",
        f"| Mediana | {summary.median:.4f} |",
        f"| Média | {summary.mean:.4f} |",
        f"| 3º quartil (Q3) | {summary.q3:.4f} |",
        f"| Máximo | {summary.maximum:.4f} |",
        f"| IQR (Q3-Q1) | {summary.iqr:.4f} |",
        "",
        f"**Método de outlier:** regra do IQR (1.5×) — valores abaixo de "
        f"`{summary.low_fence:.4f}` ou acima de `{summary.high_fence:.4f}` são "
        "tratados como atípicos.\n",
        f"- Outliers baixos: {len(summary.outliers_low)}",
        f"- Outliers altos: {len(summary.outliers_high)}",
        "",
    ]
    if summary.outliers_high:
        lines.append("**Top outliers altos (mais forks que estrelas, proporcionalmente):**\n")
        lines.append("| Repositório | `fork_star_ratio` |")
        lines.append("|---|---|")
        for ident, value in summary.outliers_high[:15]:
            lines.append(f"| {ident} | {value:.4f} |")
        lines.append("")
    if summary.outliers_low:
        lines.append("**Outliers baixos (engajamento ativo quase nulo frente às estrelas):**\n")
        lines.append("| Repositório | `fork_star_ratio` |")
        lines.append("|---|---|")
        for ident, value in summary.outliers_low[:15]:
            lines.append(f"| {ident} | {value:.4f} |")
        lines.append("")
    return lines


def render_markdown(
    total_rows: int,
    ratio_summary: FieldSummary,
    fork_count_null: int,
    stargazer_zero: int,
    comparison: dict,
) -> str:
    lines = [
        "# Análise RQ08 (bônus) — Engajamento real: razão forks/estrelas — "
        "amostra de 1.000 repositórios (Sprint S02)\n",
        f"**Total de repositórios na amostra:** {total_rows}\n",
        "**Escopo:** validação estatística de consistência (distribuição, outliers, "
        "valores ausentes) de `fork_star_ratio` sobre a totalidade dos 1.000 "
        "repositórios coletados — distinta da validação cruzada campo-a-campo de "
        "`fork_count` contra a REST API já feita em `docs/validacoes/validacao-rq08.md` "
        "(amostra de 8 repositórios). Ver `docs/metodologia.md`, seção "
        "\"RQ08 (bônus) — Engajamento real: razão forks/estrelas\".\n",
    ]

    lines += render_field_section("`fork_star_ratio` (fork_count / stargazer_count)", ratio_summary)

    lines += [
        "## Valores ausentes — detalhamento por causa\n",
        "`compute_fork_star_ratio` retorna `None` por dois motivos distintos "
        "(`src/metrics.py`):\n",
        "| Causa | Quantidade |",
        "|---|---|",
        f"| `fork_count` ainda não coletado (`NULL`) | {fork_count_null} |",
        f"| `stargazer_count = 0` (razão indefinida) | {stargazer_zero} |",
        f"| **Total de ausentes** | **{fork_count_null + stargazer_zero}** |",
        "",
    ]

    lines += [
        "## Confronto com a hipótese informal (star-farming vs. resto da amostra)\n",
        "**Hipótese registrada em `docs/metodologia.md`:** repositórios no grupo "
        f"suspeito de star-farming (idade < {STAR_FARMING_AGE_YEARS} anos e mais de "
        f"{STAR_FARMING_STARGAZERS:,} estrelas) devem ter `fork_star_ratio` "
        "sistematicamente mais baixo que o resto da amostra.\n",
        "| Grupo | N | Mediana de `fork_star_ratio` |",
        "|---|---|---|",
        f"| Star-farming (idade < {STAR_FARMING_AGE_YEARS}a, > {STAR_FARMING_STARGAZERS:,}⭐) "
        f"| {comparison['star_farming_n']} "
        f"| {comparison['star_farming_median']:.4f} |"
        if comparison["star_farming_median"] is not None
        else f"| Star-farming (idade < {STAR_FARMING_AGE_YEARS}a, > {STAR_FARMING_STARGAZERS:,}⭐) "
        f"| {comparison['star_farming_n']} | — |",
        f"| Resto da amostra | {comparison['rest_n']} "
        f"| {comparison['rest_median']:.4f} |"
        if comparison["rest_median"] is not None
        else f"| Resto da amostra | {comparison['rest_n']} | — |",
        "",
    ]

    if comparison["star_farming_median"] is not None and comparison["rest_median"] is not None:
        sf_median = comparison["star_farming_median"]
        rest_median = comparison["rest_median"]
        if sf_median < rest_median:
            verdict = (
                "**Resultado:** a hipótese se confirma — o grupo suspeito de "
                f"star-farming tem `fork_star_ratio` mediano ({sf_median:.4f}) "
                f"menor que o resto da amostra ({rest_median:.4f}), consistente "
                "com estrelas não orgânicas que não se traduzem em engajamento "
                "ativo (forks)."
            )
        else:
            verdict = (
                "**Resultado:** a hipótese não se confirma nesta amostra — o grupo "
                f"suspeito de star-farming tem `fork_star_ratio` mediano "
                f"({sf_median:.4f}) igual ou maior que o resto da amostra "
                f"({rest_median:.4f}). Isso não invalida o achado de star-farming "
                "em si (RQ01), mas sugere que `fork_star_ratio` sozinho não é um "
                "discriminador forte para esse grupo — merece nota explícita na "
                "discussão hipótese vs. resultado do Relatório Final (RQ08)."
            )
    else:
        verdict = (
            "**Resultado:** amostra insuficiente em um dos grupos para comparar "
            "medianas com confiança."
        )
    lines.append(verdict)
    lines.append("")

    return "\n".join(lines)


def build_arg_parser():
    return argparse.ArgumentParser(
        description="Análise RQ08 (bônus): distribuição, outliers e ausentes de "
        "fork_star_ratio sobre a amostra completa de repositórios."
    )


def main():
    build_arg_parser().parse_args()
    connection = get_connection()
    try:
        rows = fetch_rows(connection)
    finally:
        connection.close()

    if not rows:
        raise RuntimeError("nenhum repositório encontrado — rode o coletor antes")

    total_rows = len(rows)

    ratio_entries = [
        (f"{r['owner']}/{r['name']}", compute_fork_star_ratio(r["fork_count"], r["stargazer_count"]))
        for r in rows
    ]
    ratio_entries = [(label, ratio) for label, ratio in ratio_entries if ratio is not None]

    ratio_summary = summarize("fork_star_ratio", ratio_entries, total_rows)

    fork_count_null, stargazer_zero, _ = compute_missing_breakdown(rows)
    comparison = compute_star_farming_comparison(rows)

    markdown = render_markdown(total_rows, ratio_summary, fork_count_null, stargazer_zero, comparison)
    print(markdown)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    print(f"\nAnálise salva em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

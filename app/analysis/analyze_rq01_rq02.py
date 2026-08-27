from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from pathlib import Path

from src import storage
from src.metrics import compute_age_years
from src.storage import get_connection

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "analises" / "analise-exploratoria-rq01-rq02.md"
)

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
            SELECT id, name, owner, created_at, collected_at, merged_pull_requests,
                   stargazer_count
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
        (ident for ident, v in entries if v < low_fence), key=lambda i: i
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
        outliers_low=[o for o in outliers_low],
        outliers_high=outliers_high,
    )


def compute_star_farming_share(rows: list[dict]) -> tuple[int, int, list[dict]]:
    matches = []
    for row in rows:
        if row["created_at"] is None or row["collected_at"] is None:
            continue
        age = compute_age_years(row["created_at"], str(row["collected_at"]))
        if age < STAR_FARMING_AGE_YEARS and row["stargazer_count"] > STAR_FARMING_STARGAZERS:
            matches.append({**row, "age_years": age})
    matches.sort(key=lambda r: r["stargazer_count"], reverse=True)
    return len(matches), len(rows), matches


def render_field_section(title: str, rq: str, summary: FieldSummary) -> list[str]:
    lines = [
        f"## {title} ({rq})\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| N (valores presentes) | {summary.n} |",
        f"| Valores ausentes | {summary.missing} |",
        f"| Mínimo | {summary.minimum:.2f} |",
        f"| 1º quartil (Q1) | {summary.q1:.2f} |",
        f"| Mediana | {summary.median:.2f} |",
        f"| Média | {summary.mean:.2f} |",
        f"| 3º quartil (Q3) | {summary.q3:.2f} |",
        f"| Máximo | {summary.maximum:.2f} |",
        f"| IQR (Q3-Q1) | {summary.iqr:.2f} |",
        "",
        f"**Método de outlier:** regra do IQR (1.5×) — valores abaixo de "
        f"`{summary.low_fence:.2f}` ou acima de `{summary.high_fence:.2f}` são "
        "tratados como atípicos.\n",
        f"- Outliers baixos: {len(summary.outliers_low)}",
        f"- Outliers altos: {len(summary.outliers_high)}",
        "",
    ]
    if summary.outliers_high:
        lines.append("**Top outliers altos:**\n")
        lines.append("| Repositório | Valor |")
        lines.append("|---|---|")
        for ident, value in summary.outliers_high[:15]:
            lines.append(f"| {ident} | {value:.2f} |")
        lines.append("")
    return lines


def render_markdown(
    total_rows: int,
    age_summary: FieldSummary,
    prs_summary: FieldSummary,
    star_farming_count: int,
    star_farming_total: int,
    star_farming_sample,
) -> str:
    lines = [
        "# Análise exploratória RQ01/RQ02 — amostra de 1.000 repositórios (Sprint S02)\n",
        f"**Total de repositórios na amostra:** {total_rows}\n",
        "**Escopo:** validação estatística de consistência (distribuição, outliers, "
        "valores ausentes) sobre a totalidade dos 1.000 repositórios coletados — "
        "distinta da validação cruzada campo-a-campo contra a REST API já feita em "
        "S01 (`docs/validacoes/validacao-rq01-rq02.md`, amostra de 8 repositórios). Ver "
        "`docs/metodologia.md`, seção \"RQ01 — Idade do repositório\" e "
        "\"RQ02 — Pull requests aceitas\".\n",
    ]
    lines += render_field_section("RQ01 — Idade do repositório (anos)", "created_at", age_summary)
    lines += render_field_section(
        "RQ02 — Pull requests aceitas (merged)", "merged_pull_requests", prs_summary
    )

    pct = (star_farming_count / star_farming_total * 100) if star_farming_total else 0
    lines += [
        "## Achado de star-farming (RQ01) — comparação S01 → S02\n",
        f"Repositórios com idade < {STAR_FARMING_AGE_YEARS} anos e mais de "
        f"{STAR_FARMING_STARGAZERS:,} estrelas: **{star_farming_count} de "
        f"{star_farming_total}** ({pct:.1f}%).\n",
        "Em S01 (amostra de 100), esse padrão apareceu em 16% da amostra "
        "(`docs/metodologia.md`, seção \"Risco de dados\"). "
        + (
            "A proporção se manteve na mesma ordem de grandeza ao expandir para 1.000 "
            "repositórios, o que reforça que o padrão não é um artefato do tamanho "
            "pequeno da amostra original."
            if 10 <= pct <= 22
            else "A proporção mudou de forma perceptível ao expandir para 1.000 "
            "repositórios — merece nota explícita na discussão hipótese vs. resultado "
            "do Relatório Final (RQ01)."
        )
        + "\n",
    ]
    if star_farming_sample:
        lines.append("**Top 10 por estrelas:**\n")
        lines.append("| Repositório | Estrelas | Idade (anos) |")
        lines.append("|---|---|---|")
        for r in star_farming_sample[:10]:
            lines.append(
                f"| {r['owner']}/{r['name']} | {r['stargazer_count']} | {r['age_years']:.2f} |"
            )
        lines.append("")

    lines += [
        "## Hipóteses informais\n",
        "### RQ01 — Idade do repositório\n",
        "**Hipótese:** a maior parte dos repositórios populares acumula estrelas ao "
        "longo de vários anos — a mediana de idade da amostra de 1.000 deve ficar "
        "acima de 3 anos, com uma cauda de repositórios jovens (< 1,5 anos) puxada "
        "principalmente pelo fenômeno de star-farming/hype de IA já documentado em "
        "S01, não pela maioria da amostra.\n",
        "**Justificativa:** popularidade orgânica (uso, indicação, cobertura de "
        "comunidade) é um processo cumulativo; picos de crescimento rápido em poucos "
        "meses são exceção, não regra, mesmo entre os repositórios mais estrelados do "
        "GitHub — achado já registrado em `docs/metodologia.md` para a amostra de "
        "100.\n",
        f"**Métrica relacionada:** `age_years` (`src/metrics.compute_age_years`), "
        "confrontada com a mediana observada nesta análise e, em S03/Relatório "
        "Final, com o percentual de repositórios no grupo de star-farming.\n",
        "### RQ02 — Pull requests aceitas\n",
        "**Hipótese:** a distribuição de `merged_pull_requests` deve ser fortemente "
        "assimétrica à direita (poucos repositórios com dezenas de milhares de PRs "
        "mergeadas, a maioria concentrada em uma faixa muito menor), com uma cauda "
        "de outliers formada por projetos maduros e com grande base de "
        "contribuidores externos (ex.: linguagens/frameworks de uso massivo).\n",
        "**Justificativa:** contribuição via pull request depende de comunidade "
        "ativa de terceiros, que só se forma depois de o projeto já ser conhecido — "
        "repositórios muito jovens (mesmo que populares em estrelas) tendem a ainda "
        "não ter acumulado um volume alto de PRs aceitas, diferente de estrelas, que "
        "podem crescer de forma mais rápida (inclusive artificialmente).\n",
        "**Métrica relacionada:** `merged_pull_requests`, confrontada com a mediana e "
        "os outliers altos identificados nesta análise.\n",
    ]
    return "\n".join(lines)


def build_arg_parser():
    return argparse.ArgumentParser(
        description="Análise exploratória RQ01/RQ02 sobre a amostra completa de repositórios."
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

    age_entries = [
        (f"{r['owner']}/{r['name']}", compute_age_years(r["created_at"], str(r["collected_at"])))
        for r in rows
        if r["created_at"] is not None and r["collected_at"] is not None
    ]
    prs_entries = [
        (f"{r['owner']}/{r['name']}", r["merged_pull_requests"])
        for r in rows
        if r["merged_pull_requests"] is not None
    ]

    age_summary = summarize("age_years", age_entries, total_rows)
    prs_summary = summarize("merged_pull_requests", prs_entries, total_rows)

    star_count, star_total, star_sample = compute_star_farming_share(rows)

    markdown = render_markdown(
        total_rows, age_summary, prs_summary, star_count, star_total, star_sample
    )
    print(markdown)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    print(f"\nAnálise salva em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from src import storage
from src.metrics import compute_closed_issues_ratio
from src.storage import get_connection

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "analise-exploratoria-rq05-rq06.md"
)

_TIOBE_TOP_20 = {
    "Python": 1, "C": 2, "C++": 3, "Java": 4, "C#": 5,
    "JavaScript": 6, "Visual Basic": 7, "SQL": 8, "R": 9, "Rust": 10,
    "Delphi/Object Pascal": 11, "Scratch": 12, "PHP": 13, "Go": 14,
    "Fortran": 15, "Ruby": 16, "Swift": 17, "Perl": 18, "COBOL": 19,
    "Assembly language": 20,
}

_GITHUB_TO_TIOBE = {
    "Assembly": "Assembly language",
}

TIOBE_REFERENCE = "TIOBE Index (agosto de 2026)"


def tiobe_position(github_language: str) -> int | None:
    normalized = _GITHUB_TO_TIOBE.get(github_language, github_language)
    return _TIOBE_TOP_20.get(normalized)


_RQ05_HYPOTHESIS = """\
### Hipótese informal — RQ05

**Fonte de referência:** TIOBE Index (agosto de 2026) — https://www.tiobe.com/tiobe-index/

**Hipótese:** Python e JavaScript devem ocupar as primeiras posições da \
distribuição nos 1.000 repositórios mais populares do GitHub, refletindo \
o domínio dessas linguagens em projetos open-source de alta visibilidade \
(IA/ML, frameworks web, ferramentas de CLI). C e C++ devem aparecer em \
seguida, puxados por projetos de sistemas e kernels históricos com grande \
base de estrelas acumulada ao longo de anos. A maioria das linguagens \
presentes na amostra deve coincidir com o top 20 do TIOBE.

**Justificativa:** o TIOBE Index mede popularidade com base em buscas em \
motores de busca globais; linguagens com maior adoção tendem a dominar \
tanto as buscas quanto os repositórios mais populares do GitHub. A \
exceção esperada é TypeScript, que não aparece no top 20 do TIOBE mas \
tem forte presença em projetos open-source modernos.\
"""

_RQ06_HYPOTHESIS = """\
### Hipótese informal — RQ06

**Hipótese:** a mediana da razão `closed_issues / total_issues` deve \
ficar acima de 0,5 (mais issues fechadas do que abertas), com uma \
distribuição assimétrica à esquerda — a maioria dos repositórios \
populares mantém bom controle do backlog, mas uma cauda de projetos \
muito ativos tem grande número de issues abertas em relação ao fechado.

**Justificativa:** projetos open-source com alta popularidade costumam \
ter mantenedores ativos que fecham issues regularmente, mas à medida que \
o projeto cresce a taxa de abertura de novas issues tende a superar a de \
fechamento, especialmente em projetos com muita adoção recente.\
"""



@dataclass
class LanguageStats:
    distribution: list[tuple[str, int, float]]
    no_language_count: int
    total: int


@dataclass
class RatioStats:
    n: int
    null_count: int
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float
    mean: float
    outliers_high: list[tuple[str, float]] = field(default_factory=list)

    @property
    def iqr(self) -> float:
        return self.q3 - self.q1

    @property
    def high_fence(self) -> float:
        return self.q3 + 1.5 * self.iqr



def fetch_rows(connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT primary_language, open_issues, closed_issues FROM {storage.REPOSITORIES_TABLE}"
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]



def _language_counts(rows: list[dict]) -> Counter:
    return Counter(r["primary_language"] for r in rows if r["primary_language"] is not None)


def _to_distribution(counter: Counter, total: int) -> list[tuple[str, int, float]]:
    return [
        (lang, count, round(count / total * 100, 2))
        for lang, count in counter.most_common()
    ]


def compute_rq05_tiobe_summary(stats: LanguageStats) -> dict:
    in_tiobe = [(lang, count) for lang, count, _ in stats.distribution if tiobe_position(lang)]
    not_in_tiobe = [(lang, count) for lang, count, _ in stats.distribution if not tiobe_position(lang)]
    return {
        "languages_in_tiobe": len(in_tiobe),
        "languages_not_in_tiobe": len(not_in_tiobe),
        "repos_in_tiobe": sum(count for _, count in in_tiobe),
        "repos_not_in_tiobe": sum(count for _, count in not_in_tiobe),
        "top_exceptions": sorted(not_in_tiobe, key=lambda x: x[1], reverse=True),
    }


def compute_language_stats(rows: list[dict]) -> LanguageStats:
    total = len(rows)
    no_language_count = sum(1 for r in rows if r["primary_language"] is None)
    distribution = _to_distribution(_language_counts(rows), total)
    return LanguageStats(distribution=distribution, no_language_count=no_language_count, total=total)



def _extract_ratios(rows: list[dict]) -> tuple[list[tuple[str, float]], int]:
    entries: list[tuple[str, float]] = []
    null_count = 0
    for r in rows:
        ratio = compute_closed_issues_ratio(r["open_issues"], r["closed_issues"])
        if ratio is None:
            null_count += 1
        else:
            label = f"{r.get('owner', '')}/{r.get('name', '')}".strip("/")
            entries.append((label, ratio))
    return entries, null_count


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    if len(values) < 2:
        v = values[0]
        return v, v, v
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, median, q3


def _outliers_high(entries: list[tuple[str, float]], high_fence: float) -> list[tuple[str, float]]:
    return sorted(
        [(label, v) for label, v in entries if v > high_fence],
        key=lambda pair: pair[1],
        reverse=True,
    )


def compute_ratio_stats(rows: list[dict]) -> RatioStats:
    entries, null_count = _extract_ratios(rows)
    values = [v for _, v in entries]
    q1, median, q3 = _quartiles(values)
    high_fence = q3 + 1.5 * (q3 - q1)
    return RatioStats(
        n=len(values),
        null_count=null_count,
        minimum=min(values),
        q1=q1,
        median=median,
        q3=q3,
        maximum=max(values),
        mean=statistics.mean(values),
        outliers_high=_outliers_high(entries, high_fence),
    )



def _rq05_table(stats: LanguageStats) -> str:
    no_lang_pct = round(stats.no_language_count / stats.total * 100, 2) if stats.total else 0
    lines = [
        f"**Total de repositórios:** {stats.total} | "
        f"**Sem linguagem definida:** {stats.no_language_count} ({no_lang_pct}%)\n",
        f"**Referência de popularidade:** {TIOBE_REFERENCE}\n",
        "| Posição | Linguagem | Nº de repos | % da amostra | TIOBE Top 20 |",
        "|---|---|---|---|---|",
    ]
    for i, (lang, count, pct) in enumerate(stats.distribution, 1):
        position = tiobe_position(lang)
        tiobe_col = f"#{position}" if position else "—"
        lines.append(f"| {i} | {lang} | {count} | {pct}% | {tiobe_col} |")
    return "\n".join(lines)


def _rq06_stats_table(stats: RatioStats) -> str:
    lines = [
        f"**N (repositórios com ao menos uma issue):** {stats.n} | "
        f"**Repositórios sem nenhuma issue (ratio = indefinido):** {stats.null_count}\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| N (valores presentes) | {stats.n} |",
        f"| Valores ausentes (zero issues) | {stats.null_count} |",
        f"| Mínimo | {stats.minimum:.4f} |",
        f"| 1º quartil (Q1) | {stats.q1:.4f} |",
        f"| Mediana | {stats.median:.4f} |",
        f"| Média | {stats.mean:.4f} |",
        f"| 3º quartil (Q3) | {stats.q3:.4f} |",
        f"| Máximo | {stats.maximum:.4f} |",
        f"| IQR (Q3-Q1) | {stats.iqr:.4f} |",
        "",
        f"**Método de outlier:** regra do IQR (1.5×) — valores acima de "
        f"`{stats.high_fence:.4f}` são tratados como atípicos.",
        f"- Outliers altos: {len(stats.outliers_high)}",
    ]
    return "\n".join(lines)


def _rq06_outliers_table(stats: RatioStats) -> str:
    if not stats.outliers_high:
        return ""
    lines = [
        "\n**Top outliers altos (ratio próximo de 1.0):**\n",
        "| Repositório | Razão fechadas/total |",
        "|---|---|",
    ]
    for label, value in stats.outliers_high[:15]:
        lines.append(f"| {label} | {value:.4f} |")
    return "\n".join(lines)


def _rq05_analysis(stats: LanguageStats) -> str:
    summary = compute_rq05_tiobe_summary(stats)
    repos_tiobe_pct = round(summary["repos_in_tiobe"] / stats.total * 100, 1)
    repos_no_lang_pct = round(stats.no_language_count / stats.total * 100, 1)
    exceptions = ", ".join(
        f"{lang} ({count} repos)" for lang, count in summary["top_exceptions"][:5]
    )
    return (
        f"Das {len(stats.distribution)} linguagens encontradas, "
        f"**{summary['languages_in_tiobe']} aparecem no top 20 do TIOBE** e "
        f"{summary['languages_not_in_tiobe']} não aparecem. "
        f"Os repositórios que usam uma linguagem do TIOBE top 20 representam "
        f"**{summary['repos_in_tiobe']} repos ({repos_tiobe_pct}% da amostra)**. "
        f"{stats.no_language_count} repos ({repos_no_lang_pct}%) não têm linguagem definida.\n\n"
        f"**Linguagens fora do TIOBE top 20 com mais repos:** {exceptions}."
    )


def render_rq05_section(stats: LanguageStats) -> str:
    return "\n\n".join(filter(None, [
        "## RQ05 — Linguagem primária",
        _rq05_table(stats),
        _rq05_analysis(stats),
        _RQ05_HYPOTHESIS,
    ]))


def render_rq06_section(stats: RatioStats) -> str:
    return "\n\n".join(filter(None, [
        "## RQ06 — Razão de issues fechadas",
        _rq06_stats_table(stats),
        _rq06_outliers_table(stats),
        _RQ06_HYPOTHESIS,
    ]))


def render_markdown(language_stats: LanguageStats, ratio_stats: RatioStats) -> str:
    header = (
        "# Análise exploratória RQ05/RQ06 — amostra de 1.000 repositórios (Sprint S02)\n\n"
        f"**Total de repositórios na amostra:** {language_stats.total}"
    )
    return "\n\n".join([header, render_rq05_section(language_stats), render_rq06_section(ratio_stats)]) + "\n"



def main():
    argparse.ArgumentParser(
        description="Análise exploratória RQ05/RQ06 sobre a amostra completa de repositórios."
    ).parse_args()

    connection = get_connection()
    try:
        rows = fetch_rows(connection)
    finally:
        connection.close()

    if not rows:
        raise RuntimeError("nenhum repositório encontrado — rode o coletor antes")

    language_stats = compute_language_stats(rows)
    ratio_stats = compute_ratio_stats(rows)
    markdown = render_markdown(language_stats, ratio_stats)

    print(markdown)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    print(f"\nAnálise salva em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

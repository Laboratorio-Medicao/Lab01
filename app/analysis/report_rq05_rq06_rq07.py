from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from analysis.analyze_rq05_rq06 import (
    LanguageStats as LangStats0506,
    RatioStats,
    compute_language_stats,
    compute_ratio_stats,
    fetch_rows as fetch_rows_0506,
    tiobe_position,
)
from analysis.analyze_rq07 import (
    LanguageStats as LangStats07,
    compute_language_stats as compute_language_stats_07,
    fetch_all_repos,
)
from src.storage import get_connection

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "report-rq05-rq06-rq07.html"
)

_TIOBE_COLOR = "#1f77b4"
_NON_TIOBE_COLOR = "#ff7f0e"


def build_fig_rq05_languages(stats: LangStats0506) -> go.Figure:
    tiobe_langs, tiobe_counts = [], []
    other_langs, other_counts = [], []

    for lang, count, _ in reversed(stats.distribution):
        if tiobe_position(lang):
            tiobe_langs.append(lang)
            tiobe_counts.append(count)
        else:
            other_langs.append(lang)
            other_counts.append(count)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="No TIOBE Top 20",
        x=tiobe_counts,
        y=tiobe_langs,
        orientation="h",
        marker_color=_TIOBE_COLOR,
    ))
    fig.add_trace(go.Bar(
        name="Fora do TIOBE Top 20",
        x=other_counts,
        y=other_langs,
        orientation="h",
        marker_color=_NON_TIOBE_COLOR,
    ))
    fig.update_layout(
        title="RQ05 — Distribuição de linguagens primárias (1.000 repositórios)",
        xaxis_title="Número de repositórios",
        yaxis_title="Linguagem",
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=700,
    )
    return fig


def build_fig_rq06_histogram(stats: RatioStats, ratios: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=ratios,
        nbinsx=30,
        name="Distribuição",
        marker_color="#1f77b4",
        opacity=0.75,
    ))
    fig.add_vline(
        x=stats.median,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana = {stats.median:.4f}",
        annotation_position="top right",
    )
    fig.update_layout(
        title="RQ06 — Distribuição da razão de issues fechadas",
        xaxis_title="Razão issues fechadas / total",
        yaxis_title="Número de repositórios",
        bargap=0.05,
    )
    return fig


def build_fig_rq06_boxplot(stats: RatioStats) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        q1=[stats.q1],
        median=[stats.median],
        q3=[stats.q3],
        lowerfence=[stats.minimum],
        upperfence=[stats.maximum],
        mean=[stats.mean],
        name="RQ06",
        boxmean=True,
        marker_color="#1f77b4",
    ))
    fig.update_layout(
        title="RQ06 — Box plot da razão de issues fechadas",
        yaxis_title="Razão issues fechadas / total",
        showlegend=False,
    )
    return fig


def build_figs_rq07(stats: list[LangStats07]) -> list[go.Figure]:
    langs = [s.language for s in stats]
    prs = [s.median_prs for s in stats]
    releases = [s.median_releases for s in stats]
    days = [s.median_days_since_push for s in stats]

    configs = [
        ("RQ07 — Mediana de PRs mergeadas por linguagem", "Mediana de PRs mergeadas", prs, "#2ca02c"),
        ("RQ07 — Mediana de releases por linguagem", "Mediana de releases", releases, "#9467bd"),
        ("RQ07 — Mediana de dias desde último push por linguagem", "Dias desde último push", days, "#d62728"),
    ]

    figs = []
    for title, yaxis, values, color in configs:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=langs, y=values, marker_color=color))
        fig.update_layout(
            title=title,
            xaxis_title="Linguagem (ordenada por nº de repos)",
            yaxis_title=yaxis,
            showlegend=False,
        )
        figs.append(fig)
    return figs


def _extract_ratios_list(rows: list[dict]) -> list[float]:
    from src.metrics import compute_closed_issues_ratio
    result = []
    for r in rows:
        ratio = compute_closed_issues_ratio(r["open_issues"], r["closed_issues"])
        if ratio is not None:
            result.append(ratio)
    return result


_SECTION_TEMPLATE = """\
<section style="margin-bottom:48px">
  <h2 style="font-family:sans-serif">{title}</h2>
  <p style="font-family:sans-serif;max-width:800px">{body}</p>
  {chart}
</section>"""

_RQ05_BODY = (
    "Distribuição das linguagens primárias nos 1.000 repositórios mais populares do GitHub. "
    "Barras azuis representam linguagens presentes no TIOBE Top 20 (agosto 2026); "
    "laranja indica linguagens fora do ranking. "
    "Python lidera com ampla margem, seguido de TypeScript — que não aparece no TIOBE, "
    "mas domina projetos open-source modernos."
)

_RQ06_HIST_BODY = (
    "Histograma da razão <em>issues fechadas / total de issues</em>. "
    "A linha tracejada vermelha marca a mediana. "
    "A distribuição é fortemente assimétrica à esquerda: "
    "a maioria dos repositórios populares mantém alta taxa de resolução de issues."
)

_RQ06_BOX_BODY = (
    "Box plot resumindo Q1, mediana, Q3 e amplitude da distribuição da razão de issues fechadas. "
    "Não há outliers altos nesta amostra (todos os valores ficam abaixo do limite IQR×1.5)."
)

_RQ07_BODIES = [
    (
        "Mediana de PRs mergeadas por linguagem (top 10 por nº de repos). "
        "Linguagens com ecossistemas maduros de contribuição externa (TypeScript, Rust, Go) "
        "concentram mais PRs por repositório."
    ),
    (
        "Mediana de releases por repositório por linguagem. "
        "Go e TypeScript lideram em número de releases formais, enquanto "
        "Jupyter Notebook apresenta mediana zero — projetos de notebooks raramente fazem releases."
    ),
    (
        "Mediana de dias desde o último push por linguagem. "
        "Valores menores indicam repositórios mais ativos. "
        "Rust, Go e TypeScript apresentam os menores valores (repositórios atualizados quase diariamente)."
    ),
]


def _fig_to_div(fig: go.Figure) -> str:
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def render_html(
    lang_stats: LangStats0506,
    ratio_stats: RatioStats,
    ratios: list[float],
    rq07_stats: list[LangStats07],
) -> str:
    fig_rq05 = build_fig_rq05_languages(lang_stats)
    fig_rq06_hist = build_fig_rq06_histogram(ratio_stats, ratios)
    fig_rq06_box = build_fig_rq06_boxplot(ratio_stats)
    figs_rq07 = build_figs_rq07(rq07_stats)

    sections = []
    sections.append(_SECTION_TEMPLATE.format(
        title="RQ05 — Linguagem primária",
        body=_RQ05_BODY,
        chart=_fig_to_div(fig_rq05),
    ))
    sections.append(_SECTION_TEMPLATE.format(
        title="RQ06 — Razão de issues fechadas (histograma)",
        body=_RQ06_HIST_BODY,
        chart=_fig_to_div(fig_rq06_hist),
    ))
    sections.append(_SECTION_TEMPLATE.format(
        title="RQ06 — Razão de issues fechadas (box plot)",
        body=_RQ06_BOX_BODY,
        chart=_fig_to_div(fig_rq06_box),
    ))
    for fig, body in zip(figs_rq07, _RQ07_BODIES):
        sections.append(_SECTION_TEMPLATE.format(
            title="RQ07 — Segmentação por linguagem",
            body=body,
            chart=_fig_to_div(fig),
        ))

    plotly_cdn = (
        '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>'
    )
    body_content = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatório RQ05 / RQ06 / RQ07</title>
  {plotly_cdn}
  <style>
    body {{ font-family: sans-serif; max-width: 1100px; margin: 0 auto; padding: 32px 16px; }}
    h1 {{ color: #222; }}
  </style>
</head>
<body>
  <h1>Relatório de Análise — RQ05, RQ06 e RQ07</h1>
  <p>Sprint S03 — 1.000 repositórios mais populares do GitHub</p>
  {body_content}
</body>
</html>"""


def main() -> None:
    import argparse
    from datetime import datetime, timezone

    argparse.ArgumentParser(
        description="Gera relatório HTML com visualizações RQ05/RQ06/RQ07."
    ).parse_args()

    connection = get_connection()
    reference_date = datetime.now(tz=timezone.utc)
    try:
        rows_0506 = fetch_rows_0506(connection)
        rows_07 = fetch_all_repos(connection)
    finally:
        connection.close()

    if not rows_0506:
        raise RuntimeError("nenhum repositório encontrado — rode o coletor antes")

    lang_stats = compute_language_stats(rows_0506)
    ratio_stats = compute_ratio_stats(rows_0506)
    ratios = _extract_ratios_list(rows_0506)

    from analysis.analyze_rq07 import DEFAULT_MIN_REPOS, DEFAULT_TOP_LANGUAGES
    rq07_stats = compute_language_stats_07(
        rows_07, top_n=DEFAULT_TOP_LANGUAGES, min_repos=DEFAULT_MIN_REPOS,
        reference_date=reference_date,
    )

    html = render_html(lang_stats, ratio_stats, ratios, rq07_stats)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Relatório salvo em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

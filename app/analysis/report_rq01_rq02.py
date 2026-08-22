from __future__ import annotations

import math
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from analysis.analyze_rq01_rq02 import (
    FieldSummary,
    STAR_FARMING_AGE_YEARS,
    STAR_FARMING_STARGAZERS,
    fetch_rows,
    summarize,
)
from src.metrics import compute_age_years
from src.storage import get_connection

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "report-rq01-rq02.html"
)

_RQ01_COLOR = "#1f77b4"
_RQ02_COLOR = "#2ca02c"
_FARMING_COLOR = "#d62728"


def build_fig_rq01_histogram(summary: FieldSummary, ages: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=ages,
        nbinsx=30,
        name="Distribuição",
        marker_color=_RQ01_COLOR,
        opacity=0.75,
    ))
    fig.add_vline(
        x=summary.median,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana = {summary.median:.2f} anos",
        annotation_position="top right",
    )
    fig.update_layout(
        title="RQ01 — Distribuição da idade dos repositórios",
        xaxis_title="Idade (anos)",
        yaxis_title="Número de repositórios",
        bargap=0.05,
    )
    return fig


def build_fig_rq01_boxplot(summary: FieldSummary) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        q1=[summary.q1],
        median=[summary.median],
        q3=[summary.q3],
        lowerfence=[summary.minimum],
        upperfence=[summary.maximum],
        mean=[summary.mean],
        name="RQ01",
        boxmean=True,
        marker_color=_RQ01_COLOR,
    ))
    fig.update_layout(
        title="RQ01 — Box plot da idade dos repositórios",
        yaxis_title="Idade (anos)",
        showlegend=False,
    )
    return fig


def build_fig_rq02_histogram(summary: FieldSummary, prs: list[float]) -> go.Figure:
    log_prs = [math.log10(v + 1) for v in prs]
    log_median = math.log10(summary.median + 1)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=log_prs,
        nbinsx=40,
        name="Distribuição",
        marker_color=_RQ02_COLOR,
        opacity=0.75,
    ))
    fig.add_vline(
        x=log_median,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana = {summary.median:.0f} PRs",
        annotation_position="top right",
    )
    fig.update_layout(
        title="RQ02 — Distribuição de pull requests aceitas (escala log10)",
        xaxis_title="log10(PRs aceitas + 1)",
        yaxis_title="Número de repositórios",
        bargap=0.05,
    )
    return fig


def build_fig_rq02_boxplot(summary: FieldSummary) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        q1=[summary.q1],
        median=[summary.median],
        q3=[summary.q3],
        lowerfence=[summary.minimum],
        upperfence=[summary.maximum],
        mean=[summary.mean],
        name="RQ02",
        boxmean=True,
        marker_color=_RQ02_COLOR,
    ))
    fig.update_layout(
        title="RQ02 — Box plot de pull requests aceitas",
        yaxis_title="PRs aceitas (merged)",
        showlegend=False,
    )
    return fig


def build_fig_star_farming_scatter(
    points: list[tuple[str, float, int]],
    age_threshold: float = STAR_FARMING_AGE_YEARS,
    star_threshold: int = STAR_FARMING_STARGAZERS,
) -> go.Figure:
    normal_x, normal_y, normal_text = [], [], []
    farming_x, farming_y, farming_text = [], [], []
    for label, age, stars in points:
        if age < age_threshold and stars > star_threshold:
            farming_x.append(age)
            farming_y.append(stars)
            farming_text.append(label)
        else:
            normal_x.append(age)
            normal_y.append(stars)
            normal_text.append(label)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=normal_x,
        y=normal_y,
        mode="markers",
        name="Demais repositórios",
        marker=dict(color=_RQ01_COLOR, size=6, opacity=0.5),
        text=normal_text,
    ))
    fig.add_trace(go.Scatter(
        x=farming_x,
        y=farming_y,
        mode="markers",
        name=f"Idade < {age_threshold}a e > {star_threshold:,} estrelas",
        marker=dict(color=_FARMING_COLOR, size=8),
        text=farming_text,
    ))
    fig.update_layout(
        title="RQ01 — Idade vs. estrelas (destaque star-farming)",
        xaxis_title="Idade (anos)",
        yaxis_title="Estrelas",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def _extract_scatter_points(rows: list[dict]) -> list[tuple[str, float, int]]:
    points = []
    for r in rows:
        if r["created_at"] is None or r["collected_at"] is None:
            continue
        age = compute_age_years(r["created_at"], str(r["collected_at"]))
        points.append((f"{r['owner']}/{r['name']}", age, r["stargazer_count"]))
    return points


_SECTION_TEMPLATE = """\
<section style="margin-bottom:48px">
  <h2 style="font-family:sans-serif">{title}</h2>
  <p style="font-family:sans-serif;max-width:800px">{body}</p>
  {chart}
</section>"""

_RQ01_HIST_BODY = (
    "Histograma da idade dos repositórios, em anos, calculada a partir da data de "
    "criação. A linha tracejada vermelha marca a mediana. A distribuição concentra a "
    "maior parte dos repositórios entre 3 e 11 anos, com uma cauda de repositórios "
    "jovens puxada pelo fenômeno de star-farming/hype (ver gráfico de dispersão abaixo)."
)

_RQ01_BOX_BODY = (
    "Box plot resumindo Q1, mediana, Q3 e amplitude da distribuição de idade. Não há "
    "outliers detectados pela regra do IQR (1.5×) nesta amostra."
)

_RQ01_SCATTER_BODY = (
    "Dispersão de idade (anos) vs. estrelas para os 1.000 repositórios. Em vermelho, os "
    "repositórios com menos de 1,5 ano e mais de 100.000 estrelas — o grupo de "
    "star-farming/hype identificado na análise exploratória de S02."
)

_RQ02_HIST_BODY = (
    "Histograma de pull requests aceitas (merged), em escala log10, devido à forte "
    "assimetria da distribuição. A linha tracejada vermelha marca a mediana (em valor "
    "absoluto de PRs). A maioria dos repositórios concentra-se em valores baixos, com "
    "uma cauda longa de projetos maduros com dezenas de milhares de PRs mergeadas."
)

_RQ02_BOX_BODY = (
    "Box plot de PRs aceitas em escala linear. A distância entre a mediana e o "
    "máximo evidencia a forte assimetria à direita e os 123 outliers altos "
    "identificados pela regra do IQR (1.5×)."
)


def _fig_to_div(fig: go.Figure) -> str:
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def render_html(
    age_summary: FieldSummary,
    prs_summary: FieldSummary,
    ages: list[float],
    prs: list[float],
    scatter_points: list[tuple[str, float, int]],
) -> str:
    fig_rq01_hist = build_fig_rq01_histogram(age_summary, ages)
    fig_rq01_box = build_fig_rq01_boxplot(age_summary)
    fig_rq01_scatter = build_fig_star_farming_scatter(scatter_points)
    fig_rq02_hist = build_fig_rq02_histogram(prs_summary, prs)
    fig_rq02_box = build_fig_rq02_boxplot(prs_summary)

    sections = [
        _SECTION_TEMPLATE.format(
            title="RQ01 — Idade do repositório (histograma)",
            body=_RQ01_HIST_BODY,
            chart=_fig_to_div(fig_rq01_hist),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ01 — Idade do repositório (box plot)",
            body=_RQ01_BOX_BODY,
            chart=_fig_to_div(fig_rq01_box),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ01 — Idade vs. estrelas",
            body=_RQ01_SCATTER_BODY,
            chart=_fig_to_div(fig_rq01_scatter),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ02 — Pull requests aceitas (histograma)",
            body=_RQ02_HIST_BODY,
            chart=_fig_to_div(fig_rq02_hist),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ02 — Pull requests aceitas (box plot)",
            body=_RQ02_BOX_BODY,
            chart=_fig_to_div(fig_rq02_box),
        ),
    ]

    plotly_cdn = (
        '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>'
    )
    body_content = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatório RQ01 / RQ02</title>
  {plotly_cdn}
  <style>
    body {{ font-family: sans-serif; max-width: 1100px; margin: 0 auto; padding: 32px 16px; }}
    h1 {{ color: #222; }}
  </style>
</head>
<body>
  <h1>Relatório de Análise — RQ01 e RQ02</h1>
  <p>Sprint S03 — 1.000 repositórios mais populares do GitHub</p>
  {body_content}
</body>
</html>"""


def main() -> None:
    import argparse

    argparse.ArgumentParser(
        description="Gera relatório HTML com visualizações RQ01/RQ02."
    ).parse_args()

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

    ages = [v for _, v in age_entries]
    prs = [v for _, v in prs_entries]
    scatter_points = _extract_scatter_points(rows)

    html = render_html(age_summary, prs_summary, ages, prs, scatter_points)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Relatório salvo em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

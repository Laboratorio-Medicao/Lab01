from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from analysis.analyze_rq08 import (
    FieldSummary,
    STAR_FARMING_AGE_YEARS,
    STAR_FARMING_STARGAZERS,
    fetch_rows,
    summarize,
)
from src.metrics import compute_age_years, compute_fork_star_ratio
from src.storage import get_connection

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "visualizacoes" / "report-rq08.html"

_RATIO_COLOR = "#9467bd"
_FARMING_COLOR = "#d62728"
_REST_COLOR = "#1f77b4"


def build_fig_rq08_histogram(summary: FieldSummary, ratios: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=ratios,
        nbinsx=30,
        name="Distribuição",
        marker_color=_RATIO_COLOR,
        opacity=0.75,
    ))
    fig.add_vline(
        x=summary.median,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana = {summary.median:.4f}",
        annotation_position="top right",
    )
    fig.update_layout(
        title="RQ08 — Distribuição de fork_star_ratio (bônus)",
        xaxis_title="fork_star_ratio (fork_count / stargazer_count)",
        yaxis_title="Número de repositórios",
        bargap=0.05,
    )
    return fig


def build_fig_rq08_boxplot(summary: FieldSummary) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        q1=[summary.q1],
        median=[summary.median],
        q3=[summary.q3],
        lowerfence=[summary.minimum],
        upperfence=[summary.maximum],
        mean=[summary.mean],
        name="RQ08",
        boxmean=True,
        marker_color=_RATIO_COLOR,
    ))
    fig.update_layout(
        title="RQ08 — Box plot de fork_star_ratio (bônus)",
        yaxis_title="fork_star_ratio",
        showlegend=False,
    )
    return fig


def build_fig_rq08_group_comparison(
    star_farming_ratios: list[float], rest_ratios: list[float]
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        y=star_farming_ratios,
        name=f"Star-farming (< {STAR_FARMING_AGE_YEARS}a, > {STAR_FARMING_STARGAZERS:,}⭐)",
        marker_color=_FARMING_COLOR,
        boxmean=True,
    ))
    fig.add_trace(go.Box(
        y=rest_ratios,
        name="Resto da amostra",
        marker_color=_REST_COLOR,
        boxmean=True,
    ))
    fig.update_layout(
        title="RQ08 — fork_star_ratio: star-farming vs. resto da amostra",
        yaxis_title="fork_star_ratio",
        showlegend=True,
    )
    return fig


def _extract_group_ratios(rows: list[dict]) -> tuple[list[float], list[float]]:
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
    return star_farming_ratios, rest_ratios


_SECTION_TEMPLATE = """\
<section style="margin-bottom:48px">
  <h2 style="font-family:sans-serif">{title}</h2>
  <p style="font-family:sans-serif;max-width:800px">{body}</p>
  {chart}
</section>"""

_RQ08_HIST_BODY = (
    "Histograma de <code>fork_star_ratio</code> (fork_count / stargazer_count), métrica "
    "bônus de engajamento real. A linha tracejada vermelha marca a mediana. A distribuição "
    "é assimétrica à direita, com uma cauda de repositórios em que forks superam estrelas "
    "proporcionalmente (ex.: repositórios de tutoriais/exercícios)."
)

_RQ08_BOX_BODY = (
    "Box plot resumindo Q1, mediana, Q3 e amplitude de <code>fork_star_ratio</code>. "
    "53 outliers altos foram identificados pela regra do IQR (1.5×), sem outliers baixos."
)

_RQ08_GROUP_BODY = (
    "Comparação de <code>fork_star_ratio</code> entre o grupo suspeito de star-farming "
    "(RQ01: idade < 1,5 ano e mais de 100.000 estrelas) e o resto da amostra. A hipótese "
    "de que estrelas não-orgânicas se traduziriam em razão fork/estrela mais baixa não se "
    "confirma nesta amostra — as medianas dos dois grupos são próximas."
)


def _fig_to_div(fig: go.Figure) -> str:
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def render_html(
    summary: FieldSummary,
    ratios: list[float],
    star_farming_ratios: list[float],
    rest_ratios: list[float],
) -> str:
    fig_hist = build_fig_rq08_histogram(summary, ratios)
    fig_box = build_fig_rq08_boxplot(summary)
    fig_group = build_fig_rq08_group_comparison(star_farming_ratios, rest_ratios)

    sections = [
        _SECTION_TEMPLATE.format(
            title="RQ08 — fork_star_ratio (histograma)",
            body=_RQ08_HIST_BODY,
            chart=_fig_to_div(fig_hist),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ08 — fork_star_ratio (box plot)",
            body=_RQ08_BOX_BODY,
            chart=_fig_to_div(fig_box),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ08 — Star-farming vs. resto da amostra",
            body=_RQ08_GROUP_BODY,
            chart=_fig_to_div(fig_group),
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
  <title>Relatório RQ08 (bônus)</title>
  {plotly_cdn}
  <style>
    body {{ font-family: sans-serif; max-width: 1100px; margin: 0 auto; padding: 32px 16px; }}
    h1 {{ color: #222; }}
  </style>
</head>
<body>
  <h1>Relatório de Análise — RQ08 (bônus)</h1>
  <p>Sprint S03 — 1.000 repositórios mais populares do GitHub</p>
  {body_content}
</body>
</html>"""


def main() -> None:
    import argparse

    argparse.ArgumentParser(
        description="Gera relatório HTML com visualizações RQ08 (bônus)."
    ).parse_args()

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

    summary = summarize("fork_star_ratio", ratio_entries, total_rows)
    ratios = [v for _, v in ratio_entries]
    star_farming_ratios, rest_ratios = _extract_group_ratios(rows)

    html = render_html(summary, ratios, star_farming_ratios, rest_ratios)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Relatório salvo em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

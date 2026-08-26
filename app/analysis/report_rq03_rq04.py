from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from analysis.analyze_rq03_rq04 import (
    RQ03RQ04Analysis,
    fetch_rows as fetch_analysis_rows,
    parse_iso_utc,
    run_analysis,
    validate_total_rows,
)
from src import storage
from src.storage import get_connection

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "report-rq03-rq04.html"

_RELEASES_COLOR = "#1f77b4"
_DAYS_COLOR = "#ff7f0e"
_RELATION_COLOR = "#2ca02c"


def _log_values(values: list[float]) -> list[float]:
    import math

    return [math.log10(value + 1) for value in values]


def build_fig_rq03_histogram(summary, releases: list[float]) -> go.Figure:
    log_releases = _log_values(releases)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=log_releases,
        nbinsx=35,
        name="Distribuição",
        marker_color=_RELEASES_COLOR,
        opacity=0.75,
    ))
    fig.add_vline(
        x=_log_values([summary.median])[0],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana = {summary.median:.2f} releases",
        annotation_position="top right",
    )
    fig.update_layout(
        title="RQ03 — Distribuição do total de releases",
        xaxis_title="log10(releases + 1)",
        yaxis_title="Número de repositórios",
        bargap=0.05,
    )
    return fig


def build_fig_rq03_boxplot(summary) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        q1=[summary.q1],
        median=[summary.median],
        q3=[summary.q3],
        lowerfence=[summary.min_value],
        upperfence=[summary.max_value],
        mean=[summary.mean],
        name="RQ03",
        boxmean=True,
        marker_color=_RELEASES_COLOR,
    ))
    fig.update_layout(
        title="RQ03 — Box plot do total de releases",
        yaxis_title="Total de releases",
        showlegend=False,
    )
    return fig


def build_fig_rq04_histogram(summary, days_since_push: list[float]) -> go.Figure:
    log_days = _log_values(days_since_push)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=log_days,
        nbinsx=35,
        name="Distribuição",
        marker_color=_DAYS_COLOR,
        opacity=0.75,
    ))
    fig.add_vline(
        x=_log_values([summary.median])[0],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana = {summary.median:.2f} dias",
        annotation_position="top right",
    )
    fig.update_layout(
        title="RQ04 — Distribuição do tempo desde o último push",
        xaxis_title="log10(dias desde último push + 1)",
        yaxis_title="Número de repositórios",
        bargap=0.05,
    )
    return fig


def build_fig_rq04_boxplot(summary) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Box(
        q1=[summary.q1],
        median=[summary.median],
        q3=[summary.q3],
        lowerfence=[summary.min_value],
        upperfence=[summary.max_value],
        mean=[summary.mean],
        name="RQ04",
        boxmean=True,
        marker_color=_DAYS_COLOR,
    ))
    fig.update_layout(
        title="RQ04 — Box plot dos dias desde o último push",
        yaxis_title="Dias desde o último push",
        showlegend=False,
    )
    return fig


def build_fig_rq03_rq04_scatter(
    points: list[tuple[str, float, float]],
) -> go.Figure:
    labels = [point[0] for point in points]
    releases = [point[1] for point in points]
    days = [point[2] for point in points]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=_log_values(releases),
        y=_log_values(days),
        mode="markers",
        name="Repositórios",
        marker=dict(color=_RELATION_COLOR, size=7, opacity=0.55),
        text=labels,
        customdata=list(zip(releases, days)),
        hovertemplate=(
            "%{text}<br>releases: %{customdata[0]}"
            "<br>dias desde último push: %{customdata[1]:.2f}<extra></extra>"
        ),
    ))
    fig.update_layout(
        title="RQ03 × RQ04 — Releases e tempo desde o último push",
        xaxis_title="log10(releases + 1)",
        yaxis_title="log10(dias desde último push + 1)",
        showlegend=False,
    )
    return fig


def _valid_values(rows: list[dict], reference_date: datetime) -> tuple[list[float], list[float]]:
    releases = []
    days_since_push = []
    for row in rows:
        if row["releases_count"] is not None:
            releases.append(float(row["releases_count"]))
        pushed_at = row["pushed_at"]
        if pushed_at is None or str(pushed_at).strip() == "":
            continue
        try:
            pushed_at_dt = parse_iso_utc(str(pushed_at))
        except ValueError:
            continue
        delta_days = (reference_date - pushed_at_dt).total_seconds() / 86400
        if delta_days >= 0:
            days_since_push.append(delta_days)
    return releases, days_since_push


def _scatter_points(rows: list[dict], reference_date: datetime) -> list[tuple[str, float, float]]:
    points = []
    for row in rows:
        if row["releases_count"] is None:
            continue
        pushed_at = row["pushed_at"]
        if pushed_at is None or str(pushed_at).strip() == "":
            continue
        try:
            pushed_at_dt = parse_iso_utc(str(pushed_at))
        except ValueError:
            continue
        delta_days = (reference_date - pushed_at_dt).total_seconds() / 86400
        if delta_days < 0:
            continue
        points.append((
            f"{row['owner']}/{row['name']}",
            float(row["releases_count"]),
            delta_days,
        ))
    return points


_SECTION_TEMPLATE = """\\
<section style="margin-bottom:48px">
  <h2 style="font-family:sans-serif">{title}</h2>
  <p style="font-family:sans-serif;max-width:800px">{body}</p>
  {chart}
</section>"""


def _fig_to_div(fig: go.Figure) -> str:
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def render_html(
    result: RQ03RQ04Analysis,
    releases: list[float],
    days_since_push: list[float],
    scatter_points: list[tuple[str, float, float]],
) -> str:
    sections = [
        _SECTION_TEMPLATE.format(
            title="RQ03 — Total de releases (histograma)",
            body="Histograma em escala log10(releases + 1), adequado para visualizar a assimetria e a cauda longa da quantidade de releases. A linha tracejada marca a mediana.",
            chart=_fig_to_div(build_fig_rq03_histogram(result.releases_summary, releases)),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ03 — Total de releases (box plot)",
            body="Box plot do total de releases em escala original, resumindo quartis, média, amplitude e a dispersão da métrica.",
            chart=_fig_to_div(build_fig_rq03_boxplot(result.releases_summary)),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ04 — Dias desde o último push (histograma)",
            body="Histograma em escala log10(dias + 1), que permite observar simultaneamente a concentração de atualizações recentes e a cauda de repositórios menos ativos.",
            chart=_fig_to_div(build_fig_rq04_histogram(result.days_since_push_summary, days_since_push)),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ04 — Dias desde o último push (box plot)",
            body="Box plot dos dias desde o último push em escala original, destacando a mediana, os quartis e os valores atípicos.",
            chart=_fig_to_div(build_fig_rq04_boxplot(result.days_since_push_summary)),
        ),
        _SECTION_TEMPLATE.format(
            title="RQ03 × RQ04 — Relação entre releases e atualização",
            body="Gráfico de dispersão das duas métricas em escala logarítmica. Cada ponto mostra o repositório no tooltip, permitindo investigar se maior quantidade de releases acompanha atualização mais recente.",
            chart=_fig_to_div(build_fig_rq03_rq04_scatter(scatter_points)),
        ),
    ]
    plotly_cdn = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>'
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatório RQ03 / RQ04</title>
  {plotly_cdn}
  <style>
    body {{ font-family: sans-serif; max-width: 1100px; margin: 0 auto; padding: 32px 16px; }}
    h1 {{ color: #222; }}
  </style>
</head>
<body>
  <h1>Relatório de Análise — RQ03 e RQ04</h1>
  <p>Sprint S03 — 1.000 repositórios mais populares do GitHub</p>
  {"\\n".join(sections)}
</body>
</html>"""


def _fetch_report_rows(connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT owner, name, releases_count, pushed_at FROM {storage.REPOSITORIES_TABLE}"
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera relatório HTML com visualizações RQ03/RQ04."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="caminho do HTML de saída (padrão: docs/report-rq03-rq04.html)",
    )
    args = parser.parse_args()

    reference_date = datetime.now(tz=timezone.utc)
    connection = get_connection()
    try:
        rows = _fetch_report_rows(connection)
        analysis_rows = fetch_analysis_rows(connection)
    finally:
        connection.close()

    if not rows:
        raise RuntimeError("nenhum repositório encontrado — rode o coletor antes")
    validate_total_rows(len(rows))

    result = run_analysis(analysis_rows, reference_date)
    releases, days_since_push = _valid_values(rows, reference_date)
    points = _scatter_points(rows, reference_date)
    html = render_html(result, releases, days_since_push, points)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Relatório salvo em {args.output}")


if __name__ == "__main__":
    main()

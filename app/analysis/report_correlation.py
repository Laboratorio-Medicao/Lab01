from __future__ import annotations

import argparse
import csv
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from analysis.correlation import (
    METRIC_LABELS,
    CorrelationResult,
    build_metric_values,
    compute_correlations,
    correlation_pairs,
)
from src import storage
from src.storage import get_connection

OUTPUT_MARKDOWN = Path(__file__).resolve().parent.parent.parent / "docs" / "analises" / "analise-correlacao.md"
OUTPUT_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "visualizacoes" / "report-correlacao.html"
OUTPUT_SPEARMAN_CSV = Path(__file__).resolve().parent.parent.parent / "docs" / "dados" / "correlacao-spearman.csv"
OUTPUT_PEARSON_CSV = Path(__file__).resolve().parent.parent.parent / "docs" / "dados" / "correlacao-pearson.csv"


def build_heatmap(result: CorrelationResult, method: str = "spearman") -> go.Figure:
    matrix = result.spearman if method == "spearman" else result.pearson
    title = "Spearman" if method == "spearman" else "Pearson"
    labels = [METRIC_LABELS.get(metric, metric) for metric in result.metrics]
    text = [["" if value is None else f"{value:.2f}" for value in row] for row in matrix]
    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=labels,
        y=labels,
        zmin=-1,
        zmax=1,
        colorscale="RdBu",
        reversescale=True,
        text=text,
        texttemplate="%{text}",
        colorbar_title="r",
        hovertemplate="%{y} × %{x}<br>Correlação: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Matriz de correlação — {title}",
        xaxis_title="Métrica",
        yaxis_title="Métrica",
        height=850,
        margin=dict(l=170, r=40, t=80, b=170),
    )
    return fig


def _matrix_csv(result: CorrelationResult, method: str) -> str:
    matrix = result.spearman if method == "spearman" else result.pearson
    lines = []
    labels = [METRIC_LABELS.get(metric, metric) for metric in result.metrics]
    lines.append(",".join(["metrica", *result.metrics]))
    for metric, row in zip(result.metrics, matrix):
        formatted = ["" if value is None else f"{value:.6f}" for value in row]
        lines.append(",".join([metric, *formatted]))
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, result: CorrelationResult, method: str) -> None:
    path.write_text(_matrix_csv(result, method), encoding="utf-8")


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def render_markdown(result: CorrelationResult) -> str:
    pairs = correlation_pairs(result, "spearman")[:10]
    lines = [
        "# Matriz de correlação global",
        "",
        "Esta análise considera as métricas numéricas coletadas e as métricas derivadas de datas e razões. A matriz principal usa correlação de Spearman; Pearson é apresentada para comparação.",
        "",
        "## Métricas",
        "",
        " | ".join(["Métrica", "Descrição"]),
        "|---|---|",
    ]
    lines.extend(f"| `{metric}` | {METRIC_LABELS.get(metric, metric)} |" for metric in result.metrics)
    lines.extend(["", "## Pares com maior correlação absoluta (Spearman)", "", "| Métrica A | Métrica B | ρ | N |", "|---|---:|---:|---:|"])
    lines.extend(
        f"| `{first}` | `{second}` | {_fmt(coefficient)} | {count} |"
        for first, second, coefficient, count in pairs
    )
    lines.extend([
        "",
        "## Interpretação",
        "",
        "- Correlação positiva indica que as métricas tendem a crescer juntas; correlação negativa indica movimentos opostos.",
        "- Spearman é o resultado principal porque é menos sensível à assimetria e aos outliers presentes nas contagens do GitHub.",
        "- A correlação não implica causalidade. Métricas derivadas de outras, como `issues_total` e `fork_star_ratio`, podem produzir relações matematicamente esperadas.",
        "- O valor de N pode variar por par porque os cálculos usam observações válidas para as duas métricas comparadas.",
    ])
    return "\n".join(lines) + "\n"


def render_html(result: CorrelationResult) -> str:
    spearman = pio.to_html(build_heatmap(result, "spearman"), include_plotlyjs=False, full_html=False)
    pearson = pio.to_html(build_heatmap(result, "pearson"), include_plotlyjs=False, full_html=False)
    pairs = correlation_pairs(result, "spearman")[:10]
    rows = "".join(
        f"<tr><td>{METRIC_LABELS.get(first, first)}</td><td>{METRIC_LABELS.get(second, second)}</td><td>{coefficient:.3f}</td><td>{count}</td></tr>"
        for first, second, coefficient, count in pairs
    )
    plotly_cdn = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>'
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matriz de correlação global</title>
  {plotly_cdn}
  <style>
    body {{ font-family: sans-serif; max-width: 1200px; margin: 0 auto; padding: 32px 16px; color: #222; }}
    section {{ margin-bottom: 48px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 760px; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
  <h1>Matriz de correlação global</h1>
  <p>Correlação entre métricas coletadas e derivadas dos 1.000 repositórios.</p>
  <section><h2>Spearman</h2><p>Resultado principal, baseado nos ranks e mais robusto para distribuições assimétricas.</p>{spearman}</section>
  <section><h2>Pearson</h2><p>Comparação baseada em relações lineares entre os valores originais.</p>{pearson}</section>
  <section><h2>Maiores correlações absolutas</h2><table><thead><tr><th>Métrica A</th><th>Métrica B</th><th>ρ Spearman</th><th>N</th></tr></thead><tbody>{rows}</tbody></table></section>
</body>
</html>"""


def _fetch_rows(connection) -> list[dict]:
    columns = (
        "stargazer_count, fork_count, created_at, pushed_at, is_fork, is_archived, "
        "merged_pull_requests, releases_count, open_issues, closed_issues, collected_at"
    )
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {columns} FROM {storage.REPOSITORIES_TABLE}")
        names = [description[0] for description in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera matriz de correlação global das métricas coletadas.")
    parser.add_argument("--output", type=Path, default=OUTPUT_MARKDOWN)
    parser.add_argument("--html-output", type=Path, default=OUTPUT_HTML)
    args = parser.parse_args()

    connection = get_connection()
    try:
        rows = _fetch_rows(connection)
    finally:
        connection.close()
    if not rows:
        raise RuntimeError("nenhum repositório encontrado — rode o coletor antes")

    result = compute_correlations(build_metric_values(rows))
    markdown = render_markdown(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(result), encoding="utf-8")
    _write_csv(OUTPUT_SPEARMAN_CSV, result, "spearman")
    _write_csv(OUTPUT_PEARSON_CSV, result, "pearson")
    print(f"Relatórios salvos em {args.output} e {args.html_output}")


if __name__ == "__main__":
    main()

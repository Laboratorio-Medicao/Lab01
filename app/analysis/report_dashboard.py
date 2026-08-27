from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

from analysis.correlation import METRIC_LABELS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = REPO_ROOT / "app" / "data" / "repos.csv"
SPEARMAN_CSV = REPO_ROOT / "docs" / "dados" / "correlacao-spearman.csv"
PEARSON_CSV = REPO_ROOT / "docs" / "dados" / "correlacao-pearson.csv"
OUTPUT_PATH = REPO_ROOT / "docs" / "visualizacoes" / "dashboard.html"

STAR_FARMING_AGE_YEARS = 1.5
STAR_FARMING_STARGAZERS = 100_000
RQ07_TOP_LANGUAGES = 10
RQ07_MIN_REPOS = 10

_TIOBE_TOP_20 = {
    "Python": 1, "C": 2, "C++": 3, "Java": 4, "C#": 5,
    "JavaScript": 6, "Visual Basic": 7, "SQL": 8, "R": 9, "Rust": 10,
    "Delphi/Object Pascal": 11, "Scratch": 12, "PHP": 13, "Go": 14,
    "Fortran": 15, "Ruby": 16, "Swift": 17, "Perl": 18, "COBOL": 19,
    "Assembly language": 20,
}
_GITHUB_TO_TIOBE = {"Assembly": "Assembly language"}

_RQ01_COLOR = "#1f77b4"
_RQ02_COLOR = "#2ca02c"
_RQ03_COLOR = "#8c564b"
_RQ04_COLOR = "#17becf"
_RQ06_COLOR = "#1f77b4"
_RQ08_COLOR = "#9467bd"
_FARMING_COLOR = "#d62728"
_REST_COLOR = "#1f77b4"
_TIOBE_COLOR = "#1f77b4"
_NON_TIOBE_COLOR = "#ff7f0e"


def tiobe_position(language: str | None) -> int | None:
    if not language:
        return None
    normalized = _GITHUB_TO_TIOBE.get(language, language)
    return _TIOBE_TOP_20.get(normalized)


def _parse_float(value: str) -> float | None:
    return float(value) if value not in (None, "") else None


def _parse_int(value: str) -> int | None:
    return int(value) if value not in (None, "") else None


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_collected_at(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _days_since_push(pushed_at: str, collected_at: str) -> float | None:
    """Precisão total (não os passos de 0.1 ano de `update_recency_years`),
    replicando o cálculo original de RQ04 em `analyze_rq03_rq04.py`."""
    if not pushed_at or not collected_at:
        return None
    delta = (_parse_collected_at(collected_at) - _parse_iso8601(pushed_at)).total_seconds() / 86400
    return delta if delta >= 0 else None


def load_repos(path: Path = DATA_PATH) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            rows.append({
                "owner": r["owner"],
                "name": r["name"],
                "label": f"{r['owner']}/{r['name']}",
                "stargazer_count": _parse_int(r["stargazer_count"]),
                "fork_count": _parse_int(r["fork_count"]),
                "primary_language": r["primary_language"] or None,
                "merged_pull_requests": _parse_int(r["merged_pull_requests"]),
                "releases_count": _parse_int(r["releases_count"]),
                "open_issues": _parse_int(r["open_issues"]),
                "closed_issues": _parse_int(r["closed_issues"]),
                "age_years": _parse_float(r["age_years"]),
                "days_since_push": _days_since_push(r["pushed_at"], r["collected_at"]),
                "closed_issues_ratio": _parse_float(r["closed_issues_ratio"]),
                "fork_star_ratio": _parse_float(r["fork_star_ratio"]),
            })
    return rows


def is_star_farming(repo: dict) -> bool:
    return (
        repo["age_years"] is not None
        and repo["age_years"] < STAR_FARMING_AGE_YEARS
        and repo["stargazer_count"] is not None
        and repo["stargazer_count"] > STAR_FARMING_STARGAZERS
    )


@dataclass
class Summary:
    n: int
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float
    mean: float

    @property
    def iqr(self) -> float:
        return self.q3 - self.q1


def summarize(values: list[float]) -> Summary:
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return Summary(
        n=len(values),
        minimum=min(values),
        q1=q1,
        median=median,
        q3=q3,
        maximum=max(values),
        mean=statistics.mean(values),
    )


def _box_trace(summary: Summary, name: str, color: str) -> go.Box:
    return go.Box(
        q1=[summary.q1], median=[summary.median], q3=[summary.q3],
        lowerfence=[summary.minimum], upperfence=[summary.maximum],
        mean=[summary.mean], name=name, boxmean=True, marker_color=color,
    )



def build_kpis(rows: list[dict]) -> dict:
    total = len(rows)
    ages = [r["age_years"] for r in rows if r["age_years"] is not None]
    prs = [r["merged_pull_requests"] for r in rows if r["merged_pull_requests"] is not None]
    releases = [r["releases_count"] for r in rows if r["releases_count"] is not None]
    recency_days = [r["days_since_push"] for r in rows if r["days_since_push"] is not None]
    closed_ratio = [r["closed_issues_ratio"] for r in rows if r["closed_issues_ratio"] is not None]
    fork_ratio = [r["fork_star_ratio"] for r in rows if r["fork_star_ratio"] is not None]
    languages = Counter(r["primary_language"] for r in rows if r["primary_language"])
    top_lang, top_lang_count = languages.most_common(1)[0]
    farming_count = sum(1 for r in rows if is_star_farming(r))

    return {
        "total_repos": total,
        "total_stars": sum(r["stargazer_count"] for r in rows if r["stargazer_count"] is not None),
        "median_age": statistics.median(ages),
        "median_prs": statistics.median(prs),
        "median_releases": statistics.median(releases),
        "median_recency_days": statistics.median(recency_days),
        "median_closed_ratio": statistics.median(closed_ratio),
        "median_fork_ratio": statistics.median(fork_ratio),
        "farming_count": farming_count,
        "farming_pct": farming_count / total * 100,
        "unique_languages": len(languages),
        "top_lang": top_lang,
        "top_lang_pct": top_lang_count / total * 100,
        "no_lang_pct": sum(1 for r in rows if not r["primary_language"]) / total * 100,
    }


_KPI_CARD_TEMPLATE = """\
<div class="kpi-card">
  <span class="kpi-value">{value}</span>
  <span class="kpi-label">{label}</span>
</div>"""


def render_kpi_cards(k: dict) -> str:
    cards = [
        (f"{k['total_repos']:,}".replace(",", "."), "Repositórios analisados"),
        (f"{k['total_stars']:,}".replace(",", "."), "Estrelas somadas"),
        (f"{k['median_age']:.1f} anos", "Idade mediana (RQ01)"),
        (f"{k['median_prs']:.0f}", "PRs mergeadas — mediana (RQ02)"),
        (f"{k['median_releases']:.0f}", "Releases — mediana (RQ03)"),
        (f"{k['median_recency_days']:.1f} dias", "Desde último push — mediana (RQ04)"),
        (f"{k['unique_languages']}", f"Linguagens distintas ({k['top_lang']} lidera, {k['top_lang_pct']:.1f}%)"),
        (f"{k['median_closed_ratio']:.2f}", "Razão de issues fechadas — mediana (RQ06)"),
        (f"{k['median_fork_ratio']:.3f}", "Razão forks/estrelas — mediana (RQ08)"),
        (f"{k['farming_count']} ({k['farming_pct']:.1f}%)", "Suspeitos de star-farming"),
    ]
    return "\n".join(_KPI_CARD_TEMPLATE.format(value=v, label=l) for v, l in cards)



def build_fig_rq01_histogram(summary: Summary, ages: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=ages, nbinsx=30, marker_color=_RQ01_COLOR, opacity=0.75, name="Distribuição"))
    fig.add_vline(x=summary.median, line_dash="dash", line_color="red",
                  annotation_text=f"Mediana = {summary.median:.2f} anos", annotation_position="top right")
    fig.update_layout(title="RQ01 — Distribuição da idade dos repositórios",
                       xaxis_title="Idade (anos)", yaxis_title="Número de repositórios", bargap=0.05)
    return fig


def build_fig_rq02_histogram(summary: Summary, prs: list[float]) -> go.Figure:
    log_prs = [math.log10(v + 1) for v in prs]
    log_median = math.log10(summary.median + 1)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=log_prs, nbinsx=40, marker_color=_RQ02_COLOR, opacity=0.75, name="Distribuição"))
    fig.add_vline(x=log_median, line_dash="dash", line_color="red",
                  annotation_text=f"Mediana = {summary.median:.0f} PRs", annotation_position="top right")
    fig.update_layout(title="RQ02 — Distribuição de pull requests aceitas (escala log10)",
                       xaxis_title="log10(PRs aceitas + 1)", yaxis_title="Número de repositórios", bargap=0.05)
    return fig


def build_fig_star_farming_scatter(rows: list[dict]) -> go.Figure:
    normal_x, normal_y, normal_text = [], [], []
    farming_x, farming_y, farming_text = [], [], []
    for r in rows:
        if r["age_years"] is None or r["stargazer_count"] is None:
            continue
        if is_star_farming(r):
            farming_x.append(r["age_years"]); farming_y.append(r["stargazer_count"]); farming_text.append(r["label"])
        else:
            normal_x.append(r["age_years"]); normal_y.append(r["stargazer_count"]); normal_text.append(r["label"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=normal_x, y=normal_y, mode="markers", name="Demais repositórios",
                              marker=dict(color=_RQ01_COLOR, size=6, opacity=0.5), text=normal_text))
    fig.add_trace(go.Scatter(x=farming_x, y=farming_y, mode="markers",
                              name=f"Idade < {STAR_FARMING_AGE_YEARS}a e > {STAR_FARMING_STARGAZERS:,} estrelas",
                              marker=dict(color=_FARMING_COLOR, size=8), text=farming_text))
    fig.update_layout(title="RQ01 — Idade vs. estrelas (destaque star-farming)",
                       xaxis_title="Idade (anos)", yaxis_title="Estrelas",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return fig



def build_fig_rq03_histogram(summary: Summary, releases: list[float]) -> go.Figure:
    log_releases = [math.log10(v + 1) for v in releases]
    log_median = math.log10(summary.median + 1)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=log_releases, nbinsx=40, marker_color=_RQ03_COLOR, opacity=0.75, name="Distribuição"))
    fig.add_vline(x=log_median, line_dash="dash", line_color="red",
                  annotation_text=f"Mediana = {summary.median:.0f} releases", annotation_position="top right")
    fig.update_layout(title="RQ03 — Distribuição do total de releases (escala log10)",
                       xaxis_title="log10(releases + 1)", yaxis_title="Número de repositórios", bargap=0.05)
    return fig


def build_fig_rq04_histogram(summary: Summary, days: list[float]) -> go.Figure:
    log_days = [math.log10(v + 1) for v in days]
    log_median = math.log10(summary.median + 1)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=log_days, nbinsx=40, marker_color=_RQ04_COLOR, opacity=0.75, name="Distribuição"))
    fig.add_vline(x=log_median, line_dash="dash", line_color="red",
                  annotation_text=f"Mediana = {summary.median:.1f} dias", annotation_position="top right")
    fig.update_layout(title="RQ04 — Dias desde a última atualização (escala log10)",
                       xaxis_title="log10(dias desde último push + 1)", yaxis_title="Número de repositórios", bargap=0.05)
    return fig


def build_fig_rq0304_scatter(rows: list[dict]) -> go.Figure:
    x, y, text = [], [], []
    for r in rows:
        if r["releases_count"] is None or r["days_since_push"] is None:
            continue
        x.append(r["releases_count"])
        y.append(r["days_since_push"])
        text.append(r["label"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="markers",
                              marker=dict(color=_RQ03_COLOR, size=6, opacity=0.5), text=text, name="Repositórios"))
    fig.update_layout(title="RQ03 × RQ04 — Releases vs. dias desde o último push",
                       xaxis_title="Total de releases", yaxis_title="Dias desde último push",
                       yaxis_type="log", showlegend=False)
    return fig



def build_fig_rq05_languages(rows: list[dict]) -> go.Figure:
    counts = Counter(r["primary_language"] for r in rows if r["primary_language"])
    ordered = counts.most_common()
    tiobe_langs, tiobe_counts, other_langs, other_counts = [], [], [], []
    for lang, count in reversed(ordered):
        if tiobe_position(lang):
            tiobe_langs.append(lang); tiobe_counts.append(count)
        else:
            other_langs.append(lang); other_counts.append(count)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="No TIOBE Top 20", x=tiobe_counts, y=tiobe_langs, orientation="h", marker_color=_TIOBE_COLOR))
    fig.add_trace(go.Bar(name="Fora do TIOBE Top 20", x=other_counts, y=other_langs, orientation="h", marker_color=_NON_TIOBE_COLOR))
    fig.update_layout(title="RQ05 — Distribuição de linguagens primárias (1.000 repositórios)",
                       xaxis_title="Número de repositórios", yaxis_title="Linguagem", barmode="overlay",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02), height=700)
    return fig


def build_fig_rq06_histogram(summary: Summary, ratios: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=ratios, nbinsx=30, marker_color=_RQ06_COLOR, opacity=0.75, name="Distribuição"))
    fig.add_vline(x=summary.median, line_dash="dash", line_color="red",
                  annotation_text=f"Mediana = {summary.median:.4f}", annotation_position="top right")
    fig.update_layout(title="RQ06 — Distribuição da razão de issues fechadas",
                       xaxis_title="Razão issues fechadas / total", yaxis_title="Número de repositórios", bargap=0.05)
    return fig


@dataclass
class LanguageStats:
    language: str
    repo_count: int
    median_prs: float
    median_releases: float
    median_days_since_push: float


def compute_rq07_stats(rows: list[dict]) -> list[LanguageStats]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if not r["primary_language"] or r["merged_pull_requests"] is None or r["releases_count"] is None or r["days_since_push"] is None:
            continue
        buckets[r["primary_language"]].append(r)

    stats = []
    for language, entries in buckets.items():
        if len(entries) < RQ07_MIN_REPOS:
            continue
        stats.append(LanguageStats(
            language=language,
            repo_count=len(entries),
            median_prs=statistics.median(e["merged_pull_requests"] for e in entries),
            median_releases=statistics.median(e["releases_count"] for e in entries),
            median_days_since_push=statistics.median(e["days_since_push"] for e in entries),
        ))
    stats.sort(key=lambda s: s.repo_count, reverse=True)
    return stats[:RQ07_TOP_LANGUAGES]


def _spearman_rank(values: list[float]) -> float:
    """Spearman entre popularidade (posição na lista, já ordenada) e `values`."""
    n = len(values)
    ranks = list(range(1, n + 1))
    ordered = sorted(enumerate(values), key=lambda x: x[1], reverse=True)
    metric_ranks = [0] * n
    for rank, (idx, _) in enumerate(ordered, 1):
        metric_ranks[idx] = rank
    d2 = sum((ranks[i] - metric_ranks[i]) ** 2 for i in range(n))
    return 1 - (6 * d2) / (n * (n ** 2 - 1))


def build_figs_rq07(stats: list[LanguageStats]) -> list[go.Figure]:
    langs = [s.language for s in stats]
    configs = [
        ("RQ07 — Mediana de PRs mergeadas por linguagem", "Mediana de PRs mergeadas", [s.median_prs for s in stats], "#2ca02c"),
        ("RQ07 — Mediana de releases por linguagem", "Mediana de releases", [s.median_releases for s in stats], "#9467bd"),
        ("RQ07 — Mediana de dias desde último push por linguagem", "Dias desde último push", [s.median_days_since_push for s in stats], "#d62728"),
    ]
    figs = []
    for title, yaxis, values, color in configs:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=langs, y=values, marker_color=color))
        fig.update_layout(title=title, xaxis_title="Linguagem (ordenada por nº de repos)",
                           yaxis_title=yaxis, showlegend=False)
        figs.append(fig)
    return figs


def rq07_conclusion(stats: list[LanguageStats]) -> str:
    if len(stats) < 2:
        return "Amostra insuficiente para calcular correlação."
    r_prs = _spearman_rank([s.median_prs for s in stats])
    r_rel = _spearman_rank([s.median_releases for s in stats])
    r_upd = _spearman_rank([-s.median_days_since_push for s in stats])

    def interpret(r: float) -> str:
        if r > 0.5:
            return "correlação positiva"
        if r < -0.5:
            return "correlação negativa"
        return "sem correlação clara"

    return (
        f"Correlação de Spearman entre popularidade da linguagem (nº de repos na amostra) e cada métrica — "
        f"PRs mergeadas: ρ = {r_prs:.2f} ({interpret(r_prs)}); "
        f"releases: ρ = {r_rel:.2f} ({interpret(r_rel)}); "
        f"atualização (menos dias = mais atualizado): ρ = {r_upd:.2f} ({interpret(r_upd)})."
    )



def build_fig_rq08_histogram(summary: Summary, ratios: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=ratios, nbinsx=30, marker_color=_RQ08_COLOR, opacity=0.75, name="Distribuição"))
    fig.add_vline(x=summary.median, line_dash="dash", line_color="red",
                  annotation_text=f"Mediana = {summary.median:.4f}", annotation_position="top right")
    fig.update_layout(title="RQ08 — Distribuição de fork_star_ratio (bônus)",
                       xaxis_title="fork_star_ratio (fork_count / stargazer_count)",
                       yaxis_title="Número de repositórios", bargap=0.05)
    return fig


def build_fig_rq08_group_comparison(rows: list[dict]) -> go.Figure:
    farming_ratios = [r["fork_star_ratio"] for r in rows if r["fork_star_ratio"] is not None and is_star_farming(r)]
    rest_ratios = [r["fork_star_ratio"] for r in rows if r["fork_star_ratio"] is not None and not is_star_farming(r)]
    fig = go.Figure()
    fig.add_trace(go.Box(y=farming_ratios, name=f"Star-farming (< {STAR_FARMING_AGE_YEARS}a, > {STAR_FARMING_STARGAZERS:,}⭐)",
                          marker_color=_FARMING_COLOR, boxmean=True))
    fig.add_trace(go.Box(y=rest_ratios, name="Resto da amostra", marker_color=_REST_COLOR, boxmean=True))
    fig.update_layout(title="RQ08 — fork_star_ratio: star-farming vs. resto da amostra",
                       yaxis_title="fork_star_ratio", showlegend=True)
    return fig



def _read_matrix_csv(path: Path) -> tuple[list[str], list[list[float | None]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)[1:]
        matrix = []
        for row in reader:
            matrix.append([None if v == "" else float(v) for v in row[1:]])
        return header, matrix


def build_correlation_heatmap(metrics: list[str], matrix: list[list[float | None]], title: str) -> go.Figure:
    labels = [METRIC_LABELS.get(m, m) for m in metrics]
    text = [["" if v is None else f"{v:.2f}" for v in row] for row in matrix]
    fig = go.Figure(go.Heatmap(
        z=matrix, x=labels, y=labels, zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
        text=text, texttemplate="%{text}", colorbar_title="r",
        hovertemplate="%{y} × %{x}<br>Correlação: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(title=f"Matriz de correlação — {title}", xaxis_title="Métrica", yaxis_title="Métrica",
                       height=750, margin=dict(l=170, r=40, t=80, b=170))
    return fig


def top_correlation_pairs(metrics: list[str], matrix: list[list[float | None]], top_n: int = 10) -> list[tuple[str, str, float]]:
    pairs = []
    for i, m1 in enumerate(metrics):
        for j in range(i + 1, len(metrics)):
            v = matrix[i][j]
            if v is not None:
                pairs.append((m1, metrics[j], v))
    pairs.sort(key=lambda p: abs(p[2]), reverse=True)
    return pairs[:top_n]



_TABLE_COLUMNS = [
    ("label", "Repositório", "str"),
    ("primary_language", "Linguagem", "str"),
    ("stargazer_count", "Estrelas", "num"),
    ("fork_count", "Forks", "num"),
    ("merged_pull_requests", "PRs mergeadas", "num"),
    ("releases_count", "Releases", "num"),
    ("age_years", "Idade (anos)", "num"),
    ("closed_issues_ratio", "Razão issues fechadas", "num"),
    ("fork_star_ratio", "fork/estrela", "num"),
]


def build_repo_table_data(rows: list[dict]) -> list[list]:
    data = []
    for r in sorted(rows, key=lambda r: r["stargazer_count"] or 0, reverse=True):
        data.append([r.get(key) for key, _, _ in _TABLE_COLUMNS])
    return data



def _fig_to_div(fig: go.Figure, div_id: str) -> str:
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id=div_id)


_CHART_SECTION = """\
<section class="chart-block">
  <h3>{title}</h3>
  <p class="chart-body">{body}</p>
  {chart}
</section>"""


def render_html(rows: list[dict]) -> str:
    kpis = build_kpis(rows)

    ages = [r["age_years"] for r in rows if r["age_years"] is not None]
    prs = [r["merged_pull_requests"] for r in rows if r["merged_pull_requests"] is not None]
    releases = [r["releases_count"] for r in rows if r["releases_count"] is not None]
    recency_days = [r["days_since_push"] for r in rows if r["days_since_push"] is not None]
    closed_ratios = [r["closed_issues_ratio"] for r in rows if r["closed_issues_ratio"] is not None]
    fork_ratios = [r["fork_star_ratio"] for r in rows if r["fork_star_ratio"] is not None]

    age_summary = summarize(ages)
    prs_summary = summarize(prs)
    releases_summary = summarize(releases)
    recency_summary = summarize(recency_days)
    closed_ratio_summary = summarize(closed_ratios)
    fork_ratio_summary = summarize(fork_ratios)

    rq07_stats = compute_rq07_stats(rows)

    spearman_metrics, spearman_matrix = _read_matrix_csv(SPEARMAN_CSV)
    pearson_metrics, pearson_matrix = _read_matrix_csv(PEARSON_CSV)

    overview = f"""
    <div class="kpi-grid">{render_kpi_cards(kpis)}</div>
    <section class="chart-block">
      <h3>Repositórios coletados</h3>
      <p class="chart-body">Tabela interativa com os 1.000 repositórios da amostra. Use a busca para filtrar por
      nome, dono ou linguagem, e clique nos cabeçalhos para ordenar por qualquer métrica.</p>
      <input id="repo-search" type="text" placeholder="Buscar por repositório ou linguagem..." class="search-box">
      <div class="table-wrap">
        <table id="repo-table">
          <thead><tr>{"".join(f'<th data-col="{i}" data-type="{t}">{label}</th>' for i, (_, label, t) in enumerate(_TABLE_COLUMNS))}</tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <p class="table-count"><span id="table-count"></span> repositórios exibidos</p>
    </section>
    """

    rq01_02 = "\n".join([
        _CHART_SECTION.format(title="RQ01 — Idade do repositório (histograma)",
            body="Histograma da idade em anos, calculada a partir da data de criação. A mediana observada é "
                 f"{age_summary.median:.2f} anos, bem acima do limiar de 3 anos previsto na hipótese.",
            chart=_fig_to_div(build_fig_rq01_histogram(age_summary, ages), "rq01-hist")),
        _CHART_SECTION.format(title="RQ01 — Idade do repositório (box plot)",
            body="Box plot resumindo Q1, mediana, Q3 e amplitude da idade dos repositórios.",
            chart=_fig_to_div(go.Figure([_box_trace(age_summary, "RQ01", _RQ01_COLOR)]).update_layout(
                title="RQ01 — Box plot da idade dos repositórios", yaxis_title="Idade (anos)", showlegend=False),
                "rq01-box")),
        _CHART_SECTION.format(title="RQ01 — Idade vs. estrelas (star-farming)",
            body=f"Dispersão idade × estrelas. Em vermelho, os {kpis['farming_count']} repositórios "
                 f"(idade < {STAR_FARMING_AGE_YEARS} anos e mais de {STAR_FARMING_STARGAZERS:,} estrelas) "
                 "suspeitos de star-farming/hype identificados na análise.",
            chart=_fig_to_div(build_fig_star_farming_scatter(rows), "rq01-scatter")),
        _CHART_SECTION.format(title="RQ02 — Pull requests aceitas (histograma)",
            body="Histograma em escala log10, dada a forte assimetria da distribuição. A linha tracejada marca "
                 f"a mediana ({prs_summary.median:.0f} PRs).",
            chart=_fig_to_div(build_fig_rq02_histogram(prs_summary, prs), "rq02-hist")),
        _CHART_SECTION.format(title="RQ02 — Pull requests aceitas (box plot)",
            body="Box plot em escala linear — a distância entre mediana e máximo evidencia a assimetria à direita.",
            chart=_fig_to_div(go.Figure([_box_trace(prs_summary, "RQ02", _RQ02_COLOR)]).update_layout(
                title="RQ02 — Box plot de pull requests aceitas", yaxis_title="PRs aceitas (merged)", showlegend=False),
                "rq02-box")),
    ])

    rq03_04 = "\n".join([
        _CHART_SECTION.format(title="RQ03 — Total de releases (histograma)",
            body=f"Histograma em escala log10. Mediana de {releases_summary.median:.0f} releases; "
                 f"{sum(1 for r in rows if r['releases_count'] == 0)} repositórios não possuem releases formais.",
            chart=_fig_to_div(build_fig_rq03_histogram(releases_summary, releases), "rq03-hist")),
        _CHART_SECTION.format(title="RQ03 — Total de releases (box plot)",
            body="Box plot do total de releases por repositório.",
            chart=_fig_to_div(go.Figure([_box_trace(releases_summary, "RQ03", _RQ03_COLOR)]).update_layout(
                title="RQ03 — Box plot do total de releases", yaxis_title="Total de releases", showlegend=False),
                "rq03-box")),
        _CHART_SECTION.format(title="RQ04 — Dias desde a última atualização (histograma)",
            body=f"Histograma em escala log10. Mediana de {recency_summary.median:.1f} dias desde o último push.",
            chart=_fig_to_div(build_fig_rq04_histogram(recency_summary, recency_days), "rq04-hist")),
        _CHART_SECTION.format(title="RQ04 — Dias desde a última atualização (box plot)",
            body="Box plot dos dias desde o último push por repositório.",
            chart=_fig_to_div(go.Figure([_box_trace(recency_summary, "RQ04", _RQ04_COLOR)]).update_layout(
                title="RQ04 — Box plot de dias desde último push", yaxis_title="Dias desde último push", showlegend=False),
                "rq04-box")),
        _CHART_SECTION.format(title="RQ03 × RQ04 — Releases vs. dias desde o último push",
            body="Dispersão entre número de releases e dias desde o último push (escala log no eixo Y).",
            chart=_fig_to_div(build_fig_rq0304_scatter(rows), "rq0304-scatter")),
    ])

    rq05_06 = "\n".join([
        _CHART_SECTION.format(title="RQ05 — Linguagem primária",
            body=f"Distribuição das linguagens primárias. Azul = presente no TIOBE Top 20 (ago/2026); "
                 f"laranja = fora do ranking. {kpis['no_lang_pct']:.1f}% dos repositórios não têm linguagem definida.",
            chart=_fig_to_div(build_fig_rq05_languages(rows), "rq05-bar")),
        _CHART_SECTION.format(title="RQ06 — Razão de issues fechadas (histograma)",
            body=f"Histograma da razão issues fechadas / total. Mediana de {closed_ratio_summary.median:.4f}.",
            chart=_fig_to_div(build_fig_rq06_histogram(closed_ratio_summary, closed_ratios), "rq06-hist")),
        _CHART_SECTION.format(title="RQ06 — Razão de issues fechadas (box plot)",
            body="Box plot resumindo Q1, mediana, Q3 e amplitude da razão de issues fechadas.",
            chart=_fig_to_div(go.Figure([_box_trace(closed_ratio_summary, "RQ06", _RQ06_COLOR)]).update_layout(
                title="RQ06 — Box plot da razão de issues fechadas", yaxis_title="Razão issues fechadas / total", showlegend=False),
                "rq06-box")),
    ])

    rq07_figs = build_figs_rq07(rq07_stats)
    rq07_bodies = [
        "Mediana de PRs mergeadas por linguagem (top 10 por nº de repositórios na amostra, mínimo 10 repos por linguagem).",
        "Mediana de releases por repositório, por linguagem.",
        "Mediana de dias desde o último push, por linguagem — valores menores indicam repositórios mais ativos.",
    ]
    rq07 = "\n".join(
        _CHART_SECTION.format(title="RQ07 — Segmentação por linguagem", body=body, chart=_fig_to_div(fig, f"rq07-{i}"))
        for i, (fig, body) in enumerate(zip(rq07_figs, rq07_bodies))
    )
    rq07 += f'<section class="chart-block"><h3>Conclusão RQ07</h3><p class="chart-body">{rq07_conclusion(rq07_stats)}</p></section>'

    rq08 = "\n".join([
        _CHART_SECTION.format(title="RQ08 — fork_star_ratio (histograma, bônus)",
            body=f"Histograma de fork_star_ratio. Mediana de {fork_ratio_summary.median:.4f}.",
            chart=_fig_to_div(build_fig_rq08_histogram(fork_ratio_summary, fork_ratios), "rq08-hist")),
        _CHART_SECTION.format(title="RQ08 — fork_star_ratio (box plot, bônus)",
            body="Box plot resumindo Q1, mediana, Q3 e amplitude de fork_star_ratio.",
            chart=_fig_to_div(go.Figure([_box_trace(fork_ratio_summary, "RQ08", _RQ08_COLOR)]).update_layout(
                title="RQ08 — Box plot de fork_star_ratio", yaxis_title="fork_star_ratio", showlegend=False),
                "rq08-box")),
        _CHART_SECTION.format(title="RQ08 — Star-farming vs. resto da amostra (bônus)",
            body="Comparação de fork_star_ratio entre o grupo suspeito de star-farming e o resto da amostra.",
            chart=_fig_to_div(build_fig_rq08_group_comparison(rows), "rq08-group")),
    ])

    top_pairs = top_correlation_pairs(spearman_metrics, spearman_matrix)
    pairs_rows = "".join(
        f"<tr><td>{METRIC_LABELS.get(a, a)}</td><td>{METRIC_LABELS.get(b, b)}</td><td>{v:.3f}</td></tr>"
        for a, b, v in top_pairs
    )
    correlacao = f"""
    {_CHART_SECTION.format(title="Matriz de correlação — Spearman",
        body="Correlação de Spearman entre as métricas coletadas e derivadas. Menos sensível a outliers e assimetria.",
        chart=_fig_to_div(build_correlation_heatmap(spearman_metrics, spearman_matrix, "Spearman"), "corr-spearman"))}
    {_CHART_SECTION.format(title="Matriz de correlação — Pearson",
        body="Correlação de Pearson, para comparação com relações estritamente lineares.",
        chart=_fig_to_div(build_correlation_heatmap(pearson_metrics, pearson_matrix, "Pearson"), "corr-pearson"))}
    <section class="chart-block">
      <h3>Maiores correlações absolutas (Spearman)</h3>
      <table class="pairs-table"><thead><tr><th>Métrica A</th><th>Métrica B</th><th>ρ</th></tr></thead>
      <tbody>{pairs_rows}</tbody></table>
    </section>
    """

    tabs = [
        ("overview", "Visão Geral", overview),
        ("rq0102", "RQ01–RQ02 · Idade e PRs", rq01_02),
        ("rq0304", "RQ03–RQ04 · Releases e Atualização", rq03_04),
        ("rq0506", "RQ05–RQ06 · Linguagem e Issues", rq05_06),
        ("rq07", "RQ07 · Linguagem vs. Métricas", rq07),
        ("rq08", "RQ08 · Engajamento (bônus)", rq08),
        ("correlacao", "Correlação Global", correlacao),
    ]

    nav_buttons = "\n".join(
        f'<button class="tab-btn{" active" if i == 0 else ""}" data-tab="{tab_id}">{label}</button>'
        for i, (tab_id, label, _) in enumerate(tabs)
    )
    tab_panels = "\n".join(
        f'<div class="tab-panel{" active" if i == 0 else ""}" id="tab-{tab_id}">{content}</div>'
        for i, (tab_id, _, content) in enumerate(tabs)
    )

    table_data_json = json.dumps(build_repo_table_data(rows), ensure_ascii=False)
    table_columns_json = json.dumps([{"key": k, "label": l, "type": t} for k, l, t in _TABLE_COLUMNS], ensure_ascii=False)

    plotly_cdn = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — 1.000 repositórios mais populares do GitHub</title>
{plotly_cdn}
<style>
  :root {{
    --bg: #f7f8fa; --card-bg: #ffffff; --text: #1a1a1a; --muted: #555;
    --border: #e2e4e8; --accent: #1f77b4;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 0 0 64px 0;
  }}
  header.top {{
    background: #14213d; color: #fff; padding: 24px 32px;
  }}
  header.top h1 {{ margin: 0 0 4px 0; font-size: 1.6rem; }}
  header.top p {{ margin: 0; color: #cbd5e1; font-size: 0.95rem; }}
  .wrap {{ max-width: 1280px; margin: 0 auto; padding: 24px 20px; }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 12px; margin-bottom: 28px;
  }}
  .kpi-card {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;
  }}
  .kpi-value {{ font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
  .kpi-label {{ font-size: 0.78rem; color: var(--muted); }}
  .tab-nav {{
    display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 2px solid var(--border);
    margin-bottom: 24px; position: sticky; top: 0; background: var(--bg); z-index: 10; padding-top: 8px;
  }}
  .tab-btn {{
    background: none; border: none; padding: 10px 16px; font-size: 0.9rem; font-weight: 600;
    color: var(--muted); cursor: pointer; border-bottom: 3px solid transparent; border-radius: 6px 6px 0 0;
  }}
  .tab-btn:hover {{ background: #eef1f5; }}
  .tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .chart-block {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px; margin-bottom: 20px;
  }}
  .chart-block h3 {{ margin-top: 0; }}
  .chart-body {{ color: var(--muted); max-width: 900px; font-size: 0.92rem; }}
  .search-box {{
    width: 100%; max-width: 420px; padding: 8px 12px; border: 1px solid var(--border);
    border-radius: 8px; font-size: 0.9rem; margin-bottom: 12px;
  }}
  .table-wrap {{ overflow-x: auto; max-height: 520px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  thead th {{ position: sticky; top: 0; background: #eef1f5; cursor: pointer; user-select: none; }}
  thead th:hover {{ background: #e2e6ec; }}
  tbody tr:hover {{ background: #f5f7fa; }}
  .table-count {{ font-size: 0.8rem; color: var(--muted); }}
  .pairs-table {{ max-width: 620px; }}
  .pairs-table td, .pairs-table th {{ white-space: normal; }}
</style>
</head>
<body>
<header class="top">
  <h1>Dashboard interativo — Características de Repositórios Populares</h1>
  <p>Lab01 · Engenharia de Software · 1.000 repositórios mais estrelados do GitHub (coleta: agosto de 2026)</p>
</header>
<div class="wrap">
  <nav class="tab-nav">{nav_buttons}</nav>
  {tab_panels}
</div>
<script>
  document.querySelectorAll(".tab-btn").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      document.querySelectorAll(".tab-btn").forEach(function (b) {{ b.classList.remove("active"); }});
      document.querySelectorAll(".tab-panel").forEach(function (p) {{ p.classList.remove("active"); }});
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
      window.dispatchEvent(new Event("resize"));
    }});
  }});

  (function () {{
    var columns = {table_columns_json};
    var rows = {table_data_json};
    var tbody = document.querySelector("#repo-table tbody");
    var countLabel = document.getElementById("table-count");
    var searchInput = document.getElementById("repo-search");
    var sortState = {{ col: null, dir: 1 }};

    function fmt(value, type) {{
      if (value === null || value === undefined) return "—";
      if (type === "num") {{
        return typeof value === "number" && !Number.isInteger(value) ? value.toFixed(4) : value;
      }}
      return value;
    }}

    function render(data) {{
      var html = "";
      for (var i = 0; i < data.length; i++) {{
        html += "<tr>";
        for (var c = 0; c < columns.length; c++) {{
          html += "<td>" + fmt(data[i][c], columns[c].type) + "</td>";
        }}
        html += "</tr>";
      }}
      tbody.innerHTML = html;
      countLabel.textContent = data.length;
    }}

    function currentRows() {{
      var term = searchInput.value.trim().toLowerCase();
      var filtered = !term ? rows.slice() : rows.filter(function (r) {{
        return (String(r[0]).toLowerCase().indexOf(term) !== -1) ||
               (String(r[1] || "").toLowerCase().indexOf(term) !== -1);
      }});
      if (sortState.col !== null) {{
        var col = sortState.col, dir = sortState.dir, type = columns[col].type;
        filtered.sort(function (a, b) {{
          var va = a[col], vb = b[col];
          if (va === null) return 1;
          if (vb === null) return -1;
          if (type === "num") return (va - vb) * dir;
          return String(va).localeCompare(String(vb)) * dir;
        }});
      }}
      return filtered;
    }}

    searchInput.addEventListener("input", function () {{ render(currentRows()); }});

    document.querySelectorAll("#repo-table thead th").forEach(function (th) {{
      th.addEventListener("click", function () {{
        var col = parseInt(th.dataset.col, 10);
        sortState.dir = (sortState.col === col) ? -sortState.dir : -1;
        sortState.col = col;
        render(currentRows());
      }});
    }});

    render(rows);
  }})();
</script>
</body>
</html>"""


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Gera dashboard HTML interativo com todas as RQs do laboratório.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Caminho para repos.csv")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Caminho de saída do dashboard.html")
    args = parser.parse_args()

    rows = load_repos(args.data)
    if not rows:
        raise RuntimeError(f"nenhum repositório encontrado em {args.data}")

    html = render_html(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Dashboard salvo em {args.output}")


if __name__ == "__main__":
    main()

from datetime import datetime, timezone

import plotly.graph_objects as go

from analysis.analyze_rq03_rq04 import run_analysis
from analysis.report_rq03_rq04 import (
    build_fig_rq03_boxplot,
    build_fig_rq03_histogram,
    build_fig_rq03_rq04_scatter,
    build_fig_rq04_boxplot,
    build_fig_rq04_histogram,
    render_html,
)


REFERENCE_DATE = datetime(2026, 8, 25, tzinfo=timezone.utc)
ROWS = [
    (0, "2026-08-24T00:00:00Z"),
    (10, "2026-08-20T00:00:00Z"),
    (100, "2026-07-25T00:00:00Z"),
]


def _result():
    return run_analysis(ROWS, REFERENCE_DATE)


def test_rq03_figures_are_plotly_figures():
    result = _result()
    releases = [0.0, 10.0, 100.0]

    assert isinstance(build_fig_rq03_histogram(result.releases_summary, releases), go.Figure)
    assert isinstance(build_fig_rq03_boxplot(result.releases_summary), go.Figure)


def test_rq04_figures_are_plotly_figures():
    result = _result()
    days = [1.0, 5.0, 31.0]

    assert isinstance(build_fig_rq04_histogram(result.days_since_push_summary, days), go.Figure)
    assert isinstance(build_fig_rq04_boxplot(result.days_since_push_summary), go.Figure)


def test_histograms_use_logarithmic_input_values():
    result = _result()
    fig_rq03 = build_fig_rq03_histogram(result.releases_summary, [0.0, 10.0, 100.0])
    fig_rq04 = build_fig_rq04_histogram(result.days_since_push_summary, [1.0, 5.0, 31.0])

    assert list(fig_rq03.data[0].x) == [0.0, 1.0413926851582251, 2.0043213737826426]
    assert list(fig_rq04.data[0].x) == [0.3010299956639812, 0.7781512503836436, 1.505149978319906]


def test_scatter_keeps_repository_labels_and_original_values_in_tooltip():
    fig = build_fig_rq03_rq04_scatter([
        ("owner/repo", 10.0, 5.0),
        ("other/project", 0.0, 1.0),
    ])

    assert isinstance(fig, go.Figure)
    assert list(fig.data[0].text) == ["owner/repo", "other/project"]
    assert list(fig.data[0].customdata[0]) == [10.0, 5.0]


def test_render_html_contains_all_rq03_rq04_sections():
    result = _result()
    html = render_html(
        result,
        releases=[0.0, 10.0, 100.0],
        days_since_push=[1.0, 5.0, 31.0],
        scatter_points=[("owner/repo", 10.0, 5.0)],
    )

    assert "RQ03" in html
    assert "RQ04" in html
    assert "RQ03 × RQ04" in html
    assert "plotly" in html.lower()

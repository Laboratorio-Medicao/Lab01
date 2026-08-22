import plotly.graph_objects as go

from analysis.analyze_rq01_rq02 import FieldSummary
from analysis.report_rq01_rq02 import (
    build_fig_rq01_boxplot,
    build_fig_rq01_histogram,
    build_fig_rq02_boxplot,
    build_fig_rq02_histogram,
    build_fig_star_farming_scatter,
    render_html,
)


def _age_summary():
    return FieldSummary(
        label="age_years",
        n=1000,
        missing=0,
        minimum=0.00,
        q1=3.50,
        median=7.70,
        q3=11.33,
        maximum=18.40,
        mean=7.65,
        outliers_low=[],
        outliers_high=[],
    )


def _prs_summary():
    return FieldSummary(
        label="merged_pull_requests",
        n=1000,
        missing=0,
        minimum=0.00,
        q1=175.00,
        median=768.00,
        q3=3391.25,
        maximum=103167.00,
        mean=4212.96,
        outliers_low=[],
        outliers_high=[("firstcontributions/first-contributions", 103167.00)],
    )


def test_build_fig_rq01_histogram_returns_figure():
    fig = build_fig_rq01_histogram(_age_summary(), ages=[0.5, 3.0, 7.7, 11.0, 18.0])

    assert isinstance(fig, go.Figure)


def test_build_fig_rq01_histogram_has_histogram_trace():
    fig = build_fig_rq01_histogram(_age_summary(), ages=[0.5, 3.0, 7.7, 11.0, 18.0])

    types = [type(t).__name__ for t in fig.data]
    assert "Histogram" in types


def test_build_fig_rq01_boxplot_returns_figure():
    fig = build_fig_rq01_boxplot(_age_summary())

    assert isinstance(fig, go.Figure)


def test_build_fig_rq01_boxplot_has_box_trace():
    fig = build_fig_rq01_boxplot(_age_summary())

    types = [type(t).__name__ for t in fig.data]
    assert "Box" in types


def test_build_fig_rq02_histogram_returns_figure():
    fig = build_fig_rq02_histogram(_prs_summary(), prs=[0, 175, 768, 3391, 103167])

    assert isinstance(fig, go.Figure)


def test_build_fig_rq02_histogram_uses_log_transformed_values():
    prs = [0, 175, 768, 3391, 103167]
    fig = build_fig_rq02_histogram(_prs_summary(), prs=prs)

    x_values = list(fig.data[0].x)
    assert max(x_values) < 10  # log10(103167 + 1) ~= 5.0, not the raw value


def test_build_fig_rq02_boxplot_returns_figure():
    fig = build_fig_rq02_boxplot(_prs_summary())

    assert isinstance(fig, go.Figure)


def test_build_fig_rq02_boxplot_has_box_trace():
    fig = build_fig_rq02_boxplot(_prs_summary())

    types = [type(t).__name__ for t in fig.data]
    assert "Box" in types


def _scatter_points():
    return [
        ("normal/repo-a", 7.0, 5000),
        ("normal/repo-b", 10.0, 20000),
        ("openclaw/openclaw", 0.70, 386403),
    ]


def test_build_fig_star_farming_scatter_returns_figure():
    fig = build_fig_star_farming_scatter(_scatter_points())

    assert isinstance(fig, go.Figure)


def test_build_fig_star_farming_scatter_splits_into_two_traces():
    fig = build_fig_star_farming_scatter(_scatter_points())

    assert len(fig.data) == 2


def test_build_fig_star_farming_scatter_highlights_farming_repo():
    fig = build_fig_star_farming_scatter(_scatter_points())

    farming_trace = fig.data[1]
    assert "openclaw/openclaw" in farming_trace.text
    normal_trace = fig.data[0]
    assert "openclaw/openclaw" not in normal_trace.text


def test_render_html_returns_string_with_plotly_cdn():
    html = render_html(
        _age_summary(), _prs_summary(),
        ages=[0.5, 3.0, 7.7, 11.0, 18.0],
        prs=[0, 175, 768, 3391, 103167],
        scatter_points=_scatter_points(),
    )

    assert isinstance(html, str)
    assert "plotly" in html.lower()


def test_render_html_contains_all_rq_sections():
    html = render_html(
        _age_summary(), _prs_summary(),
        ages=[0.5, 3.0, 7.7, 11.0, 18.0],
        prs=[0, 175, 768, 3391, 103167],
        scatter_points=_scatter_points(),
    )

    assert "RQ01" in html
    assert "RQ02" in html

import plotly.graph_objects as go

from analysis.analyze_rq08 import FieldSummary
from analysis.report_rq08 import (
    build_fig_rq08_boxplot,
    build_fig_rq08_group_comparison,
    build_fig_rq08_histogram,
    render_html,
)


def _summary():
    return FieldSummary(
        label="fork_star_ratio",
        n=1000,
        missing=0,
        minimum=0.0009,
        q1=0.0772,
        median=0.1144,
        q3=0.1798,
        maximum=1.9449,
        mean=0.1458,
        outliers_low=[],
        outliers_high=[("firstcontributions/first-contributions", 1.9449)],
    )


def test_build_fig_rq08_histogram_returns_figure():
    fig = build_fig_rq08_histogram(_summary(), ratios=[0.05, 0.08, 0.11, 0.18, 1.94])

    assert isinstance(fig, go.Figure)


def test_build_fig_rq08_histogram_has_histogram_trace():
    fig = build_fig_rq08_histogram(_summary(), ratios=[0.05, 0.08, 0.11, 0.18, 1.94])

    types = [type(t).__name__ for t in fig.data]
    assert "Histogram" in types


def test_build_fig_rq08_boxplot_returns_figure():
    fig = build_fig_rq08_boxplot(_summary())

    assert isinstance(fig, go.Figure)


def test_build_fig_rq08_boxplot_has_box_trace():
    fig = build_fig_rq08_boxplot(_summary())

    types = [type(t).__name__ for t in fig.data]
    assert "Box" in types


def test_build_fig_rq08_group_comparison_returns_figure():
    fig = build_fig_rq08_group_comparison(
        star_farming_ratios=[0.10, 0.12, 0.15],
        rest_ratios=[0.08, 0.11, 0.18, 0.20],
    )

    assert isinstance(fig, go.Figure)


def test_build_fig_rq08_group_comparison_has_two_box_traces():
    fig = build_fig_rq08_group_comparison(
        star_farming_ratios=[0.10, 0.12, 0.15],
        rest_ratios=[0.08, 0.11, 0.18, 0.20],
    )

    types = [type(t).__name__ for t in fig.data]
    assert types == ["Box", "Box"]


def test_build_fig_rq08_group_comparison_preserves_group_values():
    fig = build_fig_rq08_group_comparison(
        star_farming_ratios=[0.10, 0.12, 0.15],
        rest_ratios=[0.08, 0.11, 0.18, 0.20],
    )

    assert list(fig.data[0].y) == [0.10, 0.12, 0.15]
    assert list(fig.data[1].y) == [0.08, 0.11, 0.18, 0.20]


def test_render_html_returns_string_with_plotly_cdn():
    html = render_html(
        _summary(),
        ratios=[0.05, 0.08, 0.11, 0.18, 1.94],
        star_farming_ratios=[0.10, 0.12],
        rest_ratios=[0.08, 0.11, 0.18],
    )

    assert isinstance(html, str)
    assert "plotly" in html.lower()


def test_render_html_contains_rq08_section():
    html = render_html(
        _summary(),
        ratios=[0.05, 0.08, 0.11, 0.18, 1.94],
        star_farming_ratios=[0.10, 0.12],
        rest_ratios=[0.08, 0.11, 0.18],
    )

    assert "RQ08" in html

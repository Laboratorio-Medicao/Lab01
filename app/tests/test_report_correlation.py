import plotly.graph_objects as go

from analysis.correlation import build_metric_values, compute_correlations
from analysis.report_correlation import build_heatmap, render_html, render_markdown


def _result():
    rows = [
        {
            "stargazer_count": 10,
            "fork_count": 2,
            "created_at": "2026-08-01T00:00:00Z",
            "pushed_at": "2026-08-24T00:00:00Z",
            "collected_at": "2026-08-25 00:00:00",
            "is_fork": 0,
            "is_archived": 0,
            "merged_pull_requests": 5,
            "releases_count": 1,
            "open_issues": 2,
            "closed_issues": 8,
        },
        {
            "stargazer_count": 20,
            "fork_count": 4,
            "created_at": "2026-07-01T00:00:00Z",
            "pushed_at": "2026-08-20T00:00:00Z",
            "collected_at": "2026-08-25 00:00:00",
            "is_fork": 0,
            "is_archived": 0,
            "merged_pull_requests": 10,
            "releases_count": 2,
            "open_issues": 4,
            "closed_issues": 6,
        },
    ]
    return compute_correlations(build_metric_values(rows))


def test_build_heatmap_returns_figure_with_expected_dimensions():
    result = _result()

    fig = build_heatmap(result, "spearman")

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert len(fig.data[0].z) == len(result.metrics)


def test_render_outputs_contain_both_correlation_methods():
    result = _result()

    markdown = render_markdown(result)
    html = render_html(result)

    assert "Spearman" in markdown
    assert "Pearson" in markdown
    assert "Matriz de correlação" in html
    assert "Spearman" in html
    assert "Pearson" in html
    assert "plotly" in html.lower()

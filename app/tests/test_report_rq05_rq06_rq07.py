import plotly.graph_objects as go

from analysis.analyze_rq05_rq06 import LanguageStats
from analysis.report_rq05_rq06_rq07 import build_fig_rq05_languages


def _lang_stats(distribution=None):
    if distribution is None:
        distribution = [("Python", 229, 22.9), ("TypeScript", 174, 17.4), ("Go", 76, 7.6)]
    return LanguageStats(distribution=distribution, no_language_count=87, total=1000)


def test_build_fig_rq05_languages_returns_figure():
    fig = build_fig_rq05_languages(_lang_stats())

    assert isinstance(fig, go.Figure)


def test_build_fig_rq05_languages_has_one_trace_per_tiobe_group():
    fig = build_fig_rq05_languages(_lang_stats())

    # Python e Go estão no TIOBE; TypeScript não — deve ter 2 traces (TIOBE / fora)
    assert len(fig.data) == 2


def test_build_fig_rq05_languages_traces_contain_all_languages():
    stats = _lang_stats()
    fig = build_fig_rq05_languages(stats)

    all_langs = set()
    for trace in fig.data:
        all_langs.update(trace.y)

    expected = {lang for lang, _, _ in stats.distribution}
    assert expected == all_langs


from analysis.analyze_rq05_rq06 import RatioStats
from analysis.report_rq05_rq06_rq07 import build_fig_rq06_boxplot, build_fig_rq06_histogram


def _ratio_stats():
    return RatioStats(
        n=957,
        null_count=43,
        minimum=0.0769,
        q1=0.7044,
        median=0.8763,
        q3=0.9677,
        maximum=1.0,
        mean=0.8025,
    )


def test_build_fig_rq06_histogram_returns_figure():
    fig = build_fig_rq06_histogram(_ratio_stats(), ratios=[0.5, 0.7, 0.8, 0.9, 1.0])

    assert isinstance(fig, go.Figure)


def test_build_fig_rq06_histogram_has_histogram_trace():
    fig = build_fig_rq06_histogram(_ratio_stats(), ratios=[0.5, 0.7, 0.8, 0.9, 1.0])

    types = [type(t).__name__ for t in fig.data]
    assert "Histogram" in types


def test_build_fig_rq06_boxplot_returns_figure():
    fig = build_fig_rq06_boxplot(_ratio_stats())

    assert isinstance(fig, go.Figure)


def test_build_fig_rq06_boxplot_has_box_trace():
    fig = build_fig_rq06_boxplot(_ratio_stats())

    types = [type(t).__name__ for t in fig.data]
    assert "Box" in types


from analysis.analyze_rq07 import LanguageStats as LangStats07
from analysis.report_rq05_rq06_rq07 import build_figs_rq07


def _lang_stats_07():
    return [
        LangStats07("Python", 229, 560.0, 20.0, 5.2),
        LangStats07("TypeScript", 174, 1996.5, 134.0, 2.6),
        LangStats07("Go", 76, 1690.0, 139.5, 2.8),
    ]


def test_build_figs_rq07_returns_three_figures():
    figs = build_figs_rq07(_lang_stats_07())

    assert len(figs) == 3
    assert all(isinstance(f, go.Figure) for f in figs)


def test_build_figs_rq07_figures_have_bar_traces():
    figs = build_figs_rq07(_lang_stats_07())

    for fig in figs:
        types = [type(t).__name__ for t in fig.data]
        assert "Bar" in types


def test_build_figs_rq07_x_axis_ordered_by_repo_count():
    stats = _lang_stats_07()  # Python(229) > TypeScript(174) > Go(76)
    figs = build_figs_rq07(stats)

    # primeiro gráfico (PRs): linguagens na ordem de popularidade decrescente
    x_langs = list(figs[0].data[0].x)
    assert x_langs == ["Python", "TypeScript", "Go"]


from analysis.report_rq05_rq06_rq07 import render_html


def test_render_html_returns_string_with_plotly_cdn():
    lang_stats = _lang_stats()
    ratio_stats = _ratio_stats()
    rq07_stats = _lang_stats_07()
    ratios = [0.5, 0.7, 0.8, 0.9, 1.0]

    html = render_html(lang_stats, ratio_stats, ratios, rq07_stats)

    assert isinstance(html, str)
    assert "plotly" in html.lower()


def test_render_html_contains_all_rq_sections():
    lang_stats = _lang_stats()
    ratio_stats = _ratio_stats()
    rq07_stats = _lang_stats_07()
    ratios = [0.5, 0.7, 0.8, 0.9, 1.0]

    html = render_html(lang_stats, ratio_stats, ratios, rq07_stats)

    assert "RQ05" in html
    assert "RQ06" in html
    assert "RQ07" in html

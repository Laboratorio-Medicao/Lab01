import pytest

from analysis.analyze_rq05_rq06 import (
    LanguageStats,
    RatioStats,
    compute_language_stats,
    compute_ratio_stats,
    compute_rq05_tiobe_summary,
    render_markdown,
    render_rq05_section,
    render_rq06_section,
    tiobe_position,
)


def _row(language=None, open_issues=0, closed_issues=0):
    return {"primary_language": language, "open_issues": open_issues, "closed_issues": closed_issues}


# ── RQ05 — distribuição de linguagens ────────────────────────────────────────


def test_compute_language_stats_counts_each_language():
    rows = [_row("Python"), _row("Python"), _row("JavaScript")]

    stats = compute_language_stats(rows)

    counts = {lang: count for lang, count, _ in stats.distribution}
    assert counts["Python"] == 2
    assert counts["JavaScript"] == 1


def test_compute_language_stats_sorts_by_count_descending():
    rows = [_row("Go"), _row("Python"), _row("Python"), _row("Go"), _row("Go")]

    stats = compute_language_stats(rows)

    names = [lang for lang, _, _ in stats.distribution]
    assert names[0] == "Go"
    assert names[1] == "Python"


def test_compute_language_stats_counts_null_separately():
    rows = [_row(None), _row(None), _row("Rust")]

    stats = compute_language_stats(rows)

    assert stats.no_language_count == 2
    assert all(lang is not None for lang, _, _ in stats.distribution)


def test_compute_language_stats_computes_percentage_over_total():
    rows = [_row("Python")] * 3 + [_row("Go")] * 1 + [_row(None)] * 1

    stats = compute_language_stats(rows)

    pct_by_lang = {lang: pct for lang, _, pct in stats.distribution}
    assert pct_by_lang["Python"] == pytest.approx(60.0, abs=0.01)
    assert pct_by_lang["Go"] == pytest.approx(20.0, abs=0.01)


def test_compute_language_stats_total_includes_null_rows():
    rows = [_row("Python"), _row(None)]

    stats = compute_language_stats(rows)

    assert stats.total == 2


# ── RQ06 — razão de issues fechadas ──────────────────────────────────────────


def test_compute_ratio_stats_computes_median():
    rows = [
        _row(open_issues=0, closed_issues=10),  # ratio = 1.0
        _row(open_issues=5, closed_issues=5),   # ratio = 0.5
        _row(open_issues=9, closed_issues=1),   # ratio = 0.1
    ]

    stats = compute_ratio_stats(rows)

    assert stats.median == pytest.approx(0.5, abs=0.01)
    assert stats.null_count == 0


def test_compute_ratio_stats_counts_null_repos():
    rows = [
        _row(open_issues=0, closed_issues=0),  # ratio = None
        _row(open_issues=0, closed_issues=0),  # ratio = None
        _row(open_issues=2, closed_issues=8),  # ratio = 0.8
    ]

    stats = compute_ratio_stats(rows)

    assert stats.null_count == 2
    assert stats.n == 1


def test_compute_ratio_stats_n_counts_only_defined_ratios():
    rows = [
        _row(open_issues=1, closed_issues=1),
        _row(open_issues=0, closed_issues=0),  # null
        _row(open_issues=2, closed_issues=3),
    ]

    stats = compute_ratio_stats(rows)

    assert stats.n == 2
    assert stats.null_count == 1


def test_compute_ratio_stats_identifies_outliers_high():
    rows = [_row(open_issues=9, closed_issues=1)] * 10 + [_row(open_issues=0, closed_issues=1000)]

    stats = compute_ratio_stats(rows)

    assert len(stats.outliers_high) >= 1


def test_ratio_stats_iqr_and_high_fence_are_derived():
    stats = RatioStats(n=10, null_count=0, minimum=0.0, q1=0.2, median=0.5, q3=0.8,
                       maximum=1.0, mean=0.5)

    assert stats.iqr == pytest.approx(0.6, abs=0.001)
    assert stats.high_fence == pytest.approx(0.8 + 1.5 * 0.6, abs=0.001)


# ── Rendering ─────────────────────────────────────────────────────────────────


def test_compute_rq05_tiobe_summary_counts_languages_in_tiobe():
    stats = LanguageStats(
        distribution=[("Python", 500, 50.0), ("TypeScript", 300, 30.0), ("Go", 100, 10.0)],
        no_language_count=100,
        total=1000,
    )

    summary = compute_rq05_tiobe_summary(stats)

    assert summary["languages_in_tiobe"] == 2  # Python e Go
    assert summary["languages_not_in_tiobe"] == 1  # TypeScript


def test_compute_rq05_tiobe_summary_computes_repos_covered_by_tiobe():
    stats = LanguageStats(
        distribution=[("Python", 500, 50.0), ("TypeScript", 300, 30.0), ("Go", 100, 10.0)],
        no_language_count=100,
        total=1000,
    )

    summary = compute_rq05_tiobe_summary(stats)

    assert summary["repos_in_tiobe"] == 600   # Python + Go
    assert summary["repos_not_in_tiobe"] == 300  # TypeScript


def test_compute_rq05_tiobe_summary_identifies_notable_exceptions():
    stats = LanguageStats(
        distribution=[("Python", 500, 50.0), ("TypeScript", 300, 30.0), ("Shell", 100, 10.0)],
        no_language_count=100,
        total=1000,
    )

    summary = compute_rq05_tiobe_summary(stats)

    exceptions = [lang for lang, _ in summary["top_exceptions"]]
    assert "TypeScript" in exceptions
    assert "Shell" in exceptions
    assert "Python" not in exceptions


def test_render_rq05_section_includes_tiobe_summary():
    stats = LanguageStats(
        distribution=[("Python", 700, 70.0), ("TypeScript", 300, 30.0)],
        no_language_count=0,
        total=1000,
    )

    section = render_rq05_section(stats)

    assert "TypeScript" in section
    assert "700" in section or "70" in section


def test_tiobe_position_returns_rank_for_known_language():
    assert tiobe_position("Python") == 1
    assert tiobe_position("Rust") == 10
    assert tiobe_position("Go") == 14


def test_tiobe_position_returns_none_for_unknown_language():
    assert tiobe_position("TypeScript") is None
    assert tiobe_position("Jupyter Notebook") is None


def test_tiobe_position_handles_github_name_variants():
    assert tiobe_position("Assembly") == 20


def test_render_rq05_section_shows_tiobe_position_for_known_languages():
    stats = LanguageStats(
        distribution=[("Python", 500, 50.0), ("TypeScript", 300, 30.0)],
        no_language_count=0,
        total=1000,
    )

    section = render_rq05_section(stats)

    assert "#1" in section
    assert "—" in section


def test_render_rq05_section_includes_tiobe_reference():
    stats = LanguageStats(distribution=[("Python", 1000, 100.0)], no_language_count=0, total=1000)

    section = render_rq05_section(stats)

    assert "TIOBE" in section


def test_render_rq05_section_includes_all_languages():
    stats = LanguageStats(
        distribution=[("Python", 500, 50.0), ("JavaScript", 300, 30.0)],
        no_language_count=50,
        total=1000,
    )

    section = render_rq05_section(stats)

    assert "Python" in section
    assert "JavaScript" in section


def test_render_rq05_section_shows_null_count():
    stats = LanguageStats(distribution=[("Python", 900, 90.0)], no_language_count=100, total=1000)

    section = render_rq05_section(stats)

    assert "100" in section


def test_render_rq05_section_includes_hypothesis():
    stats = LanguageStats(distribution=[("Python", 1000, 100.0)], no_language_count=0, total=1000)

    section = render_rq05_section(stats)

    assert "Hipótese" in section


def test_render_rq06_section_includes_median():
    stats = RatioStats(n=100, null_count=5, minimum=0.0, q1=0.4, median=0.7, q3=0.9,
                       maximum=1.0, mean=0.65)

    section = render_rq06_section(stats)

    assert "Mediana" in section
    assert "RQ06" in section


def test_render_rq06_section_shows_null_count():
    stats = RatioStats(n=100, null_count=42, minimum=0.0, q1=0.4, median=0.7, q3=0.9,
                       maximum=1.0, mean=0.65)

    section = render_rq06_section(stats)

    assert "42" in section


def test_render_rq06_section_omits_outliers_table_when_empty():
    stats = RatioStats(n=10, null_count=0, minimum=0.0, q1=0.4, median=0.5, q3=0.6,
                       maximum=0.7, mean=0.5, outliers_high=[])

    section = render_rq06_section(stats)

    assert "Top outliers" not in section


def test_render_rq06_section_includes_outliers_table_when_present():
    stats = RatioStats(n=10, null_count=0, minimum=0.0, q1=0.4, median=0.5, q3=0.6,
                       maximum=1.0, mean=0.5, outliers_high=[("owner/repo", 0.99)])

    section = render_rq06_section(stats)

    assert "Top outliers" in section
    assert "owner/repo" in section


def test_render_markdown_includes_both_sections():
    lang_stats = LanguageStats(
        distribution=[("Python", 1000, 100.0)], no_language_count=0, total=1000
    )
    ratio_stats = RatioStats(n=1000, null_count=0, minimum=0.0, q1=0.4, median=0.7, q3=0.9,
                             maximum=1.0, mean=0.65)

    md = render_markdown(lang_stats, ratio_stats)

    assert "RQ05" in md
    assert "RQ06" in md
    assert "Hipótese" in md

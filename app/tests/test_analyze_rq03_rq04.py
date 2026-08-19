from datetime import datetime, timezone

import pytest

from analysis.analyze_rq03_rq04 import (
    compute_outlier_summary,
    percentile_inc,
    run_analysis,
    summarize,
    validate_total_rows,
)


def test_percentile_inc_matches_known_example():
    values = [1, 2, 3, 4, 5]
    assert percentile_inc(values, 0.25) == pytest.approx(2.0)
    assert percentile_inc(values, 0.50) == pytest.approx(3.0)
    assert percentile_inc(values, 0.75) == pytest.approx(4.0)


def test_summarize_computes_quartiles_and_iqr():
    values = [1, 2, 3, 4, 5, 6, 7, 8]
    summary = summarize(values)

    assert summary.count == 8
    assert summary.mean == pytest.approx(4.5)
    assert summary.median == pytest.approx(4.5)
    assert summary.q1 == pytest.approx(2.75)
    assert summary.q3 == pytest.approx(6.25)
    assert summary.iqr == pytest.approx(3.5)


def test_compute_outlier_summary_detects_high_tail_values():
    values = [1, 2, 3, 4, 5, 6, 100]
    summary = summarize(values)
    outliers = compute_outlier_summary(values, summary)

    assert outliers.count == 1
    assert outliers.upper_bound < 100


def test_run_analysis_tracks_missing_invalid_future_and_zero_releases():
    reference = datetime(2026, 8, 17, tzinfo=timezone.utc)
    rows = [
        (0, "2026-08-16T00:00:00Z"),
        (10, "2026-08-10T00:00:00Z"),
        (None, "2026-08-01T00:00:00Z"),
        (3, None),
        (7, "invalido"),
        (5, "2026-08-30T00:00:00Z"),
    ]

    result = run_analysis(rows, reference)

    assert result.total_rows == 6
    assert result.releases_missing == 1
    assert result.pushed_at_missing == 1
    assert result.pushed_at_invalid == 1
    assert result.pushed_at_future == 1
    assert result.zero_releases_count == 1
    assert result.releases_summary.count == 5
    assert result.days_since_push_summary.count == 3


def test_validate_total_rows_requires_exactly_1000_repositories():
    validate_total_rows(1000)

    with pytest.raises(RuntimeError, match="exige exatamente 1000"):
        validate_total_rows(999)

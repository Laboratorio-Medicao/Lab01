from datetime import datetime, timezone

import pytest

from analysis.correlation import (
    METRIC_NAMES,
    build_metric_values,
    compute_correlations,
    correlation_pairs,
)


REFERENCE_DATE = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _row(**overrides):
    row = {
        "stargazer_count": 10,
        "fork_count": 2,
        "created_at": "2026-08-01T00:00:00Z",
        "pushed_at": "2026-08-24T00:00:00Z",
        "is_fork": 0,
        "is_archived": 0,
        "merged_pull_requests": 5,
        "releases_count": 1,
        "open_issues": 2,
        "closed_issues": 8,
    }
    row.update(overrides)
    return row


def test_build_metric_values_includes_original_and_derived_metrics():
    values = build_metric_values([_row()], REFERENCE_DATE)

    assert tuple(values) == METRIC_NAMES
    assert values["idade_anos"][0] == pytest.approx(24 / 365.25)
    assert values["dias_desde_ultimo_push"][0] == pytest.approx(1.0)
    assert values["issues_total"][0] == 10.0
    assert values["closed_issues_ratio"][0] == pytest.approx(0.8)
    assert values["fork_star_ratio"][0] == pytest.approx(0.2)


def test_compute_correlations_uses_pairwise_valid_observations():
    values = {
        "a": [1.0, 2.0, None, 4.0],
        "b": [2.0, 4.0, 8.0, None],
    }

    result = compute_correlations(values)

    assert result.counts == [[3, 2], [2, 3]]
    assert result.pearson[0][1] == pytest.approx(1.0)
    assert result.spearman[0][1] == pytest.approx(1.0)


def test_spearman_handles_tied_values_with_average_ranks():
    result = compute_correlations({
        "a": [1.0, 1.0, 2.0, 3.0],
        "b": [1.0, 2.0, 2.0, 3.0],
    })

    assert result.spearman[0][1] == pytest.approx(0.8333333333)


def test_correlation_pairs_excludes_diagonal_and_orders_by_absolute_value():
    result = compute_correlations({
        "a": [1.0, 2.0, 3.0],
        "b": [3.0, 2.0, 1.0],
        "c": [1.0, 3.0, 2.0],
    })

    pairs = correlation_pairs(result)

    assert len(pairs) == 3
    assert pairs[0][:3] == ("a", "b", -1.0)

from src.metrics import (
    compute_age_years,
    compute_closed_issues_ratio,
    compute_fork_star_ratio,
    compute_update_recency_years,
)


def test_compute_age_years_uses_365_25_days_per_year():
    age = compute_age_years("2020-01-01T00:00:00Z", "2024-01-01 00:00:00")

    assert age == round((4 * 365 + 1) / 365.25, 1)


def test_compute_age_years_rounds_to_one_decimal():
    age = compute_age_years("2020-01-01T00:00:00Z", "2020-07-02 00:00:00")

    assert age == round(183 / 365.25, 1)


def test_compute_update_recency_years_uses_pushed_at_not_created_at():
    recency = compute_update_recency_years("2023-06-01T00:00:00Z", "2024-06-01 00:00:00")

    assert recency == round(366 / 365.25, 1)


def test_compute_update_recency_years_is_zero_for_same_day_push():
    recency = compute_update_recency_years("2024-06-01T12:00:00Z", "2024-06-01 12:00:00")

    assert recency == 0.0


def test_compute_closed_issues_ratio_normal_case():
    ratio = compute_closed_issues_ratio(open_issues=1, closed_issues=5)

    assert ratio == round(5 / 6, 4)


def test_compute_closed_issues_ratio_returns_none_when_total_is_zero():
    ratio = compute_closed_issues_ratio(open_issues=0, closed_issues=0)

    assert ratio is None


def test_compute_closed_issues_ratio_is_one_when_everything_is_closed():
    ratio = compute_closed_issues_ratio(open_issues=0, closed_issues=10)

    assert ratio == 1.0


def test_compute_closed_issues_ratio_is_zero_when_nothing_is_closed():
    ratio = compute_closed_issues_ratio(open_issues=10, closed_issues=0)

    assert ratio == 0.0


def test_compute_fork_star_ratio_normal_case():
    ratio = compute_fork_star_ratio(fork_count=25, stargazer_count=100)

    assert ratio == round(25 / 100, 4)


def test_compute_fork_star_ratio_returns_none_when_stargazer_count_is_zero():
    ratio = compute_fork_star_ratio(fork_count=5, stargazer_count=0)

    assert ratio is None


def test_compute_fork_star_ratio_returns_none_when_fork_count_is_none():
    ratio = compute_fork_star_ratio(fork_count=None, stargazer_count=100)

    assert ratio is None


def test_compute_fork_star_ratio_is_zero_when_repository_has_no_forks():
    ratio = compute_fork_star_ratio(fork_count=0, stargazer_count=100)

    assert ratio == 0.0


def test_compute_fork_star_ratio_can_exceed_one_when_forks_outnumber_stars():
    ratio = compute_fork_star_ratio(fork_count=150, stargazer_count=100)

    assert ratio == 1.5

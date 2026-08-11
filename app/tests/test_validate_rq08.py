import pytest

from src import storage
from src.validate_rq08 import (
    InsufficientSampleError,
    RestNotFoundError,
    compute_engagement_score,
    compute_star_velocity,
    ensure_minimum_sample,
    fetch_candidate_pool,
    render_markdown_table,
    validate_candidates,
)
from tests.conftest import requires_supabase


class FakeRestClient:
    def __init__(self, get_all_pages_result=None, not_found=False):
        self._get_all_pages_result = get_all_pages_result if get_all_pages_result is not None else []
        self._not_found = not_found

    def get_all_pages(self, url):
        if self._not_found:
            raise RestNotFoundError(f"404 em {url}")
        return self._get_all_pages_result


def repository_row(repository_id, releases_count):
    return {
        "id": repository_id,
        "name": "example",
        "owner": "octocat",
        "stargazer_count": 100,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2024-01-01T00:00:00Z",
        "is_fork": 0,
        "is_archived": 0,
        "primary_language": "Python",
        "merged_pull_requests": 5,
        "releases_count": releases_count,
        "open_issues": 1,
        "closed_issues": 1,
        "raw_json": "{}",
    }


def test_compute_star_velocity_normalizes_by_age():
    assert compute_star_velocity(stargazer_count=1000, age_years=4.0) == 250.0


def test_compute_engagement_score_sums_and_normalizes_by_age():
    score = compute_engagement_score(
        merged_pull_requests=10, releases_count=5, closed_issues=25, age_years=4.0
    )

    assert score == 10.0


@requires_supabase
def test_fetch_candidate_pool_orders_by_releases_count_ascending(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", releases_count=50),
            repository_row("R_2", releases_count=5),
            repository_row("R_3", releases_count=20),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=2)

    assert [repo["releases_count"] for repo in pool] == [5, 20]


def test_validate_candidates_skips_404_and_continues(monkeypatch):
    candidates = [
        {
            "owner": "broken",
            "name": "repo",
            "stargazer_count": 100,
            "created_at": "2020-01-01T00:00:00Z",
            "collected_at": "2024-01-01 00:00:00",
            "merged_pull_requests": 5,
            "releases_count": 1,
            "closed_issues": 1,
        },
        {
            "owner": "octocat",
            "name": "example",
            "stargazer_count": 100,
            "created_at": "2020-01-01T00:00:00Z",
            "collected_at": "2024-01-01 00:00:00",
            "merged_pull_requests": 5,
            "releases_count": 1,
            "closed_issues": 1,
        },
    ]

    class RoutingClient:
        def get_all_pages(self, url):
            if "broken" in url:
                raise RestNotFoundError("404")
            return [{"id": 1}]

    results, skipped = validate_candidates(candidates, sample_size=5, client=RoutingClient())

    assert skipped == ["broken/repo"]
    assert len(results) == 1
    assert results[0]["repo"] == "octocat/example"
    assert results[0]["matches"] is True


def test_validate_candidates_stops_once_sample_size_reached():
    candidates = [
        {
            "owner": f"owner{i}",
            "name": "repo",
            "stargazer_count": 100,
            "created_at": "2020-01-01T00:00:00Z",
            "collected_at": "2024-01-01 00:00:00",
            "merged_pull_requests": 5,
            "releases_count": 1,
            "closed_issues": 1,
        }
        for i in range(10)
    ]
    client = FakeRestClient(get_all_pages_result=[{"id": 1}])

    results, skipped = validate_candidates(candidates, sample_size=3, client=client)

    assert len(results) == 3


def test_validate_candidates_flags_releases_count_mismatch():
    candidates = [
        {
            "owner": "octocat",
            "name": "example",
            "stargazer_count": 100,
            "created_at": "2020-01-01T00:00:00Z",
            "collected_at": "2024-01-01 00:00:00",
            "merged_pull_requests": 5,
            "releases_count": 1,
            "closed_issues": 1,
        }
    ]
    client = FakeRestClient(get_all_pages_result=[{"id": 1}, {"id": 2}])

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0]["releases_rest"] == 2
    assert results[0]["matches"] is False


def test_ensure_minimum_sample_raises_when_below_minimum():
    with pytest.raises(InsufficientSampleError):
        ensure_minimum_sample([{"repo": "a"}, {"repo": "b"}], minimum=5)


def test_ensure_minimum_sample_passes_when_at_or_above_minimum():
    results = [{"repo": str(i)} for i in range(5)]

    ensure_minimum_sample(results, minimum=5)


def test_render_markdown_table_marks_matches_and_mismatches():
    results = [
        {
            "repo": "octocat/example",
            "age_years": 4.0,
            "releases_query": 5,
            "releases_rest": 5,
            "star_velocity": 25.0,
            "engagement_score": 10.0,
            "matches": True,
        },
        {
            "repo": "octocat/broken",
            "age_years": 4.0,
            "releases_query": 5,
            "releases_rest": 6,
            "star_velocity": 25.0,
            "engagement_score": 10.0,
            "matches": False,
        },
    ]

    table = render_markdown_table(results)

    assert "octocat/example" in table
    assert "✅" in table
    assert "❌" in table

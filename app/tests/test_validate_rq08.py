import pytest

from src import storage
from src.validate_rq08 import (
    InsufficientSampleError,
    RestNotFoundError,
    ensure_minimum_sample,
    fetch_candidate_pool,
    fetch_rest_forks_count,
    render_markdown_table,
    validate_candidates,
)
from tests.conftest import requires_supabase


class FakeRestClient:
    def __init__(self, get_result=None, not_found=False):
        self._get_result = get_result or {}
        self._not_found = not_found

    def get(self, url):
        if self._not_found:
            raise RestNotFoundError(f"404 em {url}")
        return self._get_result


def repository_row(repository_id, fork_count, stargazer_count=100):
    return {
        "id": repository_id,
        "name": "example",
        "owner": "octocat",
        "stargazer_count": stargazer_count,
        "fork_count": fork_count,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2024-01-01T00:00:00Z",
        "is_fork": 0,
        "is_archived": 0,
        "primary_language": "Python",
        "merged_pull_requests": 5,
        "releases_count": 2,
        "open_issues": 1,
        "closed_issues": 1,
        "raw_json": "{}",
    }


@requires_supabase
def test_fetch_candidate_pool_orders_by_fork_count_then_stargazer_count(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", fork_count=5, stargazer_count=300),
            repository_row("R_2", fork_count=5, stargazer_count=100),
            repository_row("R_3", fork_count=2, stargazer_count=200),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=3)

    assert [repo["fork_count"] for repo in pool] == [2, 5, 5]
    assert [repo["stargazer_count"] for repo in pool[1:]] == [100, 300]


@requires_supabase
def test_fetch_candidate_pool_mixes_zero_and_non_zero_forks(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", fork_count=0, stargazer_count=100),
            repository_row("R_2", fork_count=0, stargazer_count=200),
            repository_row("R_3", fork_count=3, stargazer_count=300),
            repository_row("R_4", fork_count=7, stargazer_count=400),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=4)

    forks_in_pool = [repo["fork_count"] for repo in pool]
    assert 0 in forks_in_pool
    assert any(count > 0 for count in forks_in_pool)
    assert pool[0]["fork_count"] > 0


def test_fetch_rest_forks_count_returns_value():
    client = FakeRestClient(get_result={"forks_count": 42})

    count = fetch_rest_forks_count("owner", "repo", client)

    assert count == 42


def test_validate_candidates_skips_404_and_continues():
    candidates = [
        {"owner": "broken", "name": "repo", "fork_count": 10, "stargazer_count": 100},
        {"owner": "octocat", "name": "example", "fork_count": 10, "stargazer_count": 100},
    ]

    class RoutingClient:
        def get(self, url):
            if "broken" in url:
                raise RestNotFoundError("404")
            return {"forks_count": 10}

    results, skipped = validate_candidates(candidates, sample_size=5, client=RoutingClient())

    assert skipped == ["broken/repo"]
    assert len(results) == 1
    assert results[0].repo == "octocat/example"
    assert results[0].matches is True


def test_validate_candidates_flags_fork_count_mismatch():
    candidates = [
        {"owner": "octocat", "name": "example", "fork_count": 10, "stargazer_count": 100},
    ]
    client = FakeRestClient(get_result={"forks_count": 11})

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0].matches is False
    assert results[0].fork_count_query == 10
    assert results[0].fork_count_rest == 11


def test_validate_candidates_stops_once_sample_size_reached():
    candidates = [
        {"owner": f"owner{i}", "name": "repo", "fork_count": 1, "stargazer_count": 100}
        for i in range(10)
    ]
    calls = {"count": 0}

    class CountingClient:
        def get(self, url):
            calls["count"] += 1
            return {"forks_count": 1}

    results, skipped = validate_candidates(candidates, sample_size=3, client=CountingClient())

    assert len(results) == 3
    assert calls["count"] == 3


def test_validate_candidates_includes_fork_star_ratio():
    candidates = [
        {"owner": "octocat", "name": "example", "fork_count": 25, "stargazer_count": 100},
    ]
    client = FakeRestClient(get_result={"forks_count": 25})

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0].fork_star_ratio == 0.25


def test_ensure_minimum_sample_raises_when_below_minimum():
    with pytest.raises(InsufficientSampleError):
        ensure_minimum_sample([{"repo": "a"}, {"repo": "b"}], minimum=5)


def test_ensure_minimum_sample_passes_when_at_or_above_minimum():
    results = [{"repo": str(i)} for i in range(5)]

    ensure_minimum_sample(results, minimum=5)


def test_render_markdown_table_marks_matches_and_mismatches():
    from src.validate_rq08 import ValidationResult

    results = [
        ValidationResult(
            repo="octocat/example",
            fork_count_query=10,
            fork_count_rest=10,
            fork_star_ratio=0.1,
            matches=True,
        ),
        ValidationResult(
            repo="octocat/broken",
            fork_count_query=10,
            fork_count_rest=12,
            fork_star_ratio=0.1,
            matches=False,
        ),
    ]

    table = render_markdown_table(results)

    assert "octocat/example" in table
    assert "✅" in table
    assert "❌" in table

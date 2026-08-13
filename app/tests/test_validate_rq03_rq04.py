import pytest

from src import storage
from src.validate_rq03_rq04 import (
    InsufficientSampleError,
    RestNotFoundError,
    ensure_minimum_sample,
    fetch_candidate_pool,
    fetch_rest_releases_count,
    render_markdown_table,
    validate_candidates,
)
from tests.conftest import requires_supabase


class FakeRestClient:
    def __init__(self, get_result=None, get_all_pages_result=None, not_found=False):
        self._get_result = get_result or {}
        self._get_all_pages_result = get_all_pages_result if get_all_pages_result is not None else []
        self._not_found = not_found

    def get(self, url):
        if self._not_found:
            raise RestNotFoundError(f"404 em {url}")
        return self._get_result

    def get_all_pages(self, url):
        if self._not_found:
            raise RestNotFoundError(f"404 em {url}")
        return self._get_all_pages_result


def repository_row(repository_id, releases_count, pushed_at):
    return {
        "id": repository_id,
        "name": "example",
        "owner": "octocat",
        "stargazer_count": 100,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": pushed_at,
        "is_fork": 0,
        "is_archived": 0,
        "primary_language": "Python",
        "merged_pull_requests": 5,
        "releases_count": releases_count,
        "open_issues": 1,
        "closed_issues": 1,
        "raw_json": "{}",
    }


@requires_supabase
def test_fetch_candidate_pool_orders_by_releases_then_pushed_at(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", releases_count=5, pushed_at="2024-01-03T00:00:00Z"),
            repository_row("R_2", releases_count=5, pushed_at="2024-01-01T00:00:00Z"),
            repository_row("R_3", releases_count=2, pushed_at="2024-01-02T00:00:00Z"),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=3)

    assert [repo["releases_count"] for repo in pool] == [2, 5, 5]
    assert [repo["pushed_at"] for repo in pool[1:]] == [
        "2024-01-01T00:00:00Z",
        "2024-01-03T00:00:00Z",
    ]


@requires_supabase
def test_fetch_candidate_pool_mixes_zero_and_non_zero_releases(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", releases_count=0, pushed_at="2024-01-01T00:00:00Z"),
            repository_row("R_2", releases_count=0, pushed_at="2024-01-02T00:00:00Z"),
            repository_row("R_3", releases_count=3, pushed_at="2024-01-03T00:00:00Z"),
            repository_row("R_4", releases_count=7, pushed_at="2024-01-04T00:00:00Z"),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=4)

    releases_in_pool = [repo["releases_count"] for repo in pool]
    assert 0 in releases_in_pool
    assert any(count > 0 for count in releases_in_pool)
    assert pool[0]["releases_count"] > 0


def test_fetch_rest_releases_count_counts_all_pages():
    client = FakeRestClient(get_all_pages_result=[{"id": 1}, {"id": 2}, {"id": 3}])

    count = fetch_rest_releases_count("owner", "repo", client)

    assert count == 3


def test_validate_candidates_skips_404_and_continues():
    candidates = [
        {"owner": "broken", "name": "repo", "releases_count": 1, "pushed_at": "2024-01-01T00:00:00Z"},
        {"owner": "octocat", "name": "example", "releases_count": 1, "pushed_at": "2024-01-01T00:00:00Z"},
    ]

    class RoutingClient:
        def get(self, url):
            if "broken" in url:
                raise RestNotFoundError("404")
            return {"pushed_at": "2024-01-01T00:00:00Z"}

        def get_all_pages(self, url):
            if "broken" in url:
                raise RestNotFoundError("404")
            return [{"id": 1}]

    results, skipped = validate_candidates(candidates, sample_size=5, client=RoutingClient())

    assert skipped == ["broken/repo"]
    assert len(results) == 1
    assert results[0].repo == "octocat/example"
    assert results[0].matches is True


def test_validate_candidates_flags_releases_and_pushed_at_mismatch():
    candidates = [
        {"owner": "octocat", "name": "example", "releases_count": 1, "pushed_at": "2024-01-01T00:00:00Z"},
    ]
    client = FakeRestClient(
        get_result={"pushed_at": "2023-12-31T23:59:59Z"},
        get_all_pages_result=[{"id": 1}, {"id": 2}],
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0].releases_matches is False
    assert results[0].pushed_at_matches is False
    assert results[0].matches is False


def test_validate_candidates_stops_once_sample_size_reached():
    candidates = [
        {"owner": f"owner{i}", "name": "repo", "releases_count": 1, "pushed_at": "2024-01-01T00:00:00Z"}
        for i in range(10)
    ]
    calls = {"count": 0}

    class CountingClient:
        def get(self, url):
            calls["count"] += 1
            return {"pushed_at": "2024-01-01T00:00:00Z"}

        def get_all_pages(self, url):
            return [{"id": 1}]

    results, skipped = validate_candidates(candidates, sample_size=3, client=CountingClient())

    assert len(results) == 3
    assert calls["count"] == 3


def test_ensure_minimum_sample_raises_when_below_minimum():
    with pytest.raises(InsufficientSampleError):
        ensure_minimum_sample([{"repo": "a"}, {"repo": "b"}], minimum=5)


def test_ensure_minimum_sample_passes_when_at_or_above_minimum():
    results = [{"repo": str(i)} for i in range(5)]

    ensure_minimum_sample(results, minimum=5)


def test_render_markdown_table_marks_matches_and_mismatches():
    from src.validate_rq03_rq04 import ValidationResult

    results = [
        ValidationResult(
            repo="octocat/example",
            releases_query=5,
            releases_rest=5,
            pushed_at_query="2024-01-01T00:00:00Z",
            pushed_at_rest="2024-01-01T00:00:00Z",
            releases_matches=True,
            pushed_at_matches=True,
        ),
        ValidationResult(
            repo="octocat/broken",
            releases_query=5,
            releases_rest=6,
            pushed_at_query="2024-01-01T00:00:00Z",
            pushed_at_rest="2023-12-31T23:59:59Z",
            releases_matches=False,
            pushed_at_matches=False,
        ),
    ]

    table = render_markdown_table(results)

    assert "octocat/example" in table
    assert "✅" in table
    assert "❌" in table
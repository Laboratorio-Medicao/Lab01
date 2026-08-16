import pytest

from src import storage
from src.validate_rq01_rq02 import (
    InsufficientSampleError,
    RestNotFoundError,
    RestRequestError,
    compute_age_years,
    ensure_minimum_sample,
    fetch_candidate_pool,
    fetch_merged_pr_count_via_rest_pagination,
    render_markdown_table,
    validate_candidates,
)
from tests.conftest import requires_supabase


class FakeRestClient:
    def __init__(self, get_result=None, get_all_pages_result=None, not_found=False):
        self._get_result = get_result
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


def pull_request(merged=True):
    return {"merged_at": "2020-01-01T00:00:00Z" if merged else None}


def test_compute_age_years_uses_365_25_days_per_year():
    age = compute_age_years("2020-01-01T00:00:00Z", "2024-01-01 00:00:00")

    assert age == round((4 * 365 + 1) / 365.25, 1)


def repository_row(repository_id, merged_pull_requests):
    return {
        "id": repository_id,
        "name": "example",
        "owner": "octocat",
        "stargazer_count": 100,
        "fork_count": 10,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2024-01-01T00:00:00Z",
        "is_fork": 0,
        "is_archived": 0,
        "primary_language": "Python",
        "merged_pull_requests": merged_pull_requests,
        "releases_count": 1,
        "open_issues": 1,
        "closed_issues": 1,
        "raw_json": "{}",
    }


@requires_supabase
def test_fetch_candidate_pool_orders_by_merged_pull_requests_ascending(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", merged_pull_requests=50),
            repository_row("R_2", merged_pull_requests=5),
            repository_row("R_3", merged_pull_requests=20),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=2)

    assert [repo["merged_pull_requests"] for repo in pool] == [5, 20]


def test_fetch_merged_pr_count_counts_only_merged():
    client = FakeRestClient(
        get_all_pages_result=[pull_request(merged=True) for _ in range(103)]
        + [pull_request(merged=False)]
    )

    count = fetch_merged_pr_count_via_rest_pagination("owner", "repo", client)

    assert count == 103


def test_fetch_merged_pr_count_handles_no_pull_requests():
    client = FakeRestClient(get_all_pages_result=[])

    count = fetch_merged_pr_count_via_rest_pagination("owner", "repo", client)

    assert count == 0


def test_validate_candidates_skips_404_and_continues(monkeypatch):
    candidates = [
        {
            "owner": "broken",
            "name": "repo",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        },
        {
            "owner": "octocat",
            "name": "example",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        },
    ]

    def fake_created_at(owner, name, client):
        if owner == "broken":
            raise RestNotFoundError("404")
        return "2020-01-01T00:00:00Z"

    monkeypatch.setattr("src.validate_rq01_rq02.fetch_rest_created_at", fake_created_at)
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, client: 5,
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client="fake-client")

    assert skipped == ["broken/repo (404)"]
    assert len(results) == 1
    assert results[0]["repo"] == "octocat/example"
    assert results[0]["matches"] is True


def test_validate_candidates_skips_retryable_rest_error_and_continues(monkeypatch):
    candidates = [
        {
            "owner": "flaky",
            "name": "repo",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        },
        {
            "owner": "octocat",
            "name": "example",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        },
    ]

    def fake_created_at(owner, name, client):
        if owner == "flaky":
            raise RestRequestError("503 esgotou tentativas", retryable=True)
        return "2020-01-01T00:00:00Z"

    monkeypatch.setattr("src.validate_rq01_rq02.fetch_rest_created_at", fake_created_at)
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, client: 5,
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client="fake-client")

    assert skipped == ["flaky/repo (falha transitória)"]
    assert len(results) == 1
    assert results[0]["repo"] == "octocat/example"


def test_validate_candidates_reraises_non_retryable_rest_error(monkeypatch):
    candidates = [
        {
            "owner": "broken",
            "name": "repo",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        }
    ]

    def fake_created_at(owner, name, client):
        raise RestRequestError("401 token inválido", retryable=False)

    monkeypatch.setattr("src.validate_rq01_rq02.fetch_rest_created_at", fake_created_at)

    with pytest.raises(RestRequestError):
        validate_candidates(candidates, sample_size=5, client="fake-client")


def test_validate_candidates_stops_once_sample_size_reached(monkeypatch):
    candidates = [
        {
            "owner": f"owner{i}",
            "name": "repo",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        }
        for i in range(10)
    ]
    calls = {"count": 0}

    def fake_created_at(owner, name, client):
        calls["count"] += 1
        return "2020-01-01T00:00:00Z"

    monkeypatch.setattr("src.validate_rq01_rq02.fetch_rest_created_at", fake_created_at)
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, client: 5,
    )

    results, skipped = validate_candidates(candidates, sample_size=3, client="fake-client")

    assert len(results) == 3
    assert calls["count"] == 3


def test_validate_candidates_flags_mismatch(monkeypatch):
    candidates = [
        {
            "owner": "octocat",
            "name": "example",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_pull_requests": 5,
            "collected_at": "2024-01-01 00:00:00",
        }
    ]

    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_rest_created_at",
        lambda owner, name, client: "1999-01-01T00:00:00Z",
    )
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, client: 999,
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client="fake-client")

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
            "created_at_query": "2020-01-01T00:00:00Z",
            "created_at_rest": "2020-01-01T00:00:00Z",
            "age_years": 4.0,
            "merged_query": 5,
            "merged_rest": 5,
            "matches": True,
        },
        {
            "repo": "octocat/broken",
            "created_at_query": "2020-01-01T00:00:00Z",
            "created_at_rest": "2020-01-01T00:00:00Z",
            "age_years": 4.0,
            "merged_query": 5,
            "merged_rest": 6,
            "matches": False,
        },
    ]

    table = render_markdown_table(results)

    assert "octocat/example" in table
    assert "✅" in table
    assert "❌" in table

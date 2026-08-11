import io
import urllib.error

import pytest

from src import storage
from src.validate_rq01_rq02 import (
    InsufficientSampleError,
    RestNotFoundError,
    compute_age_years,
    ensure_minimum_sample,
    fetch_candidate_pool,
    fetch_merged_pr_count_via_rest_pagination,
    render_markdown_table,
    validate_candidates,
    _rest_get,
)
from tests.conftest import requires_supabase


class FakeResponse:
    def __init__(self, payload):
        import json

        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def http_error(code, headers=None, body=b'{"message": "error"}'):
    return urllib.error.HTTPError(
        url="https://api.github.com/repos/owner/repo",
        code=code,
        msg="error",
        hdrs=headers if headers is not None else {},
        fp=io.BytesIO(body),
    )


def pull_request(merged=True):
    return {"merged_at": "2020-01-01T00:00:00Z" if merged else None}


# --- compute_age_years -------------------------------------------------


def test_compute_age_years_uses_365_25_days_per_year():
    age = compute_age_years("2020-01-01T00:00:00Z", "2024-01-01 00:00:00")

    assert age == round((4 * 365 + 1) / 365.25, 1)


# --- fetch_candidate_pool ------------------------------------------------


def repository_row(repository_id, merged_pull_requests):
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


# --- _rest_get retry/backoff --------------------------------------------


def test_rest_get_raises_not_found_without_retrying(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise http_error(404)

    monkeypatch.setattr("src.validate_rq01_rq02.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RestNotFoundError):
        _rest_get("https://api.github.com/repos/owner/repo", "token")

    assert attempts["count"] == 1


def test_rest_get_retries_on_server_error_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise http_error(503)
        return FakeResponse({"ok": True})

    monkeypatch.setattr("src.validate_rq01_rq02.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.validate_rq01_rq02.time.sleep", lambda seconds: None)

    result = _rest_get("https://api.github.com/repos/owner/repo", "token")

    assert result == {"ok": True}
    assert attempts["count"] == 2


def test_rest_get_respects_retry_after_header(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise http_error(403, headers={"Retry-After": "7"})
        return FakeResponse({"ok": True})

    monkeypatch.setattr("src.validate_rq01_rq02.urllib.request.urlopen", fake_urlopen)
    sleep_calls = []
    monkeypatch.setattr(
        "src.validate_rq01_rq02.time.sleep", lambda seconds: sleep_calls.append(seconds)
    )

    _rest_get("https://api.github.com/repos/owner/repo", "token")

    assert sleep_calls == [7.0]


def test_rest_get_gives_up_after_max_attempts(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise http_error(503)

    monkeypatch.setattr("src.validate_rq01_rq02.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.validate_rq01_rq02.time.sleep", lambda seconds: None)

    with pytest.raises(RuntimeError):
        _rest_get("https://api.github.com/repos/owner/repo", "token", max_attempts=3)

    assert attempts["count"] == 3


# --- fetch_merged_pr_count_via_rest_pagination ---------------------------


def test_fetch_merged_pr_count_paginates_and_counts_only_merged(monkeypatch):
    pages = [
        [pull_request(merged=True) for _ in range(100)],
        [pull_request(merged=True) for _ in range(3)] + [pull_request(merged=False)],
    ]

    def fake_rest_get(url, token):
        return pages.pop(0)

    monkeypatch.setattr("src.validate_rq01_rq02._rest_get", fake_rest_get)

    count = fetch_merged_pr_count_via_rest_pagination("owner", "repo", "token")

    assert count == 103


def test_fetch_merged_pr_count_stops_on_empty_page(monkeypatch):
    monkeypatch.setattr("src.validate_rq01_rq02._rest_get", lambda url, token: [])

    count = fetch_merged_pr_count_via_rest_pagination("owner", "repo", "token")

    assert count == 0


# --- validate_candidates --------------------------------------------------


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

    def fake_created_at(owner, name, token):
        if owner == "broken":
            raise RestNotFoundError("404")
        return "2020-01-01T00:00:00Z"

    monkeypatch.setattr("src.validate_rq01_rq02.fetch_rest_created_at", fake_created_at)
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, token: 5,
    )

    results, skipped = validate_candidates(candidates, sample_size=5, token="token")

    assert skipped == ["broken/repo"]
    assert len(results) == 1
    assert results[0]["repo"] == "octocat/example"
    assert results[0]["matches"] is True


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

    def fake_created_at(owner, name, token):
        calls["count"] += 1
        return "2020-01-01T00:00:00Z"

    monkeypatch.setattr("src.validate_rq01_rq02.fetch_rest_created_at", fake_created_at)
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, token: 5,
    )

    results, skipped = validate_candidates(candidates, sample_size=3, token="token")

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
        lambda owner, name, token: "1999-01-01T00:00:00Z",
    )
    monkeypatch.setattr(
        "src.validate_rq01_rq02.fetch_merged_pr_count_via_rest_pagination",
        lambda owner, name, token: 999,
    )

    results, skipped = validate_candidates(candidates, sample_size=5, token="token")

    assert results[0]["matches"] is False


# --- ensure_minimum_sample -------------------------------------------------


def test_ensure_minimum_sample_raises_when_below_minimum():
    with pytest.raises(InsufficientSampleError):
        ensure_minimum_sample([{"repo": "a"}, {"repo": "b"}], minimum=5)


def test_ensure_minimum_sample_passes_when_at_or_above_minimum():
    results = [{"repo": str(i)} for i in range(5)]

    ensure_minimum_sample(results, minimum=5)


# --- render_markdown_table -------------------------------------------------


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

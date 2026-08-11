import pytest

from src import storage
from src.validate_rq05_rq06_rq07 import (
    InsufficientSampleError,
    RestNotFoundError,
    ensure_minimum_sample,
    fetch_candidate_pool,
    render_markdown_table,
    validate_candidates,
)
from tests.conftest import requires_supabase


class FakeRestClient:
    """Dublê de RestClient — ver mesmo padrão em test_validate_rq01_rq02.py."""

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


def repository_row(repository_id, owner, name, primary_language, open_issues, closed_issues):
    return {
        "id": repository_id,
        "name": name,
        "owner": owner,
        "stargazer_count": 100,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2024-01-01T00:00:00Z",
        "is_fork": 0,
        "is_archived": 0,
        "primary_language": primary_language,
        "merged_pull_requests": 5,
        "releases_count": 1,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "raw_json": "{}",
    }


# --- fetch_candidate_pool (integração real com Postgres) ------------------


@requires_supabase
def test_fetch_candidate_pool_includes_zero_issues_repo_and_orders_rest_ascending(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            repository_row("R_1", "owner1", "repo1", "Python", open_issues=0, closed_issues=0),
            repository_row("R_2", "owner2", "repo2", "TypeScript", open_issues=10, closed_issues=40),
            repository_row("R_3", "owner3", "repo3", "Go", open_issues=1, closed_issues=1),
        ],
    )

    pool = fetch_candidate_pool(db_connection, pool_size=3)

    assert pool[0]["owner"] == "owner1"
    assert pool[0]["open_issues"] + pool[0]["closed_issues"] == 0
    remaining = [(r["owner"], r["open_issues"] + r["closed_issues"]) for r in pool[1:]]
    assert remaining == sorted(remaining, key=lambda item: item[1])


# --- validate_candidates -----------------------------------------------


def test_validate_candidates_skips_404_and_continues():
    candidates = [
        {"owner": "broken", "name": "repo", "primary_language": "Python", "open_issues": 1, "closed_issues": 1},
        {"owner": "octocat", "name": "example", "primary_language": "Python", "open_issues": 1, "closed_issues": 1},
    ]

    class RoutingClient:
        def get(self, url):
            if "broken" in url:
                raise RestNotFoundError("404")
            return {"language": "Python", "open_issues_count": 1}

        def get_all_pages(self, url):
            if "broken" in url:
                raise RestNotFoundError("404")
            return [{"title": "closed issue"}]

    results, skipped = validate_candidates(candidates, sample_size=5, client=RoutingClient())

    assert skipped == ["broken/repo"]
    assert len(results) == 1
    assert results[0].repo == "octocat/example"
    assert results[0].matches is True


def test_validate_candidates_flags_language_and_issues_mismatch():
    candidates = [
        {"owner": "octocat", "name": "example", "primary_language": "Python", "open_issues": 1, "closed_issues": 5},
    ]
    client = FakeRestClient(
        get_result={"language": "JavaScript", "open_issues_count": 1},
        get_all_pages_result=[{"title": f"issue {i}"} for i in range(3)],
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0].language_matches is False
    assert results[0].issues_match is False
    assert results[0].matches is False


def test_validate_candidates_normalizes_null_language():
    candidates = [
        {"owner": "octocat", "name": "example", "primary_language": None, "open_issues": 0, "closed_issues": 0},
    ]
    client = FakeRestClient(
        get_result={"language": None, "open_issues_count": 0},
        get_all_pages_result=[],
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0].zero_issues is True
    assert results[0].language_matches is True


def test_validate_candidates_excludes_pull_requests_from_closed_issues_count():
    candidates = [
        {"owner": "octocat", "name": "example", "primary_language": "Python", "open_issues": 0, "closed_issues": 2},
    ]
    client = FakeRestClient(
        get_result={"language": "Python", "open_issues_count": 0},
        get_all_pages_result=[
            {"title": "real issue 1"},
            {"title": "real issue 2"},
            {"title": "a PR", "pull_request": {"url": "..."}},
        ],
    )

    results, skipped = validate_candidates(candidates, sample_size=5, client=client)

    assert results[0].closed_issues_rest == 2
    assert results[0].issues_match is True


# --- ensure_minimum_sample -------------------------------------------------


def test_ensure_minimum_sample_raises_when_below_minimum():
    with pytest.raises(InsufficientSampleError):
        ensure_minimum_sample([{"repo": "a"}], minimum=5)


def test_ensure_minimum_sample_passes_when_at_or_above_minimum():
    class Result:
        pass

    ensure_minimum_sample([Result() for _ in range(5)], minimum=5)


# --- render_markdown_table -------------------------------------------------


def test_render_markdown_table_marks_matches_mismatches_and_zero_issues():
    from src.validate_rq05_rq06_rq07 import ValidationResult

    results = [
        ValidationResult(
            repo="octocat/example",
            language_query="Python",
            language_rest="Python",
            open_issues_query=0,
            open_issues_rest=0,
            closed_issues_query=0,
            closed_issues_rest=0,
            zero_issues=True,
            language_matches=True,
            issues_match=True,
        ),
        ValidationResult(
            repo="octocat/broken",
            language_query="Python",
            language_rest="JavaScript",
            open_issues_query=1,
            open_issues_rest=1,
            closed_issues_query=5,
            closed_issues_rest=3,
            zero_issues=False,
            language_matches=False,
            issues_match=False,
        ),
    ]

    table = render_markdown_table(results)

    assert "octocat/example" in table
    assert "⚠️ sim" in table
    assert "✅" in table
    assert "❌" in table

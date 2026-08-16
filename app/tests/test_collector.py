import json
from unittest.mock import patch

import pytest

from src import storage
from src.client import GraphQLRequestError
from src.collector import collect_page, collect_total, parse_repository_node
from tests.conftest import requires_supabase


def repository_node(repository_id="R_1", language=None, is_fork=False, is_archived=False):
    return {
        "id": repository_id,
        "name": "example",
        "owner": {"login": "octocat"},
        "stargazerCount": 42,
        "forkCount": 7,
        "createdAt": "2020-01-01T00:00:00Z",
        "pushedAt": "2024-01-01T00:00:00Z",
        "isFork": is_fork,
        "isArchived": is_archived,
        "primaryLanguage": {"name": language} if language else None,
        "mergedPullRequests": {"totalCount": 3},
        "releases": {"totalCount": 1},
        "openIssues": {"totalCount": 2},
        "closedIssues": {"totalCount": 8},
    }


def test_parse_repository_node_maps_all_fields():
    parsed = parse_repository_node(repository_node(language="Python"))

    assert parsed["id"] == "R_1"
    assert parsed["owner"] == "octocat"
    assert parsed["fork_count"] == 7
    assert parsed["primary_language"] == "Python"
    assert parsed["merged_pull_requests"] == 3
    assert parsed["releases_count"] == 1
    assert parsed["open_issues"] == 2
    assert parsed["closed_issues"] == 8
    assert parsed["is_fork"] == 0
    assert parsed["is_archived"] == 0
    assert json.loads(parsed["raw_json"])["id"] == "R_1"


def test_parse_repository_node_maps_fork_and_archived_flags():
    parsed = parse_repository_node(repository_node(is_fork=True, is_archived=True))

    assert parsed["is_fork"] == 1
    assert parsed["is_archived"] == 1


def test_parse_repository_node_handles_missing_language():
    parsed = parse_repository_node(repository_node(language=None))

    assert parsed["primary_language"] is None


class FakeClient:
    def __init__(self, search_response):
        self._search_response = search_response

    def execute(self, query, variables):
        return {"search": self._search_response}


@requires_supabase
def test_collect_page_persists_repositories_and_advances_cursor(db_connection):
    storage.init_db(db_connection)
    client = FakeClient(
        {
            "repositoryCount": 2,
            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            "nodes": [repository_node("R_1"), repository_node("R_2")],
        }
    )

    repositories = collect_page(client, db_connection, per_page=2)

    assert len(repositories) == 2
    assert storage.count_repositories(db_connection) == 2
    assert storage.get_collection_state(db_connection) == {
        "cursor": "cursor-1",
        "total_collected": 2,
    }


@requires_supabase
def test_collect_page_filters_out_null_nodes(db_connection):
    storage.init_db(db_connection)
    client = FakeClient(
        {
            "repositoryCount": 1,
            "pageInfo": {"hasNextPage": False, "endCursor": "cursor-1"},
            "nodes": [repository_node("R_1"), None],
        }
    )

    repositories = collect_page(client, db_connection, per_page=2)

    assert len(repositories) == 1
    assert storage.count_repositories(db_connection) == 1


@requires_supabase
def test_collect_page_resumes_from_saved_cursor(db_connection):
    storage.init_db(db_connection)
    storage.save_collection_state(db_connection, cursor="cursor-1", total_collected=10)
    client = FakeClient(
        {
            "repositoryCount": 1,
            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-2"},
            "nodes": [repository_node("R_11")],
        }
    )

    collect_page(client, db_connection, per_page=1)

    assert storage.get_collection_state(db_connection) == {
        "cursor": "cursor-2",
        "total_collected": 11,
    }


class SequencedFakeClient:
    def __init__(self, total_available):
        self._total_available = total_available
        self.calls = []

    def execute(self, query, variables):
        per_page = variables["perPage"]
        after = variables["after"]
        start = int(after) if after else 0
        self.calls.append(per_page)

        end = min(start + per_page, self._total_available)
        nodes = [repository_node(f"R_{i}") for i in range(start, end)]
        return {
            "search": {
                "repositoryCount": self._total_available,
                "pageInfo": {
                    "hasNextPage": end < self._total_available,
                    "endCursor": str(end),
                },
                "nodes": nodes,
            }
        }


@requires_supabase
def test_collect_total_accumulates_across_batches(db_connection):
    storage.init_db(db_connection)
    client = SequencedFakeClient(total_available=1000)

    with patch("src.collector.time.sleep"):
        total_collected = collect_total(client, db_connection, total=100, batch_size=25)

    assert total_collected == 100
    assert storage.count_repositories(db_connection) == 100
    assert client.calls == [25, 25, 25, 25]


@requires_supabase
def test_collect_total_clamps_last_batch_to_remaining(db_connection):
    storage.init_db(db_connection)
    client = SequencedFakeClient(total_available=1000)

    with patch("src.collector.time.sleep"):
        collect_total(client, db_connection, total=90, batch_size=25)

    assert client.calls == [25, 25, 25, 15]


@requires_supabase
def test_collect_total_stops_early_when_search_runs_out_of_results(db_connection):
    storage.init_db(db_connection)
    client = SequencedFakeClient(total_available=10)

    with patch("src.collector.time.sleep"):
        total_collected = collect_total(client, db_connection, total=100, batch_size=25)

    assert total_collected == 10
    assert storage.count_repositories(db_connection) == 10


@requires_supabase
def test_collect_total_is_noop_when_already_met(db_connection):
    storage.init_db(db_connection)
    storage.save_collection_state(db_connection, cursor="cursor-x", total_collected=100)
    client = SequencedFakeClient(total_available=1000)

    total_collected = collect_total(client, db_connection, total=100, batch_size=25)

    assert total_collected == 100
    assert client.calls == []


class ShrinkingFailureFakeClient:
    def __init__(self, total_available, fails_above_page_size):
        self._total_available = total_available
        self._fails_above_page_size = fails_above_page_size
        self.calls = []

    def execute(self, query, variables):
        per_page = variables["perPage"]
        after = variables["after"]
        self.calls.append(per_page)

        if per_page > self._fails_above_page_size:
            raise GraphQLRequestError("502 simulado", retryable=True)

        start = int(after) if after else 0
        end = min(start + per_page, self._total_available)
        return {
            "search": {
                "repositoryCount": self._total_available,
                "pageInfo": {
                    "hasNextPage": end < self._total_available,
                    "endCursor": str(end),
                },
                "nodes": [repository_node(f"R_{i}") for i in range(start, end)],
            }
        }


@requires_supabase
def test_collect_total_shrinks_batch_size_after_retryable_failure(db_connection):
    storage.init_db(db_connection)
    client = ShrinkingFailureFakeClient(total_available=1000, fails_above_page_size=5)

    with patch("src.collector.time.sleep"):
        total_collected = collect_total(client, db_connection, total=13, batch_size=25)

    assert total_collected == 13
    assert storage.count_repositories(db_connection) == 13
    assert client.calls == [13, 12, 6, 5, 5, 3]


@requires_supabase
def test_collect_total_reraises_non_retryable_graphql_error(db_connection):
    storage.init_db(db_connection)

    class AlwaysFailsClient:
        def execute(self, query, variables):
            raise GraphQLRequestError("token inválido", retryable=False)

    with pytest.raises(GraphQLRequestError):
        collect_total(AlwaysFailsClient(), db_connection, total=10, batch_size=25)


@requires_supabase
def test_collect_total_reraises_retryable_error_once_at_min_batch_size(db_connection):
    storage.init_db(db_connection)
    client = ShrinkingFailureFakeClient(total_available=1000, fails_above_page_size=1)

    with pytest.raises(GraphQLRequestError):
        with patch("src.collector.time.sleep"):
            collect_total(client, db_connection, total=10, batch_size=25)

    assert client.calls == [10, 10, 6, 5]

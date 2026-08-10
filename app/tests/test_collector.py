import json
import sqlite3
from unittest.mock import patch

from src import db
from src.collector import collect_page, collect_total, parse_repository_node


def repository_node(repository_id="R_1", language=None, is_fork=False, is_archived=False):
    return {
        "id": repository_id,
        "name": "example",
        "owner": {"login": "octocat"},
        "stargazerCount": 42,
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


def test_collect_page_persists_repositories_and_advances_cursor():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    client = FakeClient(
        {
            "repositoryCount": 2,
            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            "nodes": [repository_node("R_1"), repository_node("R_2")],
        }
    )

    repositories = collect_page(client, connection, per_page=2)

    assert len(repositories) == 2
    assert db.count_repositories(connection) == 2
    assert db.get_collection_state(connection) == {
        "cursor": "cursor-1",
        "total_collected": 2,
    }


def test_collect_page_filters_out_null_nodes():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    client = FakeClient(
        {
            "repositoryCount": 1,
            "pageInfo": {"hasNextPage": False, "endCursor": "cursor-1"},
            "nodes": [repository_node("R_1"), None],
        }
    )

    repositories = collect_page(client, connection, per_page=2)

    assert len(repositories) == 1
    assert db.count_repositories(connection) == 1


def test_collect_page_resumes_from_saved_cursor():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    db.save_collection_state(connection, cursor="cursor-1", total_collected=10)
    client = FakeClient(
        {
            "repositoryCount": 1,
            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-2"},
            "nodes": [repository_node("R_11")],
        }
    )

    collect_page(client, connection, per_page=1)

    assert db.get_collection_state(connection) == {
        "cursor": "cursor-2",
        "total_collected": 11,
    }


class SequencedFakeClient:
    """Simula a paginação real da busca do GitHub: cada página devolve até
    `perPage` repositórios a partir do cursor (índice), respeitando o total
    de repositórios "disponíveis" na busca simulada."""

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


def test_collect_total_accumulates_across_batches():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    client = SequencedFakeClient(total_available=1000)

    with patch("src.collector.time.sleep"):
        total_collected = collect_total(client, connection, total=100, batch_size=25)

    assert total_collected == 100
    assert db.count_repositories(connection) == 100
    assert client.calls == [25, 25, 25, 25]


def test_collect_total_clamps_last_batch_to_remaining():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    client = SequencedFakeClient(total_available=1000)

    with patch("src.collector.time.sleep"):
        collect_total(client, connection, total=90, batch_size=25)

    assert client.calls == [25, 25, 25, 15]


def test_collect_total_stops_early_when_search_runs_out_of_results():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    client = SequencedFakeClient(total_available=10)

    with patch("src.collector.time.sleep"):
        total_collected = collect_total(client, connection, total=100, batch_size=25)

    assert total_collected == 10
    assert db.count_repositories(connection) == 10


def test_collect_total_is_noop_when_already_met():
    connection = sqlite3.connect(":memory:")
    db.init_db(connection)
    db.save_collection_state(connection, cursor="cursor-x", total_collected=100)
    client = SequencedFakeClient(total_available=1000)

    total_collected = collect_total(client, connection, total=100, batch_size=25)

    assert total_collected == 100
    assert client.calls == []

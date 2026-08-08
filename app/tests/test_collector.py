import json
import sqlite3

from src import db
from src.collector import collect_page, parse_repository_node


def repository_node(repository_id="R_1", language=None):
    return {
        "id": repository_id,
        "name": "example",
        "owner": {"login": "octocat"},
        "stargazerCount": 42,
        "createdAt": "2020-01-01T00:00:00Z",
        "pushedAt": "2024-01-01T00:00:00Z",
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
    assert json.loads(parsed["raw_json"])["id"] == "R_1"


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

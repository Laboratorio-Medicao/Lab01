import sqlite3

from src import db


def make_connection():
    return sqlite3.connect(":memory:")


def sample_repository(repository_id="R_1", stargazer_count=100):
    return {
        "id": repository_id,
        "name": "example",
        "owner": "octocat",
        "stargazer_count": stargazer_count,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": "2024-01-01T00:00:00Z",
        "primary_language": "Python",
        "merged_pull_requests": 5,
        "releases_count": 2,
        "open_issues": 1,
        "closed_issues": 9,
        "raw_json": "{}",
    }


def test_init_db_creates_default_collection_state():
    connection = make_connection()

    db.init_db(connection)

    assert db.get_collection_state(connection) == {"cursor": None, "total_collected": 0}


def test_init_db_does_not_reset_existing_state():
    connection = make_connection()
    db.init_db(connection)
    db.save_collection_state(connection, cursor="abc", total_collected=10)

    db.init_db(connection)

    assert db.get_collection_state(connection) == {"cursor": "abc", "total_collected": 10}


def test_save_and_get_collection_state_roundtrip():
    connection = make_connection()
    db.init_db(connection)

    db.save_collection_state(connection, cursor="Y3Vyc29yOjEw", total_collected=20)

    assert db.get_collection_state(connection) == {
        "cursor": "Y3Vyc29yOjEw",
        "total_collected": 20,
    }


def test_upsert_repositories_inserts_new_rows():
    connection = make_connection()
    db.init_db(connection)

    db.upsert_repositories(connection, [sample_repository()])

    assert db.count_repositories(connection) == 1


def test_upsert_repositories_updates_existing_row_in_place():
    connection = make_connection()
    db.init_db(connection)
    db.upsert_repositories(connection, [sample_repository(stargazer_count=100)])

    db.upsert_repositories(connection, [sample_repository(stargazer_count=200)])

    assert db.count_repositories(connection) == 1
    stored_stargazer_count = connection.execute(
        "SELECT stargazer_count FROM repositories WHERE id = 'R_1'"
    ).fetchone()[0]
    assert stored_stargazer_count == 200


def test_upsert_repositories_handles_multiple_distinct_rows():
    connection = make_connection()
    db.init_db(connection)

    db.upsert_repositories(
        connection,
        [sample_repository(repository_id="R_1"), sample_repository(repository_id="R_2")],
    )

    assert db.count_repositories(connection) == 2


def test_get_connection_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "repos.db"

    connection = db.get_connection(db_path)
    connection.close()

    assert db_path.parent.exists()

import sqlite3

from src import storage


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
        "is_fork": 0,
        "is_archived": 0,
        "primary_language": "Python",
        "merged_pull_requests": 5,
        "releases_count": 2,
        "open_issues": 1,
        "closed_issues": 9,
        "raw_json": "{}",
    }


def test_init_db_creates_default_collection_state():
    connection = make_connection()

    storage.init_db(connection)

    assert storage.get_collection_state(connection) == {"cursor": None, "total_collected": 0}


def test_init_db_does_not_reset_existing_state():
    connection = make_connection()
    storage.init_db(connection)
    storage.save_collection_state(connection, cursor="abc", total_collected=10)

    storage.init_db(connection)

    assert storage.get_collection_state(connection) == {"cursor": "abc", "total_collected": 10}


def test_save_and_get_collection_state_roundtrip():
    connection = make_connection()
    storage.init_db(connection)

    storage.save_collection_state(connection, cursor="Y3Vyc29yOjEw", total_collected=20)

    assert storage.get_collection_state(connection) == {
        "cursor": "Y3Vyc29yOjEw",
        "total_collected": 20,
    }


def test_upsert_repositories_inserts_new_rows():
    connection = make_connection()
    storage.init_db(connection)

    storage.upsert_repositories(connection, [sample_repository()])

    assert storage.count_repositories(connection) == 1


def test_upsert_repositories_updates_existing_row_in_place():
    connection = make_connection()
    storage.init_db(connection)
    storage.upsert_repositories(connection, [sample_repository(stargazer_count=100)])

    storage.upsert_repositories(connection, [sample_repository(stargazer_count=200)])

    assert storage.count_repositories(connection) == 1
    stored_stargazer_count = connection.execute(
        "SELECT stargazer_count FROM repositories WHERE id = 'R_1'"
    ).fetchone()[0]
    assert stored_stargazer_count == 200


def test_upsert_repositories_handles_multiple_distinct_rows():
    connection = make_connection()
    storage.init_db(connection)

    storage.upsert_repositories(
        connection,
        [sample_repository(repository_id="R_1"), sample_repository(repository_id="R_2")],
    )

    assert storage.count_repositories(connection) == 2


def test_init_db_migrates_missing_columns_on_pre_existing_table():
    """Reproduz o cenário real: um repos.db criado antes de is_fork/is_archived
    existirem, com dados já persistidos, precisa ganhar as colunas novas sem
    perder as linhas existentes."""
    connection = make_connection()
    connection.execute(
        """
        CREATE TABLE repositories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner TEXT NOT NULL,
            stargazer_count INTEGER,
            created_at TEXT,
            pushed_at TEXT,
            primary_language TEXT,
            merged_pull_requests INTEGER,
            releases_count INTEGER,
            open_issues INTEGER,
            closed_issues INTEGER,
            raw_json TEXT,
            collected_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    connection.execute(
        "INSERT INTO repositories (id, name, owner, stargazer_count) VALUES "
        "('R_1', 'example', 'octocat', 100)"
    )
    connection.commit()

    storage.init_db(connection)

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(repositories)").fetchall()
    }
    assert {"is_fork", "is_archived"}.issubset(columns)
    assert storage.count_repositories(connection) == 1
    is_fork, is_archived = connection.execute(
        "SELECT is_fork, is_archived FROM repositories WHERE id = 'R_1'"
    ).fetchone()
    assert is_fork is None
    assert is_archived is None


def test_init_db_migration_is_idempotent():
    connection = make_connection()
    storage.init_db(connection)

    storage.init_db(connection)

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(repositories)").fetchall()
    }
    assert {"is_fork", "is_archived"}.issubset(columns)


def test_get_connection_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "repos.db"

    connection = storage.get_connection(db_path)
    connection.close()

    assert db_path.parent.exists()

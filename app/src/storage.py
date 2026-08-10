import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "repos.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    stargazer_count INTEGER,
    created_at TEXT,
    pushed_at TEXT,
    is_fork INTEGER,
    is_archived INTEGER,
    primary_language TEXT,
    merged_pull_requests INTEGER,
    releases_count INTEGER,
    open_issues INTEGER,
    closed_issues INTEGER,
    raw_json TEXT,
    collected_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS collection_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    cursor TEXT,
    total_collected INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection(db_path=DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    return connection


def _migrate_missing_columns(connection):
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(repositories)").fetchall()
    }
    for column in ("is_fork", "is_archived"):
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE repositories ADD COLUMN {column} INTEGER")


def init_db(connection):
    connection.executescript(SCHEMA)
    _migrate_missing_columns(connection)
    connection.execute(
        "INSERT OR IGNORE INTO collection_state (id, cursor, total_collected) VALUES (1, NULL, 0)"
    )
    connection.commit()


def get_collection_state(connection):
    cursor, total_collected = connection.execute(
        "SELECT cursor, total_collected FROM collection_state WHERE id = 1"
    ).fetchone()
    return {"cursor": cursor, "total_collected": total_collected}


def save_collection_state(connection, cursor, total_collected):
    connection.execute(
        """
        UPDATE collection_state
        SET cursor = ?, total_collected = ?, updated_at = datetime('now')
        WHERE id = 1
        """,
        (cursor, total_collected),
    )
    connection.commit()


def upsert_repositories(connection, repos):
    connection.executemany(
        """
        INSERT INTO repositories (
            id, name, owner, stargazer_count, created_at, pushed_at,
            is_fork, is_archived, primary_language, merged_pull_requests,
            releases_count, open_issues, closed_issues, raw_json
        ) VALUES (
            :id, :name, :owner, :stargazer_count, :created_at, :pushed_at,
            :is_fork, :is_archived, :primary_language, :merged_pull_requests,
            :releases_count, :open_issues, :closed_issues, :raw_json
        )
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            owner = excluded.owner,
            stargazer_count = excluded.stargazer_count,
            created_at = excluded.created_at,
            pushed_at = excluded.pushed_at,
            is_fork = excluded.is_fork,
            is_archived = excluded.is_archived,
            primary_language = excluded.primary_language,
            merged_pull_requests = excluded.merged_pull_requests,
            releases_count = excluded.releases_count,
            open_issues = excluded.open_issues,
            closed_issues = excluded.closed_issues,
            raw_json = excluded.raw_json
        """,
        repos,
    )
    connection.commit()


def count_repositories(connection):
    return connection.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]


EXPORT_COLUMNS = [
    "id",
    "name",
    "owner",
    "stargazer_count",
    "created_at",
    "pushed_at",
    "is_fork",
    "is_archived",
    "primary_language",
    "merged_pull_requests",
    "releases_count",
    "open_issues",
    "closed_issues",
    "collected_at",
]


def iter_repositories_for_export(connection):
    columns_sql = ", ".join(EXPORT_COLUMNS)
    cursor = connection.execute(
        f"SELECT {columns_sql} FROM repositories ORDER BY stargazer_count DESC"
    )
    for row in cursor:
        yield dict(zip(EXPORT_COLUMNS, row))

import psycopg2
from psycopg2.extras import execute_values

from src.config import get_supabase_connection_params

REPOSITORIES_TABLE = "repositories"
COLLECTION_STATE_TABLE = "collection_state"

_REPOSITORY_COLUMNS = (
    "id",
    "name",
    "owner",
    "stargazer_count",
    "fork_count",
    "created_at",
    "pushed_at",
    "is_fork",
    "is_archived",
    "primary_language",
    "merged_pull_requests",
    "releases_count",
    "open_issues",
    "closed_issues",
    "raw_json",
)


def get_connection(connection_params=None):
    if connection_params is None:
        connection_params = get_supabase_connection_params()
    return psycopg2.connect(**connection_params)


def init_db(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {REPOSITORIES_TABLE} (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner TEXT NOT NULL,
                stargazer_count INTEGER,
                fork_count INTEGER,
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
                collected_at TEXT NOT NULL DEFAULT (
                    to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')
                )
            )
            """
        )
        cursor.execute(
            f"ALTER TABLE {REPOSITORIES_TABLE} ADD COLUMN IF NOT EXISTS fork_count INTEGER"
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {COLLECTION_STATE_TABLE} (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cursor TEXT,
                total_collected INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (
                    to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')
                )
            )
            """
        )
        cursor.execute(
            f"INSERT INTO {COLLECTION_STATE_TABLE} (id, cursor, total_collected) "
            "VALUES (1, NULL, 0) ON CONFLICT (id) DO NOTHING"
        )
    connection.commit()


def get_collection_state(connection):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT cursor, total_collected FROM {COLLECTION_STATE_TABLE} WHERE id = 1")
        cursor_value, total_collected = cursor.fetchone()
    return {"cursor": cursor_value, "total_collected": total_collected}


def _save_collection_state_row(cursor, collection_cursor, total_collected):
    cursor.execute(
        f"""
        UPDATE {COLLECTION_STATE_TABLE}
        SET cursor = %(cursor)s,
            total_collected = %(total_collected)s,
            updated_at = to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')
        WHERE id = 1
        """,
        {"cursor": collection_cursor, "total_collected": total_collected},
    )


def save_collection_state(connection, cursor, total_collected):
    with connection.cursor() as db_cursor:
        _save_collection_state_row(db_cursor, cursor, total_collected)
    connection.commit()


def _upsert_repositories_rows(cursor, repos):
    if not repos:
        return
    values = [tuple(repo[column] for column in _REPOSITORY_COLUMNS) for repo in repos]
    execute_values(
        cursor,
        f"""
        INSERT INTO {REPOSITORIES_TABLE} (
            id, name, owner, stargazer_count, fork_count, created_at, pushed_at,
            is_fork, is_archived, primary_language, merged_pull_requests,
            releases_count, open_issues, closed_issues, raw_json
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            owner = EXCLUDED.owner,
            stargazer_count = EXCLUDED.stargazer_count,
            fork_count = EXCLUDED.fork_count,
            created_at = EXCLUDED.created_at,
            pushed_at = EXCLUDED.pushed_at,
            is_fork = EXCLUDED.is_fork,
            is_archived = EXCLUDED.is_archived,
            primary_language = EXCLUDED.primary_language,
            merged_pull_requests = EXCLUDED.merged_pull_requests,
            releases_count = EXCLUDED.releases_count,
            open_issues = EXCLUDED.open_issues,
            closed_issues = EXCLUDED.closed_issues,
            raw_json = EXCLUDED.raw_json,
            collected_at = to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')
        """,
        values,
        page_size=len(values),
    )


def upsert_repositories(connection, repos):
    with connection.cursor() as cursor:
        _upsert_repositories_rows(cursor, repos)
    connection.commit()


def upsert_page_and_advance_cursor(connection, repos, cursor, total_collected):
    with connection:
        with connection.cursor() as db_cursor:
            _upsert_repositories_rows(db_cursor, repos)
            _save_collection_state_row(db_cursor, cursor, total_collected)


def count_repositories(connection):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {REPOSITORIES_TABLE}")
        return cursor.fetchone()[0]


EXPORT_COLUMNS = [
    "id",
    "name",
    "owner",
    "stargazer_count",
    "fork_count",
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
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {columns_sql} FROM {REPOSITORIES_TABLE} ORDER BY stargazer_count DESC")
        for row in cursor:
            yield dict(zip(EXPORT_COLUMNS, row))

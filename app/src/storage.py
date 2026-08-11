import psycopg2

from src.config import get_supabase_connection_params

# Nomes de tabela module-level (não constantes fixas em SQL pré-formatado) para
# que os testes possam apontar para tabelas isoladas (test_repositories,
# test_collection_state) via monkeypatch, sem tocar nos dados reais do time —
# ver tests/conftest.py.
REPOSITORIES_TABLE = "repositories"
COLLECTION_STATE_TABLE = "collection_state"


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


def save_collection_state(connection, cursor, total_collected):
    with connection.cursor() as db_cursor:
        db_cursor.execute(
            f"""
            UPDATE {COLLECTION_STATE_TABLE}
            SET cursor = %(cursor)s,
                total_collected = %(total_collected)s,
                updated_at = to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')
            WHERE id = 1
            """,
            {"cursor": cursor, "total_collected": total_collected},
        )
    connection.commit()


def upsert_repositories(connection, repos):
    with connection.cursor() as cursor:
        cursor.executemany(
            f"""
            INSERT INTO {REPOSITORIES_TABLE} (
                id, name, owner, stargazer_count, created_at, pushed_at,
                is_fork, is_archived, primary_language, merged_pull_requests,
                releases_count, open_issues, closed_issues, raw_json
            ) VALUES (
                %(id)s, %(name)s, %(owner)s, %(stargazer_count)s, %(created_at)s, %(pushed_at)s,
                %(is_fork)s, %(is_archived)s, %(primary_language)s, %(merged_pull_requests)s,
                %(releases_count)s, %(open_issues)s, %(closed_issues)s, %(raw_json)s
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                owner = EXCLUDED.owner,
                stargazer_count = EXCLUDED.stargazer_count,
                created_at = EXCLUDED.created_at,
                pushed_at = EXCLUDED.pushed_at,
                is_fork = EXCLUDED.is_fork,
                is_archived = EXCLUDED.is_archived,
                primary_language = EXCLUDED.primary_language,
                merged_pull_requests = EXCLUDED.merged_pull_requests,
                releases_count = EXCLUDED.releases_count,
                open_issues = EXCLUDED.open_issues,
                closed_issues = EXCLUDED.closed_issues,
                raw_json = EXCLUDED.raw_json
            """,
            repos,
        )
    connection.commit()


def count_repositories(connection):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {REPOSITORIES_TABLE}")
        return cursor.fetchone()[0]


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
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {columns_sql} FROM {REPOSITORIES_TABLE} ORDER BY stargazer_count DESC")
        for row in cursor:
            yield dict(zip(EXPORT_COLUMNS, row))

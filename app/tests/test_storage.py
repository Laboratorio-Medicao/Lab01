from src import storage
from tests.conftest import requires_supabase


def sample_repository(repository_id="R_1", stargazer_count=100):
    return {
        "id": repository_id,
        "name": "example",
        "owner": "octocat",
        "stargazer_count": stargazer_count,
        "fork_count": 10,
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


@requires_supabase
def test_init_db_creates_default_collection_state(db_connection):
    storage.init_db(db_connection)

    assert storage.get_collection_state(db_connection) == {"cursor": None, "total_collected": 0}


@requires_supabase
def test_init_db_does_not_reset_existing_state(db_connection):
    storage.init_db(db_connection)
    storage.save_collection_state(db_connection, cursor="abc", total_collected=10)

    storage.init_db(db_connection)

    assert storage.get_collection_state(db_connection) == {"cursor": "abc", "total_collected": 10}


@requires_supabase
def test_save_and_get_collection_state_roundtrip(db_connection):
    storage.init_db(db_connection)

    storage.save_collection_state(db_connection, cursor="Y3Vyc29yOjEw", total_collected=20)

    assert storage.get_collection_state(db_connection) == {
        "cursor": "Y3Vyc29yOjEw",
        "total_collected": 20,
    }


@requires_supabase
def test_upsert_repositories_inserts_new_rows(db_connection):
    storage.init_db(db_connection)

    storage.upsert_repositories(db_connection, [sample_repository()])

    assert storage.count_repositories(db_connection) == 1


@requires_supabase
def test_upsert_repositories_updates_existing_row_in_place(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(db_connection, [sample_repository(stargazer_count=100)])

    storage.upsert_repositories(db_connection, [sample_repository(stargazer_count=200)])

    assert storage.count_repositories(db_connection) == 1
    with db_connection.cursor() as cursor:
        cursor.execute(
            f"SELECT stargazer_count FROM {storage.REPOSITORIES_TABLE} WHERE id = 'R_1'"
        )
        stored_stargazer_count = cursor.fetchone()[0]
    assert stored_stargazer_count == 200


@requires_supabase
def test_upsert_repositories_refreshes_collected_at_on_conflict(db_connection):
    storage.init_db(db_connection)
    storage.upsert_repositories(db_connection, [sample_repository()])

    with db_connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {storage.REPOSITORIES_TABLE} SET collected_at = '2020-01-01 00:00:00' "
            "WHERE id = 'R_1'"
        )
    db_connection.commit()

    storage.upsert_repositories(db_connection, [sample_repository(stargazer_count=200)])

    with db_connection.cursor() as cursor:
        cursor.execute(
            f"SELECT collected_at FROM {storage.REPOSITORIES_TABLE} WHERE id = 'R_1'"
        )
        collected_at = cursor.fetchone()[0]
    assert collected_at != "2020-01-01 00:00:00"


@requires_supabase
def test_upsert_repositories_handles_multiple_distinct_rows(db_connection):
    storage.init_db(db_connection)

    storage.upsert_repositories(
        db_connection,
        [sample_repository(repository_id="R_1"), sample_repository(repository_id="R_2")],
    )

    assert storage.count_repositories(db_connection) == 2


@requires_supabase
def test_get_repository_integrity_stats_returns_total_and_distinct_ids(db_connection):
    storage.init_db(db_connection)

    storage.upsert_repositories(
        db_connection,
        [sample_repository(repository_id="R_1"), sample_repository(repository_id="R_2")],
    )
    storage.upsert_repositories(
        db_connection,
        [sample_repository(repository_id="R_2", stargazer_count=999)],
    )

    stats = storage.get_repository_integrity_stats(db_connection)
    assert stats == {"total_rows": 2, "distinct_ids": 2}

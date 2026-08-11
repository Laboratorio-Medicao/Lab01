import csv

from src import storage
from src.export import export_to_csv
from tests.conftest import requires_supabase


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


@requires_supabase
def test_export_to_csv_writes_all_repositories_ordered_by_stars(db_connection, tmp_path):
    storage.init_db(db_connection)
    storage.upsert_repositories(
        db_connection,
        [
            sample_repository("R_1", stargazer_count=100),
            sample_repository("R_2", stargazer_count=200),
        ],
    )
    output_path = tmp_path / "repos.csv"

    rows_written = export_to_csv(db_connection, output_path=output_path)

    assert rows_written == 2
    with output_path.open(encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert [row["id"] for row in rows] == ["R_2", "R_1"]
    assert "raw_json" not in rows[0]


@requires_supabase
def test_export_to_csv_creates_parent_directory(db_connection, tmp_path):
    storage.init_db(db_connection)
    output_path = tmp_path / "nested" / "repos.csv"

    export_to_csv(db_connection, output_path=output_path)

    assert output_path.exists()

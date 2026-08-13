import csv
import logging
from pathlib import Path

from src.metrics import (
    compute_age_years,
    compute_closed_issues_ratio,
    compute_update_recency_years,
)
from src.storage import EXPORT_COLUMNS, get_connection, iter_repositories_for_export

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "repos.csv"

COMPUTED_METRIC_COLUMNS = ["age_years", "update_recency_years", "closed_issues_ratio"]
EXPORT_FIELDNAMES = EXPORT_COLUMNS + COMPUTED_METRIC_COLUMNS


def _with_computed_metrics(row):
    row = dict(row)
    row["age_years"] = compute_age_years(row["created_at"], row["collected_at"])
    row["update_recency_years"] = compute_update_recency_years(
        row["pushed_at"], row["collected_at"]
    )
    row["closed_issues_ratio"] = compute_closed_issues_ratio(
        row["open_issues"], row["closed_issues"]
    )
    return row


def export_to_csv(connection, output_path=OUTPUT_PATH):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=EXPORT_FIELDNAMES)
        writer.writeheader()
        for row in iter_repositories_for_export(connection):
            writer.writerow(_with_computed_metrics(row))
            rows_written += 1
    return rows_written


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    connection = get_connection()
    try:
        rows_written = export_to_csv(connection)
    finally:
        connection.close()

    logger.info("export concluído: %s repositórios salvos em %s", rows_written, OUTPUT_PATH)


if __name__ == "__main__":
    main()

"""Exporta os repositórios coletados em data/repos.db para data/repos.csv
(entregável exigido — ver README.md).

Uso:
    python src/export.py
"""

import csv
import logging
from pathlib import Path

from src.storage import EXPORT_COLUMNS, get_connection, iter_repositories_for_export

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "repos.csv"


def export_to_csv(connection, output_path=OUTPUT_PATH):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for row in iter_repositories_for_export(connection):
            writer.writerow(row)
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

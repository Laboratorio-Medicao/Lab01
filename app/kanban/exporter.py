import csv
from datetime import date
from pathlib import Path

CSV_FIELDNAMES = ["number", "title", "status", "assignees", "labels"]

ASSIGNEES_SEPARATOR = "|"
LABELS_SEPARATOR = "|"


def _item_to_row(item):
    return {
        "number": "" if item.number is None else item.number,
        "title": item.title,
        "status": item.status,
        "assignees": ASSIGNEES_SEPARATOR.join(item.assignees),
        "labels": LABELS_SEPARATOR.join(item.labels),
    }


class CsvExporter:
    def __init__(self, output_dir):
        self._output_dir = Path(output_dir)

    def export(self, items, snapshot_date=None):
        if snapshot_date is None:
            snapshot_date = date.today()

        output_path = self._output_dir / f"kanban-snapshot-{snapshot_date.isoformat()}.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for item in items:
                writer.writerow(_item_to_row(item))

        return output_path

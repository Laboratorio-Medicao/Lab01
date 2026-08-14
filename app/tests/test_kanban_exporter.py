import csv
from datetime import date
from pathlib import Path

import pytest

from kanban.exporter import CSV_FIELDNAMES, CsvExporter, _item_to_row
from kanban.models import KanbanItem


def make_item(number=1, title="Foo", status="Done", assignees=("alice",), labels=("bug",)):
    return KanbanItem(number=number, title=title, status=status, assignees=assignees, labels=labels)


# --- _item_to_row ---

def test_item_to_row_maps_all_fields():
    item = make_item(number=7, title="Minha issue", status="In progress", assignees=("alice", "bob"), labels=("bug",))
    row = _item_to_row(item)

    assert row["number"] == 7
    assert row["title"] == "Minha issue"
    assert row["status"] == "In progress"
    assert row["assignees"] == "alice|bob"
    assert row["labels"] == "bug"


def test_item_to_row_uses_empty_string_for_missing_number():
    item = make_item(number=None)
    row = _item_to_row(item)

    assert row["number"] == ""


def test_item_to_row_joins_multiple_labels():
    item = make_item(labels=("bug", "enhancement", "sprint-s02"))
    row = _item_to_row(item)

    assert row["labels"] == "bug|enhancement|sprint-s02"


def test_item_to_row_empty_assignees_and_labels():
    item = make_item(assignees=(), labels=())
    row = _item_to_row(item)

    assert row["assignees"] == ""
    assert row["labels"] == ""


# --- CsvExporter.export ---

def test_export_creates_file_with_correct_name(tmp_path):
    exporter = CsvExporter(tmp_path)
    snapshot_date = date(2024, 6, 15)

    output_path = exporter.export([], snapshot_date=snapshot_date)

    assert output_path == tmp_path / "kanban-snapshot-2024-06-15.csv"
    assert output_path.exists()


def test_export_writes_header_and_rows(tmp_path):
    items = [
        make_item(number=1, title="Issue 1", status="Done", assignees=("alice",), labels=("bug",)),
        make_item(number=2, title="Issue 2", status="In progress", assignees=(), labels=()),
    ]
    exporter = CsvExporter(tmp_path)
    output_path = exporter.export(items, snapshot_date=date(2024, 6, 15))

    with output_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert reader.fieldnames == CSV_FIELDNAMES
    assert len(rows) == 2
    assert rows[0]["number"] == "1"
    assert rows[0]["title"] == "Issue 1"
    assert rows[0]["assignees"] == "alice"
    assert rows[1]["status"] == "In progress"


def test_export_creates_output_dir_if_missing(tmp_path):
    nested_dir = tmp_path / "a" / "b" / "snapshots"
    exporter = CsvExporter(nested_dir)

    output_path = exporter.export([], snapshot_date=date(2024, 1, 1))

    assert output_path.exists()


def test_export_uses_today_when_no_date_given(tmp_path):
    exporter = CsvExporter(tmp_path)
    output_path = exporter.export([])

    expected_name = f"kanban-snapshot-{date.today().isoformat()}.csv"
    assert output_path.name == expected_name


def test_export_returns_zero_rows_for_empty_items(tmp_path):
    exporter = CsvExporter(tmp_path)
    output_path = exporter.export([], snapshot_date=date(2024, 1, 1))

    with output_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows == []

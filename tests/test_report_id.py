from pathlib import Path

from report_id import ReportId


def test_names_derive_from_date_and_scope():
    report = ReportId("2025-12-31", "global")

    assert report.markdown_name == "2025-12-31.global.md"
    assert report.csv_name == "2025-12-31.global.csv"
    assert report.json_name == "2025-12-31.global.json"
    assert report.telegram_snapshot_name == "2025-12-31.telegram.global.txt"
    assert report.telegram_public_name == "2025-12-31.global.txt"


def test_labels_and_title():
    assert ReportId("2025-12-31", "global").title == "Global Assets Weekly Report - 2025-12-31"
    assert ReportId("2025-12-31", "software").label == "Software Companies"


def test_from_path_reads_date_and_scope():
    assert ReportId.from_path(Path("reports/2025-12-31.global.md")) == ReportId("2025-12-31", "global")


def test_from_path_rejects_other_files():
    assert ReportId.from_path(Path("notes.md")) is None
    assert ReportId.from_path(Path("bad-date.global.md")) is None

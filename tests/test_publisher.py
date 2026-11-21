import json

import pytest

import publisher
from metrics import calculate_metrics, save_snapshot_csv, save_snapshot_json
from render import render_report


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point the publisher at empty reports/, snapshots/ and public/ folders."""
    reports = tmp_path / "reports"
    snapshots = tmp_path / "snapshots"
    reports.mkdir()
    snapshots.mkdir()
    monkeypatch.setattr(publisher, "REPORTS_DIR", reports)
    monkeypatch.setattr(publisher, "SNAPSHOTS_DIR", snapshots)
    monkeypatch.setattr(publisher, "PUBLIC_DIR", tmp_path / "public")
    return tmp_path


def write_report_files(workspace, date, scope, ranked, llm_sections):
    metrics = calculate_metrics(ranked)
    report = render_report(date, scope, ranked, metrics, ([], [], []), llm_sections)
    (workspace / "reports" / f"{date}.{scope}.md").write_text(report, encoding="utf-8")
    save_snapshot_csv(ranked, workspace / "snapshots" / f"{date}.{scope}.csv")
    save_snapshot_json(ranked, metrics, workspace / "snapshots" / f"{date}.{scope}.json")


def read_manifest(workspace):
    return json.loads((workspace / "public" / "manifest.json").read_text(encoding="utf-8"))


def test_excerpt_strips_markdown_and_newlines():
    assert publisher.make_excerpt("**Bold** start\n\nnext line") == "Bold start next line"


def test_excerpt_is_cut_at_a_word_boundary():
    assert publisher.make_excerpt("one two three four five", max_chars=15) == "one two three…"


def test_all_reports_are_listed_newest_first(tmp_path):
    for name in ["2025-12-24.global.md", "2025-12-31.global.md", "notes.md", "bad-date.global.md"]:
        (tmp_path / name).write_text("x", encoding="utf-8")

    reports = publisher.get_all_reports(tmp_path)

    assert [(r["date"], r["scope"]) for r in reports] == [
        ("2025-12-31", "global"),
        ("2025-12-24", "global"),
    ]


def test_build_public_publishes_report_data_manifest_and_index(workspace, ranked, llm_sections):
    write_report_files(workspace, "2025-12-31", "global", ranked, llm_sections)

    assert publisher.build_public("2025-12-31", ["global"]) is True

    public = workspace / "public"
    assert (public / "reports" / "2025-12-31.global.md").exists()
    data = json.loads((public / "data" / "2025-12-31.global.json").read_text(encoding="utf-8"))
    assert data["top_n"] == 6
    assert data["metrics"]["total_market_cap_top_n"] == 1e12
    assert data["ranking"][0]["ticker"] == "AAA"

    manifest = read_manifest(workspace)
    assert manifest["latest"]["global"]["date"] == "2025-12-31"
    entry = manifest["reports"][0]
    assert entry["title"] == "Report Settimanale Asset Globali - 2025-12-31"
    assert entry["summary_excerpt"] == "Summary text."
    assert [a["ticker"] for a in entry["top10"]] == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]

    index = (public / "index.html").read_text(encoding="utf-8")
    assert '<a href="reports/2025-12-31.global.md">' in index


def test_build_public_fails_when_there_is_nothing_to_publish(workspace):
    assert publisher.build_public("2025-12-31", ["global"]) is False


def test_build_public_from_scratch_includes_the_whole_archive(workspace, ranked, llm_sections):
    """CI starts with no public/ folder, so every run must republish past reports."""
    write_report_files(workspace, "2025-12-24", "global", ranked, llm_sections)
    write_report_files(workspace, "2025-12-24", "software", ranked, llm_sections)
    write_report_files(workspace, "2025-12-31", "global", ranked, llm_sections)

    assert publisher.build_public("2025-12-31", ["global"]) is True

    published = [(r["date"], r["scope"]) for r in read_manifest(workspace)["reports"]]
    assert sorted(published) == [
        ("2025-12-24", "global"),
        ("2025-12-24", "software"),
        ("2025-12-31", "global"),
    ]
    assert (workspace / "public" / "data" / "2025-12-24.software.json").exists()

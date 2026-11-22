import pytest

import regenerate
from metrics import calculate_metrics
from regenerate import Folders, find_reports, read_commentary, regenerate_all
from render import render_report
from report_id import ReportId
from snapshot import save_snapshot_csv

TODAY = "2026-11-22"
LLM = {"executive_summary": "LLM summary.", "strategic_reflection": "LLM reflection.", "implications": "LLM implications."}


@pytest.fixture
def folders(tmp_path):
    made = Folders(tmp_path / "reports", tmp_path / "snapshots", tmp_path / "rag")
    for folder in (made.reports, made.snapshots, made.rag):
        folder.mkdir()
    return made


@pytest.fixture
def llm(monkeypatch):
    """Replace the LLM: with a key it answers LLM (or `answer`), recording each request."""
    calls = []

    def install(answer=None):
        real = regenerate.generate_llm_sections

        def fake(input_data, rag_context, scope, api_key):
            if not api_key:
                return real(input_data, rag_context, scope, None)
            calls.append((input_data["date"], scope, rag_context))
            return answer or LLM

        monkeypatch.setattr(regenerate, "generate_llm_sections", fake)
        return calls

    return install


def placeholders(ranked):
    data = {"assets": [a.to_dict() for a in ranked], "metrics": calculate_metrics(ranked)}
    return regenerate.generate_llm_sections(data, "", "global", None)


def add_report(folders, date, ranked, content, scope="global"):
    report = ReportId(date, scope)
    save_snapshot_csv(ranked, folders.snapshots / report.csv_name)
    (folders.reports / report.markdown_name).write_text(content, encoding="utf-8")
    return report


def rendered(date, ranked, sections, scope="global", commentary_date=None):
    return render_report(
        date, scope, ranked, calculate_metrics(ranked), ([], [], []), sections, commentary_date
    )


def read(folders, report):
    return (folders.reports / report.markdown_name).read_text(encoding="utf-8")


def test_commentary_is_read_back_from_a_rendered_report(ranked, llm_sections):
    assert read_commentary(rendered("2025-12-31", ranked, llm_sections)) == llm_sections


def test_commentary_is_read_from_the_legacy_headings():
    old = "## Executive Summary\n\nS\n\n## Riflessione Strategica\n\nR\n\n## Implicazioni\n\nI\n\n---\n\n*Not financial advice. For informational purposes only.*\n"

    assert read_commentary(old) == {"executive_summary": "S", "strategic_reflection": "R", "implications": "I"}


def test_reports_are_found_oldest_first_within_scope_and_dates(tmp_path):
    for name in ["2025-12-31.software.md", "2025-12-24.global.md", "2025-12-31.global.md", "2025-12-17.global.md", "notes.md"]:
        (tmp_path / name).write_text("x", encoding="utf-8")

    found = find_reports(tmp_path, ["global", "software"], "2025-12-24", "9999-99-99")

    assert [r.stem for r in found] == ["2025-12-24.global", "2025-12-31.global", "2025-12-31.software"]
    assert [r.stem for r in find_reports(tmp_path, ["global"], "0000-00-00", "2025-12-17")] == ["2025-12-17.global"]


def test_report_with_commentary_is_rendered_again_without_calling_the_llm(folders, ranked, llm_sections, llm):
    calls = llm()
    old_format = rendered("2025-12-31", ranked, llm_sections).replace("## Ranking", "## Classifica")
    report = add_report(folders, "2025-12-31", ranked, old_format)

    assert regenerate_all([report], folders, "key", TODAY) == []

    assert calls == []
    assert read(folders, report) == rendered("2025-12-31", ranked, llm_sections)


def test_report_with_placeholders_gets_commentary_dated_today(folders, ranked, llm):
    calls = llm()
    report = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, placeholders(ranked)))

    assert regenerate_all([report], folders, "key", TODAY) == []

    assert [(date, scope) for date, scope, _ in calls] == [("2025-12-31", "global")]
    assert read(folders, report) == rendered("2025-12-31", ranked, LLM, commentary_date=TODAY)


def test_regenerating_twice_keeps_the_commentary_and_its_date(folders, ranked, llm):
    calls = llm()
    report = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, placeholders(ranked)))

    regenerate_all([report], folders, "key", TODAY)
    regenerate_all([report], folders, "key", "2027-01-01")

    assert len(calls) == 1
    assert "commentary_date: 2026-11-22" in read(folders, report)


def test_each_report_gets_the_regenerated_commentary_of_the_earlier_ones(folders, ranked, llm):
    calls = llm()
    first = add_report(folders, "2025-12-24", ranked, rendered("2025-12-24", ranked, placeholders(ranked)))
    second = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, placeholders(ranked)))

    regenerate_all([first, second], folders, "key", TODAY)

    assert calls[0][2] == ""
    assert "## Report 2025-12-24" in calls[1][2]
    assert "LLM reflection." in calls[1][2]


def test_week_over_week_changes_are_recomputed(folders, ranked, llm_sections, llm):
    llm()
    add_report(folders, "2025-12-24", ranked[:5], rendered("2025-12-24", ranked[:5], llm_sections))
    report = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, llm_sections))

    regenerate_all([report], folders, "key", TODAY)

    assert "**New Entries**: FFF" in read(folders, report)


def test_without_a_key_placeholders_stay_and_the_run_is_complete(folders, ranked, llm):
    llm()
    report = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, placeholders(ranked)))

    assert regenerate_all([report], folders, None, TODAY) == []

    assert "will be enhanced with AI-generated" in read(folders, report)
    assert "commentary_date" not in read(folders, report)


def test_failed_llm_call_leaves_the_report_incomplete(folders, ranked, llm):
    llm(answer=placeholders(ranked))
    report = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, placeholders(ranked)))

    assert regenerate_all([report], folders, "key", TODAY) == [report]


def test_report_without_a_snapshot_is_left_untouched(folders, llm):
    llm()
    report = ReportId("2025-12-31", "global")
    (folders.reports / report.markdown_name).write_text("original", encoding="utf-8")

    assert regenerate_all([report], folders, "key", TODAY) == [report]
    assert read(folders, report) == "original"


def test_telegram_text_and_rag_file_are_refreshed(folders, ranked, llm):
    llm()
    report = add_report(folders, "2025-12-31", ranked, rendered("2025-12-31", ranked, placeholders(ranked)))

    regenerate_all([report], folders, "key", TODAY)

    telegram = (folders.snapshots / report.telegram_snapshot_name).read_text(encoding="utf-8")
    assert "LLM summary." in telegram
    assert "LLM implications." in (folders.rag / "rag_context_global.txt").read_text(encoding="utf-8")

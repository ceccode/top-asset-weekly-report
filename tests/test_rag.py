from llm import generate_llm_sections
from metrics import calculate_metrics
from rag import (
    check_rag_freshness,
    ensure_rag_context,
    extract_rag_context,
    extract_section,
    get_latest_report_date,
    get_recent_reports,
    truncate_to_max_words,
)
from render import render_report


def write_report(reports_dir, date, scope="global", summary="Summary of the week."):
    path = reports_dir / f"{date}.{scope}.md"
    path.write_text(
        f"# Title\n\n## Executive Summary\n\n{summary}\n\n## Classifica\n\ntable\n",
        encoding="utf-8",
    )
    return path


def test_extract_section_returns_its_text():
    assert extract_section("## Implicazioni\n\nbody\n\n## Next\n", "Implicazioni") == "body"


def test_extract_section_ignores_todo_and_missing_sections():
    assert extract_section("## Implicazioni\n\nTODO\n", "Implicazioni") is None
    assert extract_section("## Other\n\nbody\n", "Implicazioni") is None


def test_recent_reports_are_earlier_ones_newest_first(tmp_path):
    for date in ["2025-12-10", "2025-12-17", "2025-12-24", "2025-12-31"]:
        write_report(tmp_path, date)
    write_report(tmp_path, "2025-12-24", scope="software")

    recent = get_recent_reports(tmp_path, "global", "2025-12-31", k=2)

    assert [p.name for p in recent] == ["2025-12-24.global.md", "2025-12-17.global.md"]


def test_rag_context_quotes_previous_reports(tmp_path):
    write_report(tmp_path, "2025-12-24", summary="Old news.")
    write_report(tmp_path, "2025-12-31", summary="Current news.")

    context = extract_rag_context(tmp_path, "global", "2025-12-31")

    assert context == "## Report 2025-12-24\n\n### Executive Summary\nOld news."


def test_rag_context_is_empty_without_previous_reports(tmp_path):
    assert extract_rag_context(tmp_path, "global", "2025-12-31") == ""


def test_placeholder_sections_stay_out_of_the_rag_context(tmp_path, ranked):
    metrics = calculate_metrics(ranked)
    placeholders = generate_llm_sections(
        {"assets": ranked, "metrics": metrics}, "", "global", api_key=None
    )
    report = render_report("2025-12-24", "global", ranked, metrics, ([], [], []), placeholders)
    (tmp_path / "2025-12-24.global.md").write_text(report, encoding="utf-8")

    assert extract_rag_context(tmp_path, "global", "2025-12-31") == ""


def test_truncate_to_max_words():
    assert truncate_to_max_words("a b c", 5) == "a b c"
    assert truncate_to_max_words("a b c d", 2) == "a b\n\n[...truncated...]"


def test_latest_report_date(tmp_path):
    assert get_latest_report_date(tmp_path, "global") is None

    write_report(tmp_path, "2025-12-24")
    write_report(tmp_path, "2025-12-31")

    assert get_latest_report_date(tmp_path, "global") == "2025-12-31"


def test_rag_is_not_fresh_when_the_file_is_missing(tmp_path):
    assert check_rag_freshness(tmp_path, tmp_path, "global") == (False, "missing")


def test_ensure_rag_context_writes_the_latest_reports(tmp_path):
    reports = tmp_path / "reports"
    rag = tmp_path / "rag"
    reports.mkdir()
    rag.mkdir()
    write_report(reports, "2025-12-31", summary="Current news.")

    path = ensure_rag_context(rag, reports, "global")

    assert path == rag / "rag_context_global.txt"
    assert "## Report 2025-12-31" in path.read_text(encoding="utf-8")
    assert check_rag_freshness(rag, reports, "global") == (True, "up-to-date")

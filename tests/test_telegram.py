from metrics import calculate_metrics, save_snapshot_csv
from render import render_report
from telegram import (
    clean_text_for_telegram,
    generate_telegram_txt,
    load_top_n_from_csv,
    parse_top_n_from_markdown_table,
)


def test_clean_text_strips_markdown():
    assert clean_text_for_telegram("**bold** *it* `code` [link](http://x)") == "bold it code link"


def test_top_n_from_csv(tmp_path, ranked):
    path = tmp_path / "snapshot.csv"
    save_snapshot_csv(ranked, path)

    top = load_top_n_from_csv(path, n=2)

    assert [(a["rank"], a["ticker"]) for a in top] == [("1", "AAA"), ("2", "BBB")]
    assert top[0]["market_cap"] == 500e9


def test_top_n_from_missing_csv_is_empty(tmp_path):
    assert load_top_n_from_csv(tmp_path / "missing.csv") == []


def test_top_n_from_the_report_table_skips_the_header(ranked, llm_sections):
    report = render_report("2025-12-31", "global", ranked, {}, ([], [], []), llm_sections)

    top = parse_top_n_from_markdown_table(report, n=3)

    assert [(a["rank"], a["ticker"]) for a in top] == [("1", "AAA"), ("2", "BBB"), ("3", "CCC")]
    assert top[0]["market_cap_str"] == "$500.00B"


def test_telegram_text_from_report_and_csv(tmp_path, ranked, llm_sections):
    csv_path = tmp_path / "snapshot.csv"
    save_snapshot_csv(ranked, csv_path)
    report = render_report(
        "2025-12-31", "global", ranked, calculate_metrics(ranked), ([], [], []), llm_sections
    )

    lines = generate_telegram_txt("2025-12-31", "global", report, csv_path).splitlines()

    assert lines[0] == "📊 Top Global Assets — 2025-12-31"
    assert "1) Alpha Corp (AAA) — $500.00B" in lines
    assert lines[lines.index("📝 Summary:") + 1] == "Summary text."
    assert lines[lines.index("💡 Insight:") + 1] == "Reflection text."
    assert lines[-1].startswith("⚠️ ")


def test_telegram_text_falls_back_to_the_report_table(tmp_path, ranked, llm_sections):
    report = render_report("2025-12-31", "global", ranked, {}, ([], [], []), llm_sections)

    lines = generate_telegram_txt(
        "2025-12-31", "global", report, tmp_path / "missing.csv"
    ).splitlines()

    assert lines[lines.index("🏆 Top 10:") + 1] == "1) Alpha Corp (AAA) — $500.00B"

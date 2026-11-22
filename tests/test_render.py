from metrics import calculate_metrics
from render import (
    render_changes_section,
    render_metrics_section,
    render_observations,
    render_ranking_table,
    render_report,
)


def mover(rank_delta, cap_delta_pct=0.0):
    return {
        "ticker": "AAA",
        "name": "Alpha Corp",
        "rank_delta": rank_delta,
        "cap_delta_pct": cap_delta_pct,
        "current_rank": 1,
    }


def test_ranking_table_has_one_row_per_asset(ranked):
    lines = render_ranking_table(ranked).splitlines()

    assert lines[0] == "| Rank | Ticker | Name | Type | Market Cap | Currency |"
    assert lines[2] == "| 1 | AAA | Alpha Corp | EQUITY | $500.00B | USD |"
    assert len(lines) == 2 + len(ranked)


def test_ranking_table_without_assets_says_so():
    assert render_ranking_table([]) == "*No data available*\n"


def test_metrics_section(ranked):
    section = render_metrics_section(calculate_metrics(ranked))

    assert "- **Total Market Cap (Top 6)**: $1.00T" in section
    assert "- **Top 5 Concentration**: 98.0%" in section
    assert "- **Top 10 Concentration**: 100.0%" in section


def test_observations_name_the_leader_and_the_type_mix(ranked):
    section = render_observations(ranked, calculate_metrics(ranked))

    assert "- **Alpha Corp** (AAA) leads with $500.00B (50.0% of total)" in section
    assert "- Asset type distribution: EQUITY: 5, ETF: 1" in section


def test_changes_section_without_changes():
    assert render_changes_section([], [], []) == "**New Entries**: None\n**Exits**: None\n"


def test_changes_section_lists_entries_and_exits():
    section = render_changes_section(["AAA", "BBB"], ["ZZZ"], [])

    assert "**New Entries**: AAA, BBB" in section
    assert "**Exits**: ZZZ" in section


def test_mover_line_for_a_rank_gain():
    lines = render_changes_section([], [], [mover(2)]).splitlines()

    assert lines[-1] == "- AAA (Alpha Corp): ↑2 places"


def test_mover_line_for_a_single_position_lost_with_cap_change():
    lines = render_changes_section([], [], [mover(-1, cap_delta_pct=-6.0)]).splitlines()

    assert lines[-1] == "- AAA (Alpha Corp): ↓1 place (-6.0% cap)"


def test_mover_line_when_only_the_cap_changed():
    lines = render_changes_section([], [], [mover(0, cap_delta_pct=6.0)]).splitlines()

    assert lines[-1] == "- AAA (Alpha Corp): rank unchanged (+6.0% cap)"


def test_report_has_frontmatter_and_sections_in_order(ranked, llm_sections):
    report = render_report(
        "2025-12-31", "global", ranked, calculate_metrics(ranked), ([], [], []), llm_sections
    )

    assert report.startswith('---\ntitle: "Global Assets Weekly Report - 2025-12-31"\n')
    headings = [line for line in report.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Executive Summary",
        "## Ranking",
        "## Key Metrics",
        "## Weekly Changes",
        "## Quantitative Observations",
        "## Methodology and Limitations",
        "## Strategic Reflection",
        "## Implications",
    ]
    assert "Summary text." in report


def test_software_report_title(ranked, llm_sections):
    report = render_report("2025-12-31", "software", ranked, {}, ([], [], []), llm_sections)

    assert "# Software Companies Weekly Report - 2025-12-31" in report


def test_report_ends_with_the_disclaimer_footer(ranked, llm_sections):
    report = render_report("2025-12-31", "global", ranked, {}, ([], [], []), llm_sections)

    assert report.endswith("Implications text.\n\n---\n\n*Not financial advice. For informational purposes only.*\n")


def test_commentary_written_on_another_day_is_declared(ranked, llm_sections):
    report = render_report(
        "2025-12-31", "global", ranked, {}, ([], [], []), llm_sections, commentary_date="2026-11-22"
    )

    assert "\ndate: 2025-12-31\n" in report
    assert "\ncommentary_date: 2026-11-22\n" in report


def test_commentary_written_on_the_report_date_is_not_declared(ranked, llm_sections):
    for commentary_date in [None, "2025-12-31"]:
        report = render_report(
            "2025-12-31", "global", ranked, {}, ([], [], []), llm_sections, commentary_date
        )

        assert "commentary_date" not in report

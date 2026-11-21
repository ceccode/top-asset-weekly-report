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

    assert lines[0] == "| Pos. | Ticker | Nome | Tipo | Cap. Mercato | Valuta |"
    assert lines[2] == "| 1 | AAA | Alpha Corp | EQUITY | $500.00B | USD |"
    assert len(lines) == 2 + len(ranked)


def test_ranking_table_without_assets_says_so():
    assert render_ranking_table([]) == "*Nessun dato disponibile*\n"


def test_metrics_section(ranked):
    section = render_metrics_section(calculate_metrics(ranked))

    assert "- **Capitalizzazione Totale (Top 6)**: $1.00T" in section
    assert "- **Concentrazione Top 5**: 98.0%" in section
    assert "- **Concentrazione Top 10**: 100.0%" in section


def test_observations_name_the_leader_and_the_type_mix(ranked):
    section = render_observations(ranked, calculate_metrics(ranked))

    assert "- **Alpha Corp** (AAA) guida con $500.00B (50.0% del totale)" in section
    assert "- Distribuzione per tipologia: EQUITY: 5, ETF: 1" in section


def test_changes_section_without_changes():
    assert render_changes_section([], [], []) == "**Nuove Entrate**: Nessuna\n**Uscite**: Nessuna\n"


def test_changes_section_lists_entries_and_exits():
    section = render_changes_section(["AAA", "BBB"], ["ZZZ"], [])

    assert "**Nuove Entrate**: AAA, BBB" in section
    assert "**Uscite**: ZZZ" in section


def test_mover_line_for_a_rank_gain():
    lines = render_changes_section([], [], [mover(2)]).splitlines()

    assert lines[-1] == "- AAA (Alpha Corp): ↑2 posizioni"


def test_mover_line_for_a_single_position_lost_with_cap_change():
    lines = render_changes_section([], [], [mover(-1, cap_delta_pct=-6.0)]).splitlines()

    assert lines[-1] == "- AAA (Alpha Corp): ↓1 posizione (-6.0% cap)"


def test_mover_line_when_only_the_cap_changed():
    lines = render_changes_section([], [], [mover(0, cap_delta_pct=6.0)]).splitlines()

    assert lines[-1] == "- AAA (Alpha Corp): posizione invariata (+6.0% cap)"


def test_report_has_frontmatter_and_sections_in_order(ranked, llm_sections):
    report = render_report(
        "2025-12-31", "global", ranked, calculate_metrics(ranked), ([], [], []), llm_sections
    )

    assert report.startswith('---\ntitle: "Report Settimanale Asset Globali - 2025-12-31"\n')
    headings = [line for line in report.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Executive Summary",
        "## Classifica",
        "## Metriche Chiave",
        "## Variazioni Settimanali",
        "## Osservazioni Quantitative",
        "## Metodologia e Limitazioni",
        "## Riflessione Strategica",
        "## Implicazioni",
    ]
    assert "Summary text." in report


def test_software_report_title(ranked, llm_sections):
    report = render_report("2025-12-31", "software", ranked, {}, ([], [], []), llm_sections)

    assert "# Report Settimanale Aziende Software - 2025-12-31" in report

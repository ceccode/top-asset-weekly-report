"""Markdown report rendering."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from asset import Asset
from config import DISCLAIMER, DISCLAIMER_SHORT
from llm import SECTION_HEADINGS
from metrics import format_market_cap
from report_id import ReportId

logger = logging.getLogger(__name__)

# Heading of the ranking table, which the Telegram fallback reads back
RANKING_HEADING = "Ranking"

# Closes every report
FOOTER = f"---\n\n*{DISCLAIMER_SHORT}*\n"


def render_frontmatter(
    title: str,
    date: str,
    scope: str,
    commentary_date: Optional[str] = None,
) -> str:
    """
    Render YAML frontmatter.

    `commentary_date` is stated only when the commentary was written on a
    different day than the report's, as happens when a report is regenerated.
    """
    commentary_line = (
        f"commentary_date: {commentary_date}\n" if commentary_date and commentary_date != date else ""
    )
    return f"""---
title: "{title}"
date: {date}
source: Yahoo Finance
scope: {scope}
{commentary_line}disclaimer: "{DISCLAIMER}"
---

"""


def render_ranking_table(ranked_assets: List[Asset]) -> str:
    """Render the ranking table in Markdown."""
    if not ranked_assets:
        return "*No data available*\n"
    
    lines = [
        "| Rank | Ticker | Name | Type | Market Cap | Currency |",
        "|------|--------|------|------|------------|----------|",
    ]
    
    for asset in ranked_assets:
        name = asset.name[:40]  # Truncate long names
        market_cap = format_market_cap(asset.market_cap)
        
        lines.append(
            f"| {asset.rank} | {asset.ticker} | {name} | {asset.quote_type} | {market_cap} | {asset.currency} |"
        )
    
    return "\n".join(lines) + "\n"


def render_metrics_section(metrics: Dict[str, Any]) -> str:
    """Render key metrics as bullet list."""
    if not metrics:
        return "*No metrics available*\n"
    
    lines = [
        f"- **Total Market Cap (Top {metrics.get('asset_count', 'N')})**: {format_market_cap(metrics.get('total_market_cap', 0))}",
        f"- **Top 5 Concentration**: {metrics.get('top5_concentration', 0):.1f}%",
        f"- **Top 10 Concentration**: {metrics.get('top10_concentration', 0):.1f}%",
        f"- **Assets Tracked**: {metrics.get('asset_count', 0)}",
    ]
    
    return "\n".join(lines) + "\n"


def render_changes_section(
    entries: List[str],
    exits: List[str],
    movers: List[Dict[str, Any]]
) -> str:
    """Render entries, exits, and movers."""
    lines = []
    
    lines.append(f"**New Entries**: {', '.join(entries) if entries else 'None'}")
    lines.append(f"**Exits**: {', '.join(exits) if exits else 'None'}")
    
    if movers:
        lines.append("\n**Notable Movers (by rank change)**:")
        for m in movers[:5]:
            cap_change = f" ({m['cap_delta_pct']:+.1f}% cap)" if abs(m["cap_delta_pct"]) > 1 else ""
            lines.append(f"- {m['ticker']} ({m['name'][:20]}): {_describe_rank_move(m['rank_delta'])}{cap_change}")

    return "\n".join(lines) + "\n"


def _describe_rank_move(rank_delta: int) -> str:
    """Describe a rank change; a positive delta means the asset moved up."""
    if rank_delta == 0:
        return "rank unchanged"

    direction = "↑" if rank_delta > 0 else "↓"
    places = abs(rank_delta)
    noun = "place" if places == 1 else "places"
    return f"{direction}{places} {noun}"


def render_observations(
    ranked_assets: List[Asset],
    metrics: Dict[str, Any]
) -> str:
    """Render quantitative observations."""
    if not ranked_assets or not metrics:
        return "*Insufficient data for observations*\n"
    
    lines = []
    
    # Top 5 dominance
    top5_conc = metrics.get("top5_concentration", 0)
    lines.append(f"- The Top 5 assets represent **{top5_conc:.1f}%** of the total tracked market cap")
    
    # Top 10 dominance
    top10_conc = metrics.get("top10_concentration", 0)
    lines.append(f"- The Top 10 assets represent **{top10_conc:.1f}%** of the total tracked market cap")
    
    # Largest asset
    if ranked_assets:
        largest = ranked_assets[0]
        largest_pct = (largest.market_cap / metrics.get("total_market_cap", 1)) * 100
        lines.append(f"- **{largest.name}** ({largest.ticker}) leads with {format_market_cap(largest.market_cap)} ({largest_pct:.1f}% of total)")
    
    # Asset type breakdown
    type_counts: Dict[str, int] = {}
    for asset in ranked_assets:
        type_counts[asset.quote_type] = type_counts.get(asset.quote_type, 0) + 1
    
    if type_counts:
        type_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))
        lines.append(f"- Asset type distribution: {type_str}")
    
    return "\n".join(lines) + "\n"


def render_methodology() -> str:
    """Render methodology and limitations section."""
    return """### Data Source
- Market data sourced from Yahoo Finance API
- Market capitalization values are as of the report generation time

### Methodology
- Assets ranked by market capitalization (descending)
- Concentration metrics calculated as percentage of total tracked market cap
- Week-over-week changes compared to previous available snapshot

### Limitations
- Data availability depends on Yahoo Finance coverage
- Some assets may be excluded due to missing market cap data
- Currency conversions not applied; values shown in native currency
- This analysis covers a curated list of assets, not the entire market
"""


def render_report(
    date: str,
    scope: str,
    ranked_assets: List[Asset],
    metrics: Dict[str, Any],
    changes: Tuple[List[str], List[str], List[Dict[str, Any]]],
    llm_sections: Dict[str, str],
    commentary_date: Optional[str] = None,
) -> str:
    """Render complete Markdown report."""
    entries, exits, movers = changes
    report = ReportId(date, scope)

    def commentary(key: str) -> str:
        return f"## {SECTION_HEADINGS[key]}\n\n{llm_sections.get(key, '*Pending*')}\n\n"

    parts = [
        render_frontmatter(report.title, date, report.label, commentary_date),
        f"# {report.title}\n\n",
        commentary("executive_summary"),
        f"## {RANKING_HEADING}\n\n",
        render_ranking_table(ranked_assets) + "\n",
        "## Key Metrics\n\n",
        render_metrics_section(metrics) + "\n",
        "## Weekly Changes\n\n",
        render_changes_section(entries, exits, movers) + "\n",
        "## Quantitative Observations\n\n",
        render_observations(ranked_assets, metrics) + "\n",
        "## Methodology and Limitations\n\n",
        render_methodology() + "\n",
        commentary("strategic_reflection"),
        commentary("implications"),
        FOOTER,
    ]
    return "".join(parts)


def save_report(content: str, filepath: Path) -> None:
    """Save report to file."""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Saved report: {filepath}")

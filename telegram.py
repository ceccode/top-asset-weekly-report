"""Telegram TXT generator for mobile-friendly report summaries."""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any

from config import DISCLAIMER_SHORT
from mdtext import extract_section, strip_inline_formatting, truncate_at_word
from metrics import format_market_cap
from llm import SECTION_HEADINGS
from render import RANKING_HEADING
from report_id import ReportId
from snapshot import load_snapshot

logger = logging.getLogger(__name__)

# Max character limits for Telegram output
MAX_SUMMARY_CHARS = 800
MAX_INSIGHT_CHARS = 600


def top_rows_from_snapshot(csv_path: Path, n: int = 10) -> List[Dict[str, Any]]:
    """The top N rows of the Telegram list, read from the CSV snapshot."""
    assets = load_snapshot(csv_path) or []
    return [
        {
            "rank": str(asset.rank),
            "ticker": asset.ticker,
            "name": asset.name,
            "market_cap_str": format_market_cap(asset.market_cap) if asset.market_cap else "",
        }
        for asset in assets[:n]
    ]


def parse_top_n_from_markdown_table(md_text: str, n: int = 10) -> List[Dict[str, Any]]:
    """
    Fallback: the same rows, parsed from the ranking table of the report.
    """
    ranking = extract_section(md_text, RANKING_HEADING)
    if not ranking:
        return []
    
    assets = []
    lines = ranking.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue

        parts = [p.strip() for p in line.split("|") if p.strip()]
        # Data rows start with the numeric rank; header and separator do not
        if len(parts) >= 4 and parts[0].isdigit():
            assets.append({
                "rank": parts[0],
                "ticker": parts[1],
                "name": parts[2][:30],  # Truncate long names
                "market_cap_str": parts[4] if len(parts) > 4 else "",
            })
        
        if len(assets) >= n:
            break
    
    return assets


def clean_text_for_telegram(text: str) -> str:
    """Clean markdown text for plain text Telegram output."""
    text = strip_inline_formatting(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # Links
    
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    
    return text.strip()


def format_summary_bullets(text: str, max_chars: int) -> str:
    """Extract key points from summary text."""
    text = clean_text_for_telegram(text)
    
    # If text has bullet points, extract them
    lines = text.split("\n")
    bullets = [l.strip() for l in lines if l.strip().startswith("-")]
    
    if bullets:
        result = "\n".join(bullets[:5])
    else:
        # Take first paragraph(s)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        result = "\n\n".join(paragraphs[:2])
    
    return truncate_at_word(result, max_chars)


def generate_telegram_txt(
    date: str,
    scope: str,
    md_content: str,
    csv_path: Path,
) -> str:
    """
    Generate Telegram-friendly text summary from report.
    
    Args:
        date: Report date YYYY-MM-DD
        md_content: Full markdown report content
        csv_path: Path to CSV snapshot for top N data
    
    Returns:
        Plain text formatted for Telegram
    """
    scope_label = ReportId(date, scope).label
    
    lines = []
    
    # Title
    lines.append(f"📊 Top {scope_label} — {date}")
    lines.append("Source: Yahoo Finance (market cap)")
    lines.append("")
    
    # Top 10 list
    top = top_rows_from_snapshot(csv_path, n=10) or parse_top_n_from_markdown_table(md_content, n=10)

    if top:
        lines.append("🏆 Top 10:")
        for row in top:
            lines.append(f"{row['rank']}) {row['name'][:25]} ({row['ticker']}) — {row['market_cap_str']}")
        lines.append("")
    
    # Executive Summary
    summary = extract_section(md_content, SECTION_HEADINGS["executive_summary"])
    if summary:
        summary_clean = format_summary_bullets(summary, MAX_SUMMARY_CHARS)
        lines.append("📝 Summary:")
        lines.append(summary_clean)
        lines.append("")
    
    # Insight from the strategic reflection
    insight = extract_section(md_content, SECTION_HEADINGS["strategic_reflection"])
    if insight:
        insight_clean = clean_text_for_telegram(insight)
        # Take first paragraph only
        first_para = insight_clean.split("\n\n")[0]
        insight_truncated = truncate_at_word(first_para, MAX_INSIGHT_CHARS)
        lines.append("💡 Insight:")
        lines.append(insight_truncated)
        lines.append("")
    
    # Disclaimer
    lines.append(f"⚠️ {DISCLAIMER_SHORT}")
    
    return "\n".join(lines)


def save_telegram_txt(content: str, filepath: Path) -> None:
    """Save Telegram text to file."""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Saved Telegram TXT: {filepath}")

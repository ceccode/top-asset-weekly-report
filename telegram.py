"""Telegram TXT generator for mobile-friendly report summaries."""

import csv
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import DISCLAIMER_SHORT
from metrics import format_market_cap

logger = logging.getLogger(__name__)

# Max character limits for Telegram output
MAX_SUMMARY_CHARS = 800
MAX_INSIGHT_CHARS = 600


def extract_section_from_markdown(md_text: str, heading: str) -> str:
    """
    Extract a section from markdown by heading.
    Returns content between ## heading and next ## or end of file.
    """
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, md_text, re.DOTALL | re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    return ""


def load_top_n_from_csv(csv_path: Path, n: int = 10) -> List[Dict[str, Any]]:
    """Load top N assets from CSV snapshot."""
    if not csv_path.exists():
        return []
    
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assets = []
            for i, row in enumerate(reader):
                if i >= n:
                    break
                assets.append({
                    "rank": row.get("rank", str(i + 1)),
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "market_cap": float(row.get("market_cap", 0)),
                })
            return assets
    except Exception as e:
        logger.warning(f"Error reading CSV {csv_path}: {e}")
        return []


def parse_top_n_from_markdown_table(md_text: str, n: int = 10) -> List[Dict[str, Any]]:
    """
    Fallback: parse top N from markdown table under ## Classifica.
    """
    classifica = extract_section_from_markdown(md_text, "Classifica")
    if not classifica:
        return []
    
    assets = []
    lines = classifica.split("\n")
    
    for line in lines:
        line = line.strip()
        # Skip non-table lines and header/separator
        if not line.startswith("|") or line.startswith("|--") or "Rank" in line:
            continue
        
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 4:
            try:
                assets.append({
                    "rank": parts[0],
                    "ticker": parts[1],
                    "name": parts[2][:30],  # Truncate long names
                    "market_cap_str": parts[4] if len(parts) > 4 else "",
                })
            except (IndexError, ValueError):
                continue
        
        if len(assets) >= n:
            break
    
    return assets


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max characters, ending at word boundary."""
    if len(text) <= max_chars:
        return text
    
    truncated = text[:max_chars]
    # Find last space to avoid cutting mid-word
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.7:
        truncated = truncated[:last_space]
    
    return truncated.rstrip(".,;:") + "…"


def clean_text_for_telegram(text: str) -> str:
    """Clean markdown text for plain text Telegram output."""
    # Remove markdown formatting
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*([^*]+)\*", r"\1", text)  # Italic
    text = re.sub(r"`([^`]+)`", r"\1", text)  # Code
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
    
    return truncate_text(result, max_chars)


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
    scope_label = "Global Assets" if scope == "global" else "Software Companies"
    
    lines = []
    
    # Title
    lines.append(f"📊 Top {scope_label} — {date}")
    lines.append("Source: Yahoo Finance (market cap)")
    lines.append("")
    
    # Top 10 list
    assets = load_top_n_from_csv(csv_path, n=10)
    if not assets:
        assets = parse_top_n_from_markdown_table(md_content, n=10)
    
    if assets:
        lines.append("🏆 Top 10:")
        for asset in assets:
            if "market_cap" in asset and asset["market_cap"]:
                cap_str = format_market_cap(asset["market_cap"])
            else:
                cap_str = asset.get("market_cap_str", "")
            
            name = asset.get("name", "")[:25]
            ticker = asset.get("ticker", "")
            lines.append(f"{asset['rank']}) {name} ({ticker}) — {cap_str}")
        lines.append("")
    
    # Executive Summary
    summary = extract_section_from_markdown(md_content, "Executive Summary")
    if summary:
        summary_clean = format_summary_bullets(summary, MAX_SUMMARY_CHARS)
        lines.append("📝 Summary:")
        lines.append(summary_clean)
        lines.append("")
    
    # Insight from Riflessione Strategica
    insight = extract_section_from_markdown(md_content, "Riflessione Strategica")
    if insight:
        insight_clean = clean_text_for_telegram(insight)
        # Take first paragraph only
        first_para = insight_clean.split("\n\n")[0]
        insight_truncated = truncate_text(first_para, MAX_INSIGHT_CHARS)
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

"""RAG context extraction from previous reports."""

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Sections to extract for RAG context
LLM_SECTIONS = [
    "Executive Summary",
    "Riflessione Strategica",
    "Implicazioni",
]

# Max words for RAG context
MAX_RAG_WORDS = 2000


def extract_section(content: str, section_name: str) -> Optional[str]:
    """Extract a specific section from markdown content."""
    # Match ## Section Name followed by content until next ## or end
    pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    
    if match:
        text = match.group(1).strip()
        # Skip if it's just a placeholder
        if "TODO" in text or "placeholder" in text.lower():
            return None
        return text
    return None


def get_recent_reports(reports_dir: Path, scope: str, current_date: str, k: int = 4) -> List[Path]:
    """Get the K most recent reports for the given scope before current_date."""
    current = datetime.strptime(current_date, "%Y-%m-%d")
    
    # Find all matching reports
    pattern = f"*.{scope}.md"
    all_reports = list(reports_dir.glob(pattern))
    
    # Filter to reports before current date and sort by date descending
    valid_reports = []
    for report_path in all_reports:
        try:
            date_str = report_path.name.split(".")[0]
            report_date = datetime.strptime(date_str, "%Y-%m-%d")
            if report_date < current:
                valid_reports.append((report_date, report_path))
        except ValueError:
            continue
    
    valid_reports.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in valid_reports[:k]]


def extract_rag_context(reports_dir: Path, scope: str, current_date: str, k: int = 4) -> str:
    """
    Extract LLM-generated sections from the last K reports.
    Returns concatenated context text.
    """
    recent_reports = get_recent_reports(reports_dir, scope, current_date, k)
    
    if not recent_reports:
        logger.info(f"No previous reports found for RAG context ({scope})")
        return ""
    
    context_parts = []
    
    for report_path in recent_reports:
        try:
            content = report_path.read_text(encoding="utf-8")
            date_str = report_path.name.split(".")[0]
            
            sections_found = []
            for section_name in LLM_SECTIONS:
                section_text = extract_section(content, section_name)
                if section_text:
                    sections_found.append(f"### {section_name}\n{section_text}")
            
            if sections_found:
                context_parts.append(f"## Report {date_str}\n\n" + "\n\n".join(sections_found))
        
        except Exception as e:
            logger.warning(f"Error reading {report_path}: {e}")
            continue
    
    return "\n\n---\n\n".join(context_parts)


def save_rag_context(rag_dir: Path, scope: str, context: str) -> Path:
    """Save RAG context to file."""
    filepath = rag_dir / f"rag_context_{scope}.txt"
    filepath.write_text(context, encoding="utf-8")
    logger.info(f"Saved RAG context: {filepath}")
    return filepath


def truncate_to_max_words(text: str, max_words: int = MAX_RAG_WORDS) -> str:
    """Truncate text to max words, keeping most recent content first."""
    words = text.split()
    if len(words) <= max_words:
        return text
    
    # Keep first max_words words (most recent reports are first)
    truncated_words = words[:max_words]
    return " ".join(truncated_words) + "\n\n[...truncated...]"


def get_rag_file_path(rag_dir: Path, scope: str) -> Path:
    """Get the path to RAG context file for a scope."""
    return rag_dir / f"rag_context_{scope}.txt"


def get_latest_report_date(reports_dir: Path, scope: str) -> Optional[str]:
    """Get the date of the most recent report for a scope."""
    pattern = f"*.{scope}.md"
    all_reports = list(reports_dir.glob(pattern))
    
    if not all_reports:
        return None
    
    dates = []
    for report_path in all_reports:
        try:
            date_str = report_path.name.split(".")[0]
            datetime.strptime(date_str, "%Y-%m-%d")  # Validate format
            dates.append(date_str)
        except ValueError:
            continue
    
    if not dates:
        return None
    
    return max(dates)


def check_rag_freshness(
    rag_dir: Path,
    reports_dir: Path,
    scope: str,
) -> Tuple[bool, str]:
    """
    Check if RAG context exists and is up-to-date.
    
    Returns:
        Tuple of (is_fresh, reason)
        - is_fresh: True if RAG is up-to-date, False if needs regeneration
        - reason: Description of status ("up-to-date", "missing", "stale")
    """
    rag_path = get_rag_file_path(rag_dir, scope)
    
    # Check if RAG file exists
    if not rag_path.exists():
        return False, "missing"
    
    # Get latest report date
    latest_report_date = get_latest_report_date(reports_dir, scope)
    if not latest_report_date:
        # No reports exist, RAG is technically up-to-date (nothing to include)
        return True, "up-to-date"
    
    # Check if RAG content includes the latest report date
    try:
        rag_content = rag_path.read_text(encoding="utf-8")
        
        # Check if latest report date is mentioned in RAG
        if latest_report_date in rag_content:
            return True, "up-to-date"
        
        # Also check by file modification time as fallback
        rag_mtime = rag_path.stat().st_mtime
        latest_report_path = reports_dir / f"{latest_report_date}.{scope}.md"
        if latest_report_path.exists():
            report_mtime = latest_report_path.stat().st_mtime
            if rag_mtime >= report_mtime:
                return True, "up-to-date"
        
        return False, "stale"
    
    except Exception as e:
        logger.warning(f"Error checking RAG freshness: {e}")
        return False, "error"


def ensure_rag_context(
    rag_dir: Path,
    reports_dir: Path,
    scope: str,
    k: int = 4,
    force: bool = False,
) -> Path:
    """
    Ensure RAG context exists and is up-to-date.
    Regenerates if missing or stale.
    
    Args:
        rag_dir: Directory for RAG files
        reports_dir: Directory containing reports
        scope: Report scope (global/software)
        k: Number of recent reports to include
        force: Force regeneration even if up-to-date
    
    Returns:
        Path to RAG context file
    """
    rag_path = get_rag_file_path(rag_dir, scope)
    
    if not force:
        is_fresh, reason = check_rag_freshness(rag_dir, reports_dir, scope)
        
        if is_fresh:
            logger.info(f"RAG context for {scope}: up-to-date")
            return rag_path
        
        if reason == "missing":
            logger.info(f"RAG context for {scope}: missing → generating...")
        else:
            logger.info(f"RAG context for {scope}: stale → regenerating...")
    else:
        logger.info(f"RAG context for {scope}: force regeneration...")
    
    # Get all reports (not filtered by current date) for RAG
    # Use a far future date to include all reports
    future_date = "2099-12-31"
    context = extract_rag_context(reports_dir, scope, future_date, k)
    
    if context:
        # Truncate if too long
        context = truncate_to_max_words(context, MAX_RAG_WORDS)
        save_rag_context(rag_dir, scope, context)
    else:
        # Create empty file to mark as checked
        rag_path.write_text("# No previous reports available for RAG context\n", encoding="utf-8")
        logger.info(f"RAG context for {scope}: no reports available")
    
    return rag_path

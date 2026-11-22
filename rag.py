"""RAG context extraction from previous reports."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import mdtext
from llm import PLACEHOLDER_MARKER, SECTION_HEADINGS
from render import FOOTER
from report_id import ReportId

logger = logging.getLogger(__name__)

# Sections to extract for RAG context
LLM_SECTIONS = list(SECTION_HEADINGS.values())

# Max words for RAG context
MAX_RAG_WORDS = 2000


def extract_section(content: str, section_name: str) -> Optional[str]:
    """Extract a specific section from markdown content."""
    text = mdtext.extract_section(content, section_name)
    if not text:
        return None
    # Skip if it's just a placeholder
    if "TODO" in text or "placeholder" in text.lower() or PLACEHOLDER_MARKER in text:
        return None
    return text


def _reports_for_scope(reports_dir: Path, scope: str) -> List[Tuple[str, Path]]:
    """All (date, path) pairs of the scope's reports, in no particular order."""
    found = []
    for report_path in reports_dir.glob(f"*.{scope}.md"):
        report = ReportId.from_path(report_path)
        if report:
            found.append((report.date, report_path))
    return found


def get_recent_reports(reports_dir: Path, scope: str, current_date: str, k: int = 4) -> List[Path]:
    """Get the K most recent reports for the given scope before current_date."""
    # ISO dates sort chronologically as plain strings
    earlier = [r for r in _reports_for_scope(reports_dir, scope) if r[0] < current_date]
    earlier.sort(key=lambda r: r[0], reverse=True)
    return [path for _, path in earlier[:k]]


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
            # Without the footer, which would otherwise end up in the last section
            content = report_path.read_text(encoding="utf-8").strip().removesuffix(FOOTER.strip())
            date_str = ReportId.from_path(report_path).date
            
            sections_found = []
            for section_name in LLM_SECTIONS:
                section_text = extract_section(content, section_name)
                if section_text:
                    sections_found.append(f"### {section_name}\n{section_text}")
            
            if sections_found:
                context_parts.append(f"## Report {date_str}\n\n" + "\n\n".join(sections_found))
        
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Error reading {report_path}: {e}")
            continue
    
    return "\n\n---\n\n".join(context_parts)


def save_rag_context(rag_dir: Path, scope: str, context: str) -> Path:
    """Save RAG context to file."""
    filepath = get_rag_file_path(rag_dir, scope)
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
    dates = [date for date, _ in _reports_for_scope(reports_dir, scope)]
    return max(dates) if dates else None


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
        latest_report_path = reports_dir / ReportId(latest_report_date, scope).markdown_name
        if latest_report_path.exists():
            report_mtime = latest_report_path.stat().st_mtime
            if rag_mtime >= report_mtime:
                return True, "up-to-date"
        
        return False, "stale"
    
    except (OSError, UnicodeDecodeError) as e:
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

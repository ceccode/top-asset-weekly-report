#!/usr/bin/env python3
"""
Regenerate past reports from their snapshots.

Every report is rendered again with the current template, so a template or
format fix reaches the whole archive. Commentary already written by the LLM
is kept; where a report only has placeholders, the commentary is written now
and the report states the day it was written (`commentary_date`).

Reports are processed oldest first, so each one finds the regenerated
commentary of the earlier ones as its historical context.
"""

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import RAG_DIR, REPORTS_DIR, SNAPSHOTS_DIR, get_openai_api_key
from llm import SECTION_HEADINGS, build_input, generate_llm_sections, is_placeholder
from mdtext import extract_section
from metrics import calculate_changes, calculate_metrics
from rag import ensure_rag_context, extract_rag_context
from render import FOOTER, render_report, save_report
from report_id import DATE_FORMAT, SCOPES, ReportId
from snapshot import load_previous_snapshot, load_snapshot
from telegram import generate_telegram_txt, save_telegram_txt

logger = logging.getLogger(__name__)

# Headings the commentary had before the reports were fully in English
LEGACY_HEADINGS = {
    "strategic_reflection": "Riflessione Strategica",
    "implications": "Implicazioni",
}


@dataclass(frozen=True)
class Folders:
    reports: Path = REPORTS_DIR
    snapshots: Path = SNAPSHOTS_DIR
    rag: Path = RAG_DIR


def read_commentary(md_text: str) -> Dict[str, str]:
    """The commentary sections of an existing report; a missing one is ""."""
    body = md_text.strip().removesuffix(FOOTER.strip())
    sections = {}
    for key, heading in SECTION_HEADINGS.items():
        text = extract_section(body, heading)
        if not text and key in LEGACY_HEADINGS:
            text = extract_section(body, LEGACY_HEADINGS[key])
        sections[key] = text
    return sections


def read_commentary_date(md_text: str) -> Optional[str]:
    """The `commentary_date` of an existing report's frontmatter, if it has one."""
    match = re.search(r"^commentary_date: (\S+)$", md_text, re.MULTILINE)
    return match.group(1) if match else None


def has_commentary(sections: Dict[str, str]) -> bool:
    return all(sections.values()) and not is_placeholder(sections)


def regenerate_report(
    report: ReportId,
    folders: Folders,
    api_key: Optional[str],
    today: str,
    rag_k: int = 4,
) -> bool:
    """
    Render one report again from its snapshot.

    Returns False when the report is left as it was (no readable snapshot) or
    when its commentary was wanted from the LLM but came back as placeholders.
    """
    report_path = folders.reports / report.markdown_name
    ranked = load_snapshot(folders.snapshots / report.csv_name)
    if not ranked:
        logger.error(f"{report.stem}: no readable snapshot, report left as it is")
        return False

    metrics = calculate_metrics(ranked)
    previous = load_previous_snapshot(folders.snapshots, report.scope, report.date)
    changes = calculate_changes(ranked, previous)

    existing = report_path.read_text(encoding="utf-8")
    sections = read_commentary(existing)
    commentary_date = read_commentary_date(existing)
    complete = True

    if not has_commentary(sections):
        input_data = build_input(report.date, ranked, metrics, changes)
        rag_context = extract_rag_context(folders.reports, report.scope, report.date, rag_k)
        sections = generate_llm_sections(input_data, rag_context, report.scope, api_key)
        if is_placeholder(sections):
            complete = not api_key  # placeholders are the expected outcome without a key
            commentary_date = None
        else:
            commentary_date = today

    content = render_report(report.date, report.scope, ranked, metrics, changes, sections, commentary_date)
    save_report(content, report_path)

    telegram_txt = generate_telegram_txt(
        report.date, report.scope, content, folders.snapshots / report.csv_name
    )
    save_telegram_txt(telegram_txt, folders.snapshots / report.telegram_snapshot_name)
    return complete


def find_reports(reports_dir: Path, scopes: List[str], since: str, until: str) -> List[ReportId]:
    """The reports to regenerate, oldest first."""
    found = [ReportId.from_path(path) for path in reports_dir.glob("*.md")]
    wanted = [r for r in found if r and r.scope in scopes and since <= r.date <= until]
    return sorted(wanted, key=lambda r: (r.date, r.scope))


def regenerate_all(
    reports: List[ReportId],
    folders: Folders,
    api_key: Optional[str],
    today: str,
    rag_k: int = 4,
) -> List[ReportId]:
    """Regenerate the given reports and refresh the RAG files. Returns the incomplete ones."""
    incomplete = []
    for i, report in enumerate(reports, 1):
        logger.info(f"[{i}/{len(reports)}] {report.stem}")
        if not regenerate_report(report, folders, api_key, today, rag_k):
            incomplete.append(report)

    for scope in sorted({report.scope for report in reports}):
        ensure_rag_context(folders.rag, folders.reports, scope, k=rag_k, force=True)

    return incomplete


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate past reports from their snapshots.")
    parser.add_argument("--only", choices=[*SCOPES, "all"], default="all", help="Scope to regenerate (default: all)")
    parser.add_argument("--from", dest="since", default="0000-00-00", help="First report date, YYYY-MM-DD")
    parser.add_argument("--to", dest="until", default="9999-99-99", help="Last report date, YYYY-MM-DD")
    parser.add_argument("--rag-k", type=int, default=4, help="Previous reports given as context (default: 4)")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Never call the LLM: reports without commentary keep their placeholders",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Run the CLI. Returns 0 only when every report was regenerated completely."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scopes = list(SCOPES) if args.only == "all" else [args.only]
    reports = find_reports(REPORTS_DIR, scopes, args.since, args.until)
    if not reports:
        logger.error("No reports to regenerate")
        return 1

    api_key = None if args.no_llm else get_openai_api_key()
    today = datetime.now(timezone.utc).strftime(DATE_FORMAT)
    incomplete = regenerate_all(reports, Folders(), api_key, today, args.rag_k)

    if incomplete:
        logger.error(f"Incomplete: {', '.join(r.stem for r in incomplete)}")
        return 1
    logger.info(f"✓ {len(reports)} report(s) regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

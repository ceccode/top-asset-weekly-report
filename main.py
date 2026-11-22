#!/usr/bin/env python3
"""
Top Assets Weekly Report - CLI Entrypoint

Generates weekly market reports for global assets and software companies.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from config import (
    REPORTS_DIR,
    SNAPSHOTS_DIR,
    RAG_DIR,
    get_global_tickers,
    get_software_tickers,
    get_openai_api_key,
)
from yahoo import fetch_all_tickers
from metrics import (
    rank_by_market_cap,
    calculate_metrics,
    calculate_changes,
)
from rag import extract_rag_context, ensure_rag_context
from llm import build_input, generate_llm_sections
from render import render_report, save_report
from report_id import DATE_FORMAT, SCOPES, ReportId
from snapshot import load_previous_snapshot, save_snapshot_csv, save_snapshot_json
from telegram import generate_telegram_txt, save_telegram_txt
from publisher import build_public

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Where each scope reads its tickers from
TICKER_SOURCES = {
    "global": get_global_tickers,
    "software": get_software_tickers,
}

@dataclass(frozen=True)
class Options:
    """How a report is generated, as chosen on the command line."""
    top_n: int = 50
    rag_k: int = 4
    use_llm: bool = True
    telegram: bool = True
    rag_check: bool = True


def generate_report(report: ReportId, tickers: List[str], options: Options) -> bool:
    """
    Generate a single report.

    Returns True if successful, False otherwise.
    """
    scope = report.scope
    logger.info(f"=== Generating {scope} report for {report.date} ===")

    logger.info(f"Fetching data for {len(tickers)} tickers...")
    assets = fetch_all_tickers(tickers)

    if not assets:
        logger.error(f"No valid data fetched for {scope} report. Aborting.")
        return False

    ranked = rank_by_market_cap(assets, options.top_n)
    metrics = calculate_metrics(ranked)
    logger.info(f"Ranked {len(ranked)} assets, total cap: {metrics.get('total_market_cap', 0):,.0f}")

    previous = load_previous_snapshot(SNAPSHOTS_DIR, scope, report.date)
    changes = calculate_changes(ranked, previous)
    entries, exits, movers = changes
    logger.info(f"Changes: {len(entries)} entries, {len(exits)} exits, {len(movers)} movers")

    csv_path = SNAPSHOTS_DIR / report.csv_name
    save_snapshot_csv(ranked, csv_path)
    save_snapshot_json(ranked, metrics, SNAPSHOTS_DIR / report.json_name)

    # Context for the LLM; the RAG file itself is written once, by ensure_rag_context below
    rag_context = extract_rag_context(REPORTS_DIR, scope, report.date, options.rag_k)
    if rag_context:
        logger.info(f"RAG context extracted ({len(rag_context)} chars)")
    else:
        logger.info("No RAG context available (no previous reports)")

    api_key = get_openai_api_key() if options.use_llm else None
    input_data = build_input(report.date, ranked, metrics, changes)
    llm_sections = generate_llm_sections(input_data, rag_context, scope, api_key)

    report_content = render_report(report.date, scope, ranked, metrics, changes, llm_sections)
    report_path = REPORTS_DIR / report.markdown_name
    save_report(report_content, report_path)

    # Telegram text and RAG refresh are extras: failing to write them does not fail the report
    if options.telegram:
        telegram_txt = generate_telegram_txt(report.date, scope, report_content, csv_path)
        try:
            save_telegram_txt(telegram_txt, SNAPSHOTS_DIR / report.telegram_snapshot_name)
        except OSError as e:
            logger.warning(f"Failed to save Telegram TXT: {e}")

    if options.rag_check:
        try:
            ensure_rag_context(RAG_DIR, REPORTS_DIR, scope, k=options.rag_k)
        except OSError as e:
            logger.warning(f"Failed to update RAG context: {e}")

    logger.info(f"✓ {scope} report complete: {report_path}")
    return True


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate weekly market reports for global assets and software companies."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now(timezone.utc).strftime(DATE_FORMAT),
        help="Report date in YYYY-MM-DD format (default: today UTC)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Number of top assets to include (default: 50)",
    )
    parser.add_argument(
        "--rag-k",
        type=int,
        default=4,
        help="Number of previous reports for RAG context (default: 4)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM generation, use placeholders",
    )
    parser.add_argument(
        "--only",
        type=str,
        choices=[*SCOPES, "all"],
        default="all",
        help="Generate only specific report type (default: all)",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Disable Telegram TXT generation",
    )
    parser.add_argument(
        "--no-rag-check",
        action="store_true",
        help="Disable RAG freshness check and regeneration",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Build public/ folder for GitHub Pages after generating reports",
    )
    return parser.parse_args(argv)


def _generate_safely(report: ReportId, options: Options) -> bool:
    """
    Generate one report, turning any failure into False.

    This is the boundary that lets the other scope still run: the traceback
    is logged so an unexpected error remains visible.
    """
    try:
        return generate_report(report, TICKER_SOURCES[report.scope](), options)
    except Exception:
        logger.exception(f"Failed to generate {report.scope} report")
        return False


def main(argv: Optional[List[str]] = None) -> int:
    """Run the CLI. Returns the exit code: 0 only when every requested report was generated."""
    args = parse_args(argv)

    try:
        datetime.strptime(args.date, DATE_FORMAT)
    except ValueError:
        logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD.")
        return 1

    options = Options(
        top_n=args.top_n,
        rag_k=args.rag_k,
        use_llm=not args.no_llm,
        telegram=not args.no_telegram,
        rag_check=not args.no_rag_check,
    )

    logger.info("Top Assets Weekly Report Generator")
    logger.info(f"Date: {args.date}, Top-N: {options.top_n}, RAG-K: {options.rag_k}")
    logger.info(f"LLM: {'enabled if API key present' if options.use_llm else 'disabled'}")
    logger.info(f"Telegram: {'enabled' if options.telegram else 'disabled'}")
    logger.info(f"RAG check: {'enabled' if options.rag_check else 'disabled'}")

    scopes = list(SCOPES) if args.only == "all" else [args.only]
    generated = [
        scope for scope in scopes if _generate_safely(ReportId(args.date, scope), options)
    ]

    if not generated:
        logger.error("No reports generated")
        return 1

    all_generated = len(generated) == len(scopes)
    if all_generated:
        logger.info(f"✓ All {len(generated)} report(s) generated successfully")
    else:
        logger.error(f"Partial success: {len(generated)}/{len(scopes)} reports generated")

    if args.publish:
        try:
            published = build_public(args.date, generated)
        except Exception:
            logger.exception("Failed to build public folder")
            return 1
        if not published:
            return 1

    return 0 if all_generated else 1


if __name__ == "__main__":
    sys.exit(main())

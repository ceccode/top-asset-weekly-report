#!/usr/bin/env python3
"""
Top Assets Weekly Report - CLI Entrypoint

Generates weekly market reports for global assets and software companies.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    load_previous_snapshot,
    save_snapshot_csv,
    save_snapshot_json,
)
from rag import extract_rag_context, save_rag_context, ensure_rag_context
from llm import generate_llm_sections
from render import render_report, save_report
from telegram import generate_telegram_txt, save_telegram_txt
from publisher import build_public

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_report(
    scope: str,
    tickers: list[str],
    date: str,
    top_n: int,
    rag_k: int,
    use_llm: bool,
    generate_telegram: bool = True,
    rag_check: bool = True,
) -> bool:
    """
    Generate a single report for the given scope.
    
    Returns True if successful, False otherwise.
    """
    logger.info(f"=== Generating {scope} report for {date} ===")
    
    # Fetch data
    logger.info(f"Fetching data for {len(tickers)} tickers...")
    assets = fetch_all_tickers(tickers)
    
    if not assets:
        logger.error(f"No valid data fetched for {scope} report. Aborting.")
        return False
    
    # Rank and calculate metrics
    ranked = rank_by_market_cap(assets, top_n)
    metrics = calculate_metrics(ranked)
    
    logger.info(f"Ranked {len(ranked)} assets, total cap: {metrics.get('total_market_cap', 0):,.0f}")
    
    # Load previous snapshot and calculate changes
    previous = load_previous_snapshot(SNAPSHOTS_DIR, scope, date)
    changes = calculate_changes(ranked, previous)
    entries, exits, movers = changes
    logger.info(f"Changes: {len(entries)} entries, {len(exits)} exits, {len(movers)} movers")
    
    # Save snapshots
    csv_path = SNAPSHOTS_DIR / f"{date}.{scope}.csv"
    json_path = SNAPSHOTS_DIR / f"{date}.{scope}.json"
    save_snapshot_csv(ranked, csv_path)
    save_snapshot_json(ranked, metrics, json_path)
    
    # Extract RAG context
    rag_context = extract_rag_context(REPORTS_DIR, scope, date, rag_k)
    if rag_context:
        save_rag_context(RAG_DIR, scope, rag_context)
        logger.info(f"RAG context extracted ({len(rag_context)} chars)")
    else:
        logger.info("No RAG context available (no previous reports)")
    
    # Generate LLM sections
    api_key = get_openai_api_key() if use_llm else None
    input_data = {
        "assets": ranked[:20],  # Send top 20 to LLM to reduce tokens
        "metrics": metrics,
        "entries": entries,
        "exits": exits,
        "movers": movers,
    }
    llm_sections = generate_llm_sections(input_data, rag_context, scope, api_key)
    
    # Render and save report
    report_content = render_report(date, scope, ranked, metrics, changes, llm_sections)
    report_path = REPORTS_DIR / f"{date}.{scope}.md"
    save_report(report_content, report_path)
    
    # Generate Telegram TXT
    if generate_telegram:
        try:
            telegram_txt = generate_telegram_txt(date, scope, report_content, csv_path)
            telegram_path = SNAPSHOTS_DIR / f"{date}.telegram.{scope}.txt"
            save_telegram_txt(telegram_txt, telegram_path)
        except Exception as e:
            logger.warning(f"Failed to generate Telegram TXT: {e}")
    
    # Check and update RAG context
    if rag_check:
        try:
            ensure_rag_context(RAG_DIR, REPORTS_DIR, scope, k=rag_k)
        except Exception as e:
            logger.warning(f"Failed to update RAG context: {e}")
    
    logger.info(f"✓ {scope} report complete: {report_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly market reports for global assets and software companies."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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
        choices=["global", "software", "all"],
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
    
    args = parser.parse_args()
    
    # Validate date format
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD.")
        sys.exit(1)
    
    logger.info(f"Top Assets Weekly Report Generator")
    logger.info(f"Date: {args.date}, Top-N: {args.top_n}, RAG-K: {args.rag_k}")
    logger.info(f"LLM: {'disabled' if args.no_llm else 'enabled if API key present'}")
    logger.info(f"Telegram: {'disabled' if args.no_telegram else 'enabled'}")
    logger.info(f"RAG check: {'disabled' if args.no_rag_check else 'enabled'}")
    
    use_llm = not args.no_llm
    generate_telegram = not args.no_telegram
    rag_check = not args.no_rag_check
    success_count = 0
    
    # Generate global report
    if args.only in ("global", "all"):
        try:
            global_tickers = get_global_tickers()
            if generate_report(
                "global", global_tickers, args.date, args.top_n, args.rag_k,
                use_llm, generate_telegram, rag_check
            ):
                success_count += 1
        except Exception as e:
            logger.error(f"Failed to generate global report: {e}")
    
    # Generate software report
    if args.only in ("software", "all"):
        try:
            software_tickers = get_software_tickers()
            if generate_report(
                "software", software_tickers, args.date, args.top_n, args.rag_k,
                use_llm, generate_telegram, rag_check
            ):
                success_count += 1
        except Exception as e:
            logger.error(f"Failed to generate software report: {e}")
    
    # Summary
    expected = 2 if args.only == "all" else 1
    if success_count == expected:
        logger.info(f"✓ All {success_count} report(s) generated successfully")
    elif success_count > 0:
        logger.warning(f"Partial success: {success_count}/{expected} reports generated")
    else:
        logger.error("No reports generated")
        sys.exit(1)
    
    # Build public folder if requested
    if args.publish and success_count > 0:
        scopes_to_publish = []
        if args.only in ("global", "all"):
            scopes_to_publish.append("global")
        if args.only in ("software", "all"):
            scopes_to_publish.append("software")
        
        try:
            build_public(args.date, scopes_to_publish)
        except Exception as e:
            logger.error(f"Failed to build public folder: {e}")
            sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

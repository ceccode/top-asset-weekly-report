"""Publisher module for generating static GitHub Pages site."""

import csv
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from config import REPORTS_DIR, SNAPSHOTS_DIR, DISCLAIMER, DISCLAIMER_SHORT
from mdtext import extract_section, strip_inline_formatting, truncate_at_word
from report_id import SCOPES, ReportId

logger = logging.getLogger(__name__)

# Public output directory
PUBLIC_DIR = Path(__file__).parent / "public"

# Manifest version
MANIFEST_VERSION = 1

# Max chars for summary excerpt
MAX_EXCERPT_CHARS = 300


def make_excerpt(text: str, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Create a short excerpt from text."""
    text = strip_inline_formatting(text)
    text = re.sub(r"\n+", " ", text).strip()
    return truncate_at_word(text, max_chars)


def load_ranking_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load ranking data from CSV snapshot."""
    if not csv_path.exists():
        return []
    
    ranking = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ranking.append({
                    "rank": int(row.get("rank", 0)),
                    "name": row.get("name", ""),
                    "ticker": row.get("ticker", ""),
                    "market_cap": float(row.get("market_cap", 0)),
                    "currency": row.get("currency", "USD"),
                    "quote_type": row.get("quote_type", "EQUITY"),
                })
        return ranking
    except Exception as e:
        logger.warning(f"Error reading CSV {csv_path}: {e}")
        return []


def load_metrics_from_json(json_path: Path) -> Dict[str, Any]:
    """Load metrics from JSON snapshot."""
    if not json_path.exists():
        return {}
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("metrics", {})
    except Exception as e:
        logger.warning(f"Error reading JSON {json_path}: {e}")
        return {}


def generate_report_json(
    report: ReportId,
    ranking: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    has_telegram: bool,
) -> Dict[str, Any]:
    """Generate structured JSON for a single report."""
    return {
        "date": report.date,
        "scope": report.scope,
        "source": "Yahoo Finance",
        "disclaimer": DISCLAIMER,
        "top_n": len(ranking),
        "ranking": ranking,
        "metrics": {
            "total_market_cap_top_n": metrics.get("total_market_cap", 0),
            "top5_concentration": metrics.get("top5_concentration", 0),
            "top10_concentration": metrics.get("top10_concentration", 0),
            "entries": [],  # Will be populated from metrics if available
            "exits": [],
            "movers": [],
        },
        "paths": {
            "markdown": f"reports/{report.markdown_name}",
            "telegram": f"telegram/{report.telegram_public_name}" if has_telegram else None,
        },
    }


def get_all_reports(public_reports_dir: Path) -> List[Dict[str, str]]:
    """Get all reports from public/reports/ directory."""
    reports = []
    if not public_reports_dir.exists():
        return reports
    
    for md_file in public_reports_dir.glob("*.md"):
        report = ReportId.from_path(md_file)
        if report:
            reports.append({"date": report.date, "scope": report.scope, "path": md_file})
    
    # Sort by date descending
    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports


def generate_manifest(public_dir: Path) -> Dict[str, Any]:
    """Generate manifest.json from all reports in public/."""
    reports_dir = public_dir / "reports"
    data_dir = public_dir / "data"
    telegram_dir = public_dir / "telegram"
    
    all_reports = get_all_reports(reports_dir)
    
    # Find latest per scope
    latest = {}
    for scope in SCOPES:
        scope_reports = [r for r in all_reports if r["scope"] == scope]
        if scope_reports:
            newest = ReportId(scope_reports[0]["date"], scope)
            latest[scope] = {
                "date": newest.date,
                "markdown": f"reports/{newest.markdown_name}",
                "json": f"data/{newest.json_name}",
            }
    
    # Build reports array
    reports_list = []
    for found in all_reports:
        report = ReportId(found["date"], found["scope"])
        md_path = found["path"]
        json_path = data_dir / report.json_name
        telegram_path = telegram_dir / report.telegram_public_name
        
        # Read markdown for excerpt
        try:
            md_content = md_path.read_text(encoding="utf-8")
            summary = extract_section(md_content, "Executive Summary")
            excerpt = make_excerpt(summary) if summary else "Report disponibile."
        except Exception:
            excerpt = "Report disponibile."
        
        top10 = load_ranking_from_csv(SNAPSHOTS_DIR / report.csv_name)[:10]
        
        reports_list.append({
            "date": report.date,
            "scope": report.scope,
            "title": report.title,
            "source": "Yahoo Finance",
            "disclaimer": DISCLAIMER_SHORT,
            "paths": {
                "markdown": f"reports/{report.markdown_name}",
                "json": f"data/{report.json_name}" if json_path.exists() else None,
                "telegram": f"telegram/{report.telegram_public_name}" if telegram_path.exists() else None,
            },
            "summary_excerpt": excerpt,
            "top10": top10,
        })
    
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "version": MANIFEST_VERSION,
        "latest": latest,
        "reports": reports_list,
    }


def generate_index_html(manifest: Dict[str, Any]) -> str:
    """Generate minimal index.html landing page."""
    latest = manifest.get("latest", {})
    reports = manifest.get("reports", [])[:10]  # Last 10
    
    latest_links = ""
    for scope, info in latest.items():
        scope_label = ReportId(info["date"], scope).label_it
        latest_links += f'<li><a href="{info["markdown"]}">{scope_label}</a> ({info["date"]})</li>\n'
    
    reports_links = ""
    for r in reports:
        reports_links += f'<li><a href="{r["paths"]["markdown"]}">{r["title"]}</a></li>\n'
    
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://gc.zgo.at; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;">
    <title>Top Assets Weekly Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ color: #1a1a1a; }}
        h2 {{ color: #444; margin-top: 2rem; }}
        a {{ color: #0066cc; }}
        ul {{ padding-left: 1.5rem; }}
        li {{ margin: 0.5rem 0; }}
        .disclaimer {{
            margin-top: 3rem;
            padding: 1rem;
            background: #f5f5f5;
            border-radius: 4px;
            font-size: 0.9rem;
            color: #666;
        }}
        .meta {{
            font-size: 0.85rem;
            color: #888;
        }}
    </style>
</head>
<body>
    <h1>📊 Top Assets Weekly Report</h1>
    <p>Report settimanali sui principali asset per capitalizzazione di mercato.</p>
    
    <h2>📈 Ultimi Report</h2>
    <ul>
{latest_links}
    </ul>
    
    <h2>📁 Archivio</h2>
    <ul>
{reports_links}
    </ul>
    
    <h2>🔗 Dati</h2>
    <ul>
        <li><a href="manifest.json">manifest.json</a> - Indice completo dei report</li>
    </ul>
    
    <div class="disclaimer">
        <strong>⚠️ Disclaimer:</strong> {DISCLAIMER_SHORT}
    </div>
    
    <p class="meta">Generato: {manifest.get("generated_at_utc", "N/A")}</p>
    
    <script data-goatcounter="https://topweeklyasset.goatcounter.com/count"
            async src="//gc.zgo.at/count.js"></script>
</body>
</html>
"""


def _publish_report(report: ReportId) -> None:
    """Copy one report into public/ together with its JSON data and Telegram text."""
    md_dst = PUBLIC_DIR / "reports" / report.markdown_name
    shutil.copy2(REPORTS_DIR / report.markdown_name, md_dst)
    logger.info(f"Copied: {md_dst}")
    
    telegram_src = SNAPSHOTS_DIR / report.telegram_snapshot_name
    report_json = generate_report_json(
        report,
        load_ranking_from_csv(SNAPSHOTS_DIR / report.csv_name),
        load_metrics_from_json(SNAPSHOTS_DIR / report.json_name),
        has_telegram=telegram_src.exists(),
    )
    json_dst = PUBLIC_DIR / "data" / report.json_name
    with open(json_dst, "w", encoding="utf-8") as f:
        json.dump(report_json, f, indent=2, ensure_ascii=False)
    logger.info(f"Generated: {json_dst}")
    
    if telegram_src.exists():
        telegram_dst = PUBLIC_DIR / "telegram" / report.telegram_public_name
        shutil.copy2(telegram_src, telegram_dst)
        logger.info(f"Copied: {telegram_dst}")


def build_public(date: str, scopes: List[str]) -> bool:
    """
    Build the public/ folder with all static assets.

    public/ is not versioned, so every build republishes the whole archive
    found in data/reports/, not only the reports of the current run.

    Args:
        date: Date of the reports generated by the current run
        scopes: Scopes generated by the current run (global, software)

    Returns:
        True if successful
    """
    logger.info(f"Building public/ for date={date}, scopes={scopes}")

    for d in [PUBLIC_DIR, PUBLIC_DIR / "reports", PUBLIC_DIR / "data", PUBLIC_DIR / "telegram"]:
        d.mkdir(parents=True, exist_ok=True)

    for scope in scopes:
        expected = REPORTS_DIR / ReportId(date, scope).markdown_name
        if not expected.exists():
            logger.warning(f"Report not found: {expected}")

    published_count = 0

    for found in get_all_reports(REPORTS_DIR):
        report = ReportId(found["date"], found["scope"])
        try:
            _publish_report(report)
            published_count += 1
        except Exception as e:
            logger.error(f"Failed to publish {report.stem} report: {e}")
            continue

    if published_count == 0:
        logger.error("No reports published")
        return False
    
    # Generate manifest
    try:
        manifest = generate_manifest(PUBLIC_DIR)
        manifest_path = PUBLIC_DIR / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        logger.info(f"Generated: {manifest_path}")
    except Exception as e:
        logger.error(f"Failed to generate manifest: {e}")
        return False
    
    # Generate index.html
    try:
        index_html = generate_index_html(manifest)
        index_path = PUBLIC_DIR / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        logger.info(f"Generated: {index_path}")
    except Exception as e:
        logger.error(f"Failed to generate index.html: {e}")
        # Not fatal, continue
    
    logger.info(f"✓ Public folder built: {PUBLIC_DIR}")
    return True

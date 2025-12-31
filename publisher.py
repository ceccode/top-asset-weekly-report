"""Publisher module for generating static GitHub Pages site."""

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import REPORTS_DIR, SNAPSHOTS_DIR, DISCLAIMER, DISCLAIMER_SHORT

logger = logging.getLogger(__name__)

# Public output directory
PUBLIC_DIR = Path(__file__).parent / "public"

# Manifest version
MANIFEST_VERSION = 1

# Max chars for summary excerpt
MAX_EXCERPT_CHARS = 300


def extract_section_from_markdown(md_text: str, heading: str) -> str:
    """Extract a section from markdown by heading."""
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, md_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def make_excerpt(text: str, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Create a short excerpt from text."""
    # Clean markdown formatting
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\n+", " ", text)
    text = text.strip()
    
    if len(text) <= max_chars:
        return text
    
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.7:
        truncated = truncated[:last_space]
    
    return truncated.rstrip(".,;:") + "…"


def load_ranking_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load ranking data from CSV snapshot."""
    if not csv_path.exists():
        return []
    
    import csv
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
    date: str,
    scope: str,
    ranking: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    md_path: Path,
    telegram_path: Optional[Path],
) -> Dict[str, Any]:
    """Generate structured JSON for a single report."""
    return {
        "date": date,
        "scope": scope,
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
            "markdown": f"reports/{date}.{scope}.md",
            "telegram": f"telegram/{date}.{scope}.txt" if telegram_path and telegram_path.exists() else None,
        },
    }


def get_all_reports(public_reports_dir: Path) -> List[Dict[str, str]]:
    """Get all reports from public/reports/ directory."""
    reports = []
    if not public_reports_dir.exists():
        return reports
    
    for md_file in public_reports_dir.glob("*.md"):
        try:
            parts = md_file.stem.split(".")
            if len(parts) >= 2:
                date_str = parts[0]
                scope = parts[1]
                # Validate date format
                datetime.strptime(date_str, "%Y-%m-%d")
                reports.append({"date": date_str, "scope": scope, "path": md_file})
        except ValueError:
            continue
    
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
    for scope in ["global", "software"]:
        scope_reports = [r for r in all_reports if r["scope"] == scope]
        if scope_reports:
            latest_report = scope_reports[0]
            latest[scope] = {
                "date": latest_report["date"],
                "markdown": f"reports/{latest_report['date']}.{scope}.md",
                "json": f"data/{latest_report['date']}.{scope}.json",
            }
    
    # Build reports array
    reports_list = []
    for report in all_reports:
        date = report["date"]
        scope = report["scope"]
        md_path = report["path"]
        json_path = data_dir / f"{date}.{scope}.json"
        telegram_path = telegram_dir / f"{date}.{scope}.txt"
        
        # Read markdown for excerpt
        try:
            md_content = md_path.read_text(encoding="utf-8")
            summary = extract_section_from_markdown(md_content, "Executive Summary")
            excerpt = make_excerpt(summary) if summary else "Report disponibile."
        except Exception:
            excerpt = "Report disponibile."
        
        # Load ranking for top10
        csv_path = SNAPSHOTS_DIR / f"{date}.{scope}.csv"
        ranking = load_ranking_from_csv(csv_path)
        top10 = ranking[:10]
        
        # Determine title
        scope_label = "Asset Globali" if scope == "global" else "Aziende Software"
        title = f"Report Settimanale {scope_label} - {date}"
        
        reports_list.append({
            "date": date,
            "scope": scope,
            "title": title,
            "source": "Yahoo Finance",
            "disclaimer": DISCLAIMER_SHORT,
            "paths": {
                "markdown": f"reports/{date}.{scope}.md",
                "json": f"data/{date}.{scope}.json" if json_path.exists() else None,
                "telegram": f"telegram/{date}.{scope}.txt" if telegram_path.exists() else None,
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
        scope_label = "Asset Globali" if scope == "global" else "Aziende Software"
        latest_links += f'<li><a href="{info["markdown"]}">{scope_label}</a> ({info["date"]})</li>\n'
    
    reports_links = ""
    for r in reports:
        reports_links += f'<li><a href="{r["paths"]["markdown"]}">{r["title"]}</a></li>\n'
    
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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


def build_public(date: str, scopes: List[str]) -> bool:
    """
    Build the public/ folder with all static assets.
    
    Args:
        date: Report date to publish
        scopes: List of scopes to include (global, software)
    
    Returns:
        True if successful
    """
    logger.info(f"Building public/ for date={date}, scopes={scopes}")
    
    # Create directories
    public_reports = PUBLIC_DIR / "reports"
    public_data = PUBLIC_DIR / "data"
    public_telegram = PUBLIC_DIR / "telegram"
    
    for d in [PUBLIC_DIR, public_reports, public_data, public_telegram]:
        d.mkdir(parents=True, exist_ok=True)
    
    published_count = 0
    
    for scope in scopes:
        try:
            # Source paths
            md_src = REPORTS_DIR / f"{date}.{scope}.md"
            csv_src = SNAPSHOTS_DIR / f"{date}.{scope}.csv"
            json_src = SNAPSHOTS_DIR / f"{date}.{scope}.json"
            telegram_src = SNAPSHOTS_DIR / f"{date}.telegram.{scope}.txt"
            
            # Check if markdown exists
            if not md_src.exists():
                logger.warning(f"Report not found: {md_src}")
                continue
            
            # Copy markdown
            md_dst = public_reports / f"{date}.{scope}.md"
            shutil.copy2(md_src, md_dst)
            logger.info(f"Copied: {md_dst}")
            
            # Generate report JSON from CSV
            ranking = load_ranking_from_csv(csv_src)
            metrics = load_metrics_from_json(json_src)
            
            telegram_dst = public_telegram / f"{date}.{scope}.txt"
            report_json = generate_report_json(
                date, scope, ranking, metrics, md_dst,
                telegram_src if telegram_src.exists() else None
            )
            
            json_dst = public_data / f"{date}.{scope}.json"
            with open(json_dst, "w", encoding="utf-8") as f:
                json.dump(report_json, f, indent=2, ensure_ascii=False)
            logger.info(f"Generated: {json_dst}")
            
            # Copy telegram if exists
            if telegram_src.exists():
                shutil.copy2(telegram_src, telegram_dst)
                logger.info(f"Copied: {telegram_dst}")
            
            published_count += 1
            
        except Exception as e:
            logger.error(f"Failed to publish {scope} report: {e}")
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

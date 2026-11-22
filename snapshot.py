"""Reading and writing the weekly snapshots of a ranking."""

import csv
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from asset import Asset
from report_id import DATE_FORMAT, ReportId

logger = logging.getLogger(__name__)

CSV_FIELDS = ["rank", "ticker", "name", "quote_type", "currency", "market_cap", "price", "sector", "industry"]

# How far back to look for the snapshot to compare with
PREVIOUS_SNAPSHOT_DAYS = 14


def _asset_from_row(row: Dict[str, str]) -> Asset:
    """Build an asset from a CSV row, where every value is a string."""
    price = row.get("price")
    return Asset(
        rank=int(row["rank"]),
        ticker=row["ticker"],
        name=row["name"],
        quote_type=row["quote_type"],
        currency=row["currency"],
        market_cap=float(row["market_cap"]),
        price=float(price) if price else None,
        sector=row.get("sector") or "",
        industry=row.get("industry") or "",
    )


def load_snapshot(csv_path: Path) -> Optional[List[Asset]]:
    """
    Load the ranked assets of a CSV snapshot.

    Returns None when the file is missing or cannot be read as a snapshot.
    """
    if not csv_path.exists():
        return None

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            return [_asset_from_row(row) for row in csv.DictReader(f)]
    except (OSError, UnicodeDecodeError, csv.Error, KeyError, ValueError, TypeError) as e:
        # KeyError: a missing column; ValueError/TypeError: a missing or non-numeric value
        logger.warning(f"Error reading snapshot {csv_path}: {e}")
        return None


def load_previous_snapshot(snapshots_dir: Path, scope: str, current_date: str) -> Optional[Dict[str, Asset]]:
    """
    Load the most recent previous snapshot for comparison.
    Returns a dict mapping ticker -> asset, or None when there is none to compare with.
    """
    current = datetime.strptime(current_date, DATE_FORMAT)

    for days_back in range(1, PREVIOUS_SNAPSHOT_DAYS + 1):
        prev_date = (current - timedelta(days=days_back)).strftime(DATE_FORMAT)
        csv_path = snapshots_dir / ReportId(prev_date, scope).csv_name

        if csv_path.exists():
            logger.info(f"Found previous snapshot: {csv_path}")
            assets = load_snapshot(csv_path)
            if assets is None:
                return None
            return {asset.ticker: asset for asset in assets}

    logger.info(f"No previous snapshot found for {scope}")
    return None


def save_snapshot_csv(ranked_assets: List[Asset], filepath: Path) -> None:
    """Save ranked assets to CSV."""
    if not ranked_assets:
        return

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(asset.to_dict() for asset in ranked_assets)

    logger.info(f"Saved snapshot: {filepath}")


def save_snapshot_json(ranked_assets: List[Asset], metrics: Dict[str, Any], filepath: Path) -> None:
    """Save ranked assets and metrics to JSON."""
    data = {
        "assets": [asset.to_dict() for asset in ranked_assets],
        "metrics": metrics,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved JSON snapshot: {filepath}")

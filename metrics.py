"""Ranking and metrics calculations."""

import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def rank_by_market_cap(assets: List[Dict[str, Any]], top_n: int = 50) -> List[Dict[str, Any]]:
    """Sort assets by market cap descending and return top N."""
    sorted_assets = sorted(assets, key=lambda x: x.get("market_cap", 0), reverse=True)
    ranked = []
    for i, asset in enumerate(sorted_assets[:top_n], 1):
        asset["rank"] = i
        ranked.append(asset)
    return ranked


def calculate_metrics(ranked_assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate key metrics for the ranked assets."""
    if not ranked_assets:
        return {}
    
    total_market_cap = sum(a.get("market_cap", 0) for a in ranked_assets)
    top5_cap = sum(a.get("market_cap", 0) for a in ranked_assets[:5])
    top10_cap = sum(a.get("market_cap", 0) for a in ranked_assets[:10])
    
    return {
        "total_market_cap": total_market_cap,
        "top5_concentration": (top5_cap / total_market_cap * 100) if total_market_cap > 0 else 0,
        "top10_concentration": (top10_cap / total_market_cap * 100) if total_market_cap > 0 else 0,
        "asset_count": len(ranked_assets),
        "top5_cap": top5_cap,
        "top10_cap": top10_cap,
    }


def format_market_cap(value: float) -> str:
    """Format market cap in human-readable form."""
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    elif value >= 1e9:
        return f"${value / 1e9:.2f}B"
    elif value >= 1e6:
        return f"${value / 1e6:.2f}M"
    else:
        return f"${value:,.0f}"


def load_previous_snapshot(snapshots_dir: Path, scope: str, current_date: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Load the most recent previous snapshot for comparison.
    Returns a dict mapping ticker -> asset data.
    """
    current = datetime.strptime(current_date, "%Y-%m-%d")
    
    # Look for snapshots in the last 14 days
    for days_back in range(1, 15):
        prev_date = (current - timedelta(days=days_back)).strftime("%Y-%m-%d")
        csv_path = snapshots_dir / f"{prev_date}.{scope}.csv"
        
        if csv_path.exists():
            logger.info(f"Found previous snapshot: {csv_path}")
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    return {row["ticker"]: row for row in reader}
            except Exception as e:
                logger.warning(f"Error loading previous snapshot: {e}")
                return None
    
    logger.info(f"No previous snapshot found for {scope}")
    return None


def calculate_changes(
    ranked_assets: List[Dict[str, Any]],
    previous: Optional[Dict[str, Dict[str, Any]]]
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """
    Calculate entries, exits, and rank changes compared to previous snapshot.
    Returns (entries, exits, movers).
    """
    current_tickers = {a["ticker"] for a in ranked_assets}
    
    if previous is None:
        return [], [], []
    
    previous_tickers = set(previous.keys())
    
    entries = list(current_tickers - previous_tickers)
    exits = list(previous_tickers - current_tickers)
    
    # Calculate rank changes for assets in both snapshots
    movers = []
    for asset in ranked_assets:
        ticker = asset["ticker"]
        if ticker in previous:
            prev_rank = int(previous[ticker].get("rank", 0))
            curr_rank = asset["rank"]
            rank_delta = prev_rank - curr_rank  # Positive = moved up
            
            prev_cap = float(previous[ticker].get("market_cap", 0))
            curr_cap = asset.get("market_cap", 0)
            cap_delta_pct = ((curr_cap - prev_cap) / prev_cap * 100) if prev_cap > 0 else 0
            
            if rank_delta != 0 or abs(cap_delta_pct) > 5:
                movers.append({
                    "ticker": ticker,
                    "name": asset["name"],
                    "rank_delta": rank_delta,
                    "cap_delta_pct": cap_delta_pct,
                    "current_rank": curr_rank,
                })
    
    # Sort movers by absolute rank change
    movers.sort(key=lambda x: abs(x["rank_delta"]), reverse=True)
    
    return entries, exits, movers[:10]  # Top 10 movers


def save_snapshot_csv(ranked_assets: List[Dict[str, Any]], filepath: Path) -> None:
    """Save ranked assets to CSV."""
    if not ranked_assets:
        return
    
    fieldnames = ["rank", "ticker", "name", "quote_type", "currency", "market_cap", "price", "sector", "industry"]
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ranked_assets)
    
    logger.info(f"Saved snapshot: {filepath}")


def save_snapshot_json(ranked_assets: List[Dict[str, Any]], metrics: Dict[str, Any], filepath: Path) -> None:
    """Save ranked assets and metrics to JSON."""
    data = {
        "assets": ranked_assets,
        "metrics": metrics,
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved JSON snapshot: {filepath}")

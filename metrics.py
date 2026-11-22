"""Ranking and metrics calculations."""

from typing import List, Dict, Any, Optional, Tuple

from asset import Asset


def rank_by_market_cap(assets: List[Asset], top_n: int = 50) -> List[Asset]:
    """Sort assets by market cap descending and return top N."""
    sorted_assets = sorted(assets, key=lambda asset: asset.market_cap, reverse=True)
    return [asset.ranked(i) for i, asset in enumerate(sorted_assets[:top_n], 1)]


def calculate_metrics(ranked_assets: List[Asset]) -> Dict[str, Any]:
    """Calculate key metrics for the ranked assets."""
    if not ranked_assets:
        return {}
    
    total_market_cap = sum(a.market_cap for a in ranked_assets)
    top5_cap = sum(a.market_cap for a in ranked_assets[:5])
    top10_cap = sum(a.market_cap for a in ranked_assets[:10])
    
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


def calculate_changes(
    ranked_assets: List[Asset],
    previous: Optional[Dict[str, Asset]]
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """
    Calculate entries, exits, and rank changes compared to previous snapshot.
    Returns (entries, exits, movers).
    """
    if previous is None:
        return [], [], []
    
    current_tickers = {a.ticker for a in ranked_assets}
    
    # Deterministic order: entries by current rank, exits by previous rank
    entries = [a.ticker for a in ranked_assets if a.ticker not in previous]
    exits = sorted(
        previous.keys() - current_tickers,
        key=lambda ticker: previous[ticker].rank,
    )
    
    # Calculate rank changes for assets in both snapshots
    movers = []
    for asset in ranked_assets:
        before = previous.get(asset.ticker)
        if before is None:
            continue

        rank_delta = before.rank - asset.rank  # Positive = moved up
        cap_delta_pct = (
            (asset.market_cap - before.market_cap) / before.market_cap * 100
            if before.market_cap > 0
            else 0
        )

        if rank_delta != 0 or abs(cap_delta_pct) > 5:
            movers.append({
                "ticker": asset.ticker,
                "name": asset.name,
                "rank_delta": rank_delta,
                "cap_delta_pct": cap_delta_pct,
                "current_rank": asset.rank,
            })
    
    # Sort movers by absolute rank change
    movers.sort(key=lambda x: abs(x["rank_delta"]), reverse=True)
    
    return entries, exits, movers[:10]  # Top 10 movers

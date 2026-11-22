"""The asset a report ranks."""

from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, Optional


@dataclass(frozen=True, kw_only=True)
class Asset:
    """
    A market asset as Yahoo Finance describes it.

    `rank` is its position by market cap, and is None until the asset is ranked.
    Fields are declared in the order they are written to snapshots.
    """
    ticker: str
    name: str
    quote_type: str = "UNKNOWN"
    currency: str = "USD"
    market_cap: float
    price: Optional[float] = None
    sector: str = ""
    industry: str = ""
    rank: Optional[int] = None

    def ranked(self, rank: int) -> "Asset":
        """The same asset at the given position."""
        return replace(self, rank=rank)

    def to_dict(self) -> Dict[str, Any]:
        """Plain data for JSON and CSV; an unranked asset has no rank."""
        data = asdict(self)
        if self.rank is None:
            del data["rank"]
        return data

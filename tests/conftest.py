"""Shared fixtures. The application modules live at the repository root."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from asset import Asset  # noqa: E402  (needs the path set above)


def _asset(rank, ticker, name, market_cap, quote_type="EQUITY"):
    return Asset(
        rank=rank,
        ticker=ticker,
        name=name,
        quote_type=quote_type,
        currency="USD",
        market_cap=market_cap,
        price=100.0,
        sector="Technology",
        industry="Software",
    )


@pytest.fixture
def ranked():
    """Six ranked assets whose market caps add up to exactly $1T."""
    return [
        _asset(1, "AAA", "Alpha Corp", 500e9),
        _asset(2, "BBB", "Beta Inc", 300e9),
        _asset(3, "CCC", "Gamma Ltd", 100e9),
        _asset(4, "DDD", "Delta SA", 50e9),
        _asset(5, "EEE", "Epsilon AG", 30e9),
        _asset(6, "FFF", "Phi Fund", 20e9, quote_type="ETF"),
    ]


@pytest.fixture
def llm_sections():
    return {
        "executive_summary": "Summary text.",
        "strategic_reflection": "Reflection text.",
        "implications": "Implications text.",
    }

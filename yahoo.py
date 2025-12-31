"""Yahoo Finance data fetching."""

import logging
from typing import List, Dict, Any, Optional
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_ticker_data(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch data for a single ticker.
    Returns None if ticker is invalid or missing market cap.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        if not info:
            logger.warning(f"No data returned for {ticker}")
            return None
        
        market_cap = info.get("marketCap")
        if market_cap is None or market_cap == 0:
            logger.warning(f"Skipping {ticker}: no marketCap available")
            return None
        
        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "quote_type": info.get("quoteType", "UNKNOWN"),
            "currency": info.get("currency", "USD"),
            "market_cap": market_cap,
            "price": info.get("regularMarketPrice") or info.get("previousClose"),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
        }
    except Exception as e:
        logger.warning(f"Error fetching {ticker}: {e}")
        return None


def fetch_all_tickers(tickers: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch data for all tickers.
    Skips tickers that fail or have no market cap.
    """
    results = []
    total = len(tickers)
    
    for i, ticker in enumerate(tickers, 1):
        logger.info(f"Fetching {ticker} ({i}/{total})")
        data = fetch_ticker_data(ticker)
        if data:
            results.append(data)
    
    logger.info(f"Successfully fetched {len(results)}/{total} tickers")
    return results

"""Configuration and whitelist loading."""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Base directories
PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = DATA_DIR / "config"
REPORTS_DIR = DATA_DIR / "reports"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
RAG_DIR = DATA_DIR / "rag"

# Ensure output directories exist
for d in [REPORTS_DIR, SNAPSHOTS_DIR, RAG_DIR]:
    d.mkdir(exist_ok=True)

# Default tickers if no config file exists
DEFAULT_GLOBAL_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "UNH", "JNJ", "XOM", "WMT", "MA", "PG", "HD", "CVX",
    "SPY", "QQQ", "BTC-USD", "ETH-USD"
]

# Disclaimer text
DISCLAIMER = (
    "This report is for informational purposes only and does not constitute "
    "financial advice. Past performance is not indicative of future results. "
    "Always conduct your own research before making investment decisions."
)

DISCLAIMER_SHORT = "Not financial advice. For informational purposes only."


def load_tickers_from_file(filepath: Path) -> List[str]:
    """Load tickers from a file, one per line. Lines starting with # are comments."""
    tickers = []
    if not filepath.exists():
        return tickers
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()  # Remove comments
            if line:
                tickers.append(line.upper())
    return tickers


def get_global_tickers() -> List[str]:
    """Get global tickers from config file or use defaults."""
    filepath = CONFIG_DIR / "global_tickers.txt"
    tickers = load_tickers_from_file(filepath)
    return tickers if tickers else DEFAULT_GLOBAL_TICKERS


def get_software_tickers() -> List[str]:
    """Get software tickers from whitelist file."""
    filepath = CONFIG_DIR / "software_tickers.txt"
    tickers = load_tickers_from_file(filepath)
    if not tickers:
        raise ValueError("software_tickers.txt is empty or missing")
    return tickers


def get_openai_api_key() -> str | None:
    """Get OpenAI API key from environment."""
    return os.environ.get("OPENAI_API_KEY")

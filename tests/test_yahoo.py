import pytest

import yahoo
from asset import Asset


@pytest.fixture
def yahoo_returns(monkeypatch):
    """Replace yfinance with canned `info` per ticker; an exception value is raised."""

    def install(info_by_ticker):
        class FakeTicker:
            def __init__(self, symbol):
                self.symbol = symbol

            @property
            def info(self):
                result = info_by_ticker[self.symbol]
                if isinstance(result, Exception):
                    raise result
                return result

        monkeypatch.setattr(yahoo.yf, "Ticker", FakeTicker)

    return install


FULL_INFO = {
    "longName": "Alpha Corporation",
    "shortName": "Alpha",
    "quoteType": "EQUITY",
    "currency": "EUR",
    "marketCap": 500e9,
    "regularMarketPrice": 123.4,
    "previousClose": 120.0,
    "sector": "Technology",
    "industry": "Software",
}


def test_ticker_data_is_mapped_from_yahoo_info(yahoo_returns):
    yahoo_returns({"AAA": FULL_INFO})

    assert yahoo.fetch_ticker_data("AAA") == Asset(
        ticker="AAA",
        name="Alpha Corporation",
        quote_type="EQUITY",
        currency="EUR",
        market_cap=500e9,
        price=123.4,
        sector="Technology",
        industry="Software",
    )


def test_missing_optional_fields_get_defaults(yahoo_returns):
    yahoo_returns({"AAA": {"marketCap": 1e9, "shortName": "Alpha", "previousClose": 9.5}})

    data = yahoo.fetch_ticker_data("AAA")

    assert data.name == "Alpha"
    assert data.price == 9.5
    assert data.quote_type == "UNKNOWN"
    assert data.currency == "USD"
    assert data.sector == ""
    assert data.rank is None


def test_name_falls_back_to_the_ticker(yahoo_returns):
    yahoo_returns({"AAA": {"marketCap": 1e9}})

    assert yahoo.fetch_ticker_data("AAA").name == "AAA"


@pytest.mark.parametrize("info", [{}, None, {"longName": "No Cap"}, {"marketCap": 0}])
def test_ticker_without_market_cap_is_skipped(yahoo_returns, info):
    yahoo_returns({"AAA": info})

    assert yahoo.fetch_ticker_data("AAA") is None


def test_ticker_that_yahoo_fails_on_is_skipped(yahoo_returns):
    yahoo_returns({"AAA": ConnectionError("network down")})

    assert yahoo.fetch_ticker_data("AAA") is None


def test_fetch_all_keeps_the_valid_tickers_in_order(yahoo_returns):
    yahoo_returns(
        {
            "AAA": FULL_INFO,
            "BAD": RuntimeError("delisted"),
            "NOCAP": {"longName": "No Cap"},
            "BBB": {"marketCap": 2e9},
        }
    )

    assets = yahoo.fetch_all_tickers(["AAA", "BAD", "NOCAP", "BBB"])

    assert [a.ticker for a in assets] == ["AAA", "BBB"]

import pytest

from asset import Asset
from metrics import calculate_changes, calculate_metrics, format_market_cap, rank_by_market_cap


def asset(ticker, market_cap, rank=None):
    return Asset(ticker=ticker, name="n", market_cap=market_cap, rank=rank)


def test_rank_orders_by_market_cap_descending_and_numbers_from_one():
    assets = [asset("SMALL", 1), asset("BIG", 3), asset("MID", 2)]

    ranked = rank_by_market_cap(assets)

    assert [(a.rank, a.ticker) for a in ranked] == [(1, "BIG"), (2, "MID"), (3, "SMALL")]


def test_rank_keeps_only_top_n():
    assets = [asset(str(cap), cap) for cap in range(10)]

    assert [a.ticker for a in rank_by_market_cap(assets, top_n=2)] == ["9", "8"]


def test_ranking_leaves_the_given_assets_untouched():
    assets = [asset("AAA", 1)]

    rank_by_market_cap(assets)

    assert assets == [asset("AAA", 1)]


def test_metrics_report_total_and_concentration(ranked):
    metrics = calculate_metrics(ranked)

    assert metrics["total_market_cap"] == 1e12
    assert metrics["top5_concentration"] == pytest.approx(98.0)
    assert metrics["top10_concentration"] == pytest.approx(100.0)
    assert metrics["asset_count"] == 6


def test_metrics_of_nothing_are_empty():
    assert calculate_metrics([]) == {}


@pytest.mark.parametrize(
    "value, expected",
    [(2.5e12, "$2.50T"), (3.2e9, "$3.20B"), (4.5e6, "$4.50M"), (999, "$999")],
)
def test_format_market_cap(value, expected):
    assert format_market_cap(value) == expected


def test_no_changes_without_a_previous_snapshot(ranked):
    assert calculate_changes(ranked, None) == ([], [], [])


def test_changes_report_entries_exits_and_rank_movers(ranked):
    previous = {
        "AAA": asset("AAA", 500e9, rank=1),
        "CCC": asset("CCC", 100e9, rank=2),
        "BBB": asset("BBB", 300e9, rank=3),
        "ZZZ": asset("ZZZ", 40e9, rank=4),
    }

    entries, exits, movers = calculate_changes(ranked, previous)

    assert set(entries) == {"DDD", "EEE", "FFF"}
    assert exits == ["ZZZ"]
    assert [(m["ticker"], m["rank_delta"]) for m in movers] == [("BBB", 1), ("CCC", -1)]


def test_large_cap_change_is_a_mover_even_at_the_same_rank(ranked):
    previous = {"AAA": asset("AAA", 400e9, rank=1)}

    _, _, movers = calculate_changes(ranked[:1], previous)

    assert movers[0]["rank_delta"] == 0
    assert movers[0]["cap_delta_pct"] == pytest.approx(25.0)


def test_entries_follow_current_rank_and_exits_follow_previous_rank():
    current = [asset(f"NEW{i:02d}", 100 - i, rank=i) for i in range(1, 13)]
    old_tickers = [f"OLD{(i * 7) % 12:02d}" for i in range(1, 13)]
    previous = {ticker: asset(ticker, 10, rank=i) for i, ticker in enumerate(old_tickers, 1)}

    entries, exits, _ = calculate_changes(current, previous)

    assert entries == [f"NEW{i:02d}" for i in range(1, 13)]
    assert exits == old_tickers

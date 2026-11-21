import csv
import json

import pytest

from metrics import (
    calculate_changes,
    calculate_metrics,
    format_market_cap,
    load_previous_snapshot,
    rank_by_market_cap,
    save_snapshot_csv,
    save_snapshot_json,
)


def previous_row(rank, market_cap):
    """A row as csv.DictReader returns it: every value is a string."""
    return {"rank": str(rank), "market_cap": str(market_cap)}


def test_rank_orders_by_market_cap_descending_and_numbers_from_one():
    assets = [
        {"ticker": "SMALL", "market_cap": 1},
        {"ticker": "BIG", "market_cap": 3},
        {"ticker": "MID", "market_cap": 2},
    ]

    ranked = rank_by_market_cap(assets)

    assert [(a["rank"], a["ticker"]) for a in ranked] == [(1, "BIG"), (2, "MID"), (3, "SMALL")]


def test_rank_keeps_only_top_n():
    assets = [{"ticker": str(cap), "market_cap": cap} for cap in range(10)]

    assert [a["ticker"] for a in rank_by_market_cap(assets, top_n=2)] == ["9", "8"]


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


def test_previous_snapshot_is_the_closest_earlier_one(tmp_path, ranked):
    save_snapshot_csv(ranked, tmp_path / "2025-12-17.global.csv")
    save_snapshot_csv(ranked[:2], tmp_path / "2025-12-24.global.csv")
    save_snapshot_csv(ranked[:1], tmp_path / "2025-12-31.global.csv")

    previous = load_previous_snapshot(tmp_path, "global", "2025-12-31")

    assert set(previous) == {"AAA", "BBB"}
    assert previous["AAA"]["rank"] == "1"


def test_previous_snapshot_older_than_two_weeks_is_ignored(tmp_path, ranked):
    save_snapshot_csv(ranked, tmp_path / "2025-12-01.global.csv")

    assert load_previous_snapshot(tmp_path, "global", "2025-12-31") is None


def test_no_changes_without_a_previous_snapshot(ranked):
    assert calculate_changes(ranked, None) == ([], [], [])


def test_changes_report_entries_exits_and_rank_movers(ranked):
    previous = {
        "AAA": previous_row(1, 500e9),
        "CCC": previous_row(2, 100e9),
        "BBB": previous_row(3, 300e9),
        "ZZZ": previous_row(4, 40e9),
    }

    entries, exits, movers = calculate_changes(ranked, previous)

    assert set(entries) == {"DDD", "EEE", "FFF"}
    assert exits == ["ZZZ"]
    assert [(m["ticker"], m["rank_delta"]) for m in movers] == [("BBB", 1), ("CCC", -1)]


def test_large_cap_change_is_a_mover_even_at_the_same_rank(ranked):
    previous = {"AAA": previous_row(1, 400e9)}

    _, _, movers = calculate_changes(ranked[:1], previous)

    assert movers[0]["rank_delta"] == 0
    assert movers[0]["cap_delta_pct"] == pytest.approx(25.0)


def test_entries_follow_current_rank_and_exits_follow_previous_rank():
    current = [
        {"rank": i, "ticker": f"NEW{i:02d}", "name": "n", "market_cap": 100 - i}
        for i in range(1, 13)
    ]
    previous = {f"OLD{(i * 7) % 12:02d}": previous_row(i, 10) for i in range(1, 13)}

    entries, exits, _ = calculate_changes(current, previous)

    assert entries == [f"NEW{i:02d}" for i in range(1, 13)]
    assert exits == [f"OLD{(i * 7) % 12:02d}" for i in range(1, 13)]


def test_snapshot_csv_round_trips_the_ranking(tmp_path, ranked):
    path = tmp_path / "snapshot.csv"

    save_snapshot_csv(ranked, path)

    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["ticker"] for r in rows] == [a["ticker"] for a in ranked]
    assert float(rows[0]["market_cap"]) == 500e9


def test_snapshot_json_holds_assets_and_metrics(tmp_path, ranked):
    path = tmp_path / "snapshot.json"

    save_snapshot_json(ranked, {"asset_count": 6}, path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metrics"] == {"asset_count": 6}
    assert len(data["assets"]) == 6


def test_ranking_leaves_the_given_assets_untouched():
    assets = [{"ticker": "AAA", "market_cap": 1}]

    rank_by_market_cap(assets)

    assert assets == [{"ticker": "AAA", "market_cap": 1}]

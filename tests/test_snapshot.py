import csv
import json
from dataclasses import replace

from snapshot import load_previous_snapshot, load_snapshot, save_snapshot_csv, save_snapshot_json


def test_snapshot_csv_round_trips_the_ranking(tmp_path, ranked):
    path = tmp_path / "snapshot.csv"

    save_snapshot_csv(ranked, path)

    assert load_snapshot(path) == ranked


def test_snapshot_csv_columns(tmp_path, ranked):
    path = tmp_path / "snapshot.csv"

    save_snapshot_csv(ranked, path)

    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "rank", "ticker", "name", "quote_type", "currency", "market_cap", "price", "sector", "industry",
    ]
    assert rows[1][:3] == ["1", "AAA", "Alpha Corp"]


def test_asset_without_a_price_round_trips(tmp_path, ranked):
    path = tmp_path / "snapshot.csv"
    unpriced = [replace(ranked[0], price=None)]

    save_snapshot_csv(unpriced, path)

    assert load_snapshot(path) == unpriced


def test_missing_snapshot_is_none(tmp_path):
    assert load_snapshot(tmp_path / "missing.csv") is None


def test_snapshot_with_a_missing_column_is_none(tmp_path):
    path = tmp_path / "snapshot.csv"
    path.write_text("rank,name\n1,Alpha\n", encoding="utf-8")

    assert load_snapshot(path) is None


def test_snapshot_with_a_non_numeric_market_cap_is_none(tmp_path, ranked):
    path = tmp_path / "snapshot.csv"
    save_snapshot_csv(ranked, path)
    path.write_text(path.read_text(encoding="utf-8").replace("500000000000.0", "n/a"), encoding="utf-8")

    assert load_snapshot(path) is None


def test_snapshot_json_holds_assets_and_metrics(tmp_path, ranked):
    path = tmp_path / "snapshot.json"

    save_snapshot_json(ranked, {"asset_count": 6}, path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metrics"] == {"asset_count": 6}
    assert data["assets"][0] == ranked[0].to_dict()
    assert len(data["assets"]) == 6


def test_previous_snapshot_is_the_closest_earlier_one(tmp_path, ranked):
    save_snapshot_csv(ranked, tmp_path / "2025-12-17.global.csv")
    save_snapshot_csv(ranked[:2], tmp_path / "2025-12-24.global.csv")
    save_snapshot_csv(ranked[:1], tmp_path / "2025-12-31.global.csv")

    previous = load_previous_snapshot(tmp_path, "global", "2025-12-31")

    assert set(previous) == {"AAA", "BBB"}
    assert previous["AAA"] == ranked[0]


def test_previous_snapshot_older_than_two_weeks_is_ignored(tmp_path, ranked):
    save_snapshot_csv(ranked, tmp_path / "2025-12-01.global.csv")

    assert load_previous_snapshot(tmp_path, "global", "2025-12-31") is None


def test_unreadable_previous_snapshot_is_ignored(tmp_path):
    (tmp_path / "2025-12-24.global.csv").write_text("rank,name\n1,Alpha\n", encoding="utf-8")

    assert load_previous_snapshot(tmp_path, "global", "2025-12-31") is None

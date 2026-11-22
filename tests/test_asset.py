from asset import Asset


def test_an_asset_is_unranked_until_it_is_given_a_rank():
    asset = Asset(ticker="AAA", name="Alpha Corp", market_cap=1e9)

    assert asset.rank is None
    assert asset.ranked(3).rank == 3
    assert asset.rank is None


def test_dict_of_a_ranked_asset_lists_the_fields_in_snapshot_order(ranked):
    assert list(ranked[0].to_dict().items()) == [
        ("ticker", "AAA"),
        ("name", "Alpha Corp"),
        ("quote_type", "EQUITY"),
        ("currency", "USD"),
        ("market_cap", 500e9),
        ("price", 100.0),
        ("sector", "Technology"),
        ("industry", "Software"),
        ("rank", 1),
    ]


def test_dict_of_an_unranked_asset_has_no_rank():
    assert "rank" not in Asset(ticker="AAA", name="Alpha Corp", market_cap=1e9).to_dict()

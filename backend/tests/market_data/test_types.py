from app.market_data.types import Direction, PriceTick


def test_create_sets_up_direction():
    tick = PriceTick.create("AAPL", 191.0, 190.0)
    assert tick.direction == Direction.UP

    tick = PriceTick.create("AAPL", 189.0, 190.0)
    assert tick.direction == Direction.DOWN

    tick = PriceTick.create("AAPL", 190.0, 190.0)
    assert tick.direction == Direction.FLAT


def test_create_rounds_prices():
    tick = PriceTick.create("AAPL", 191.123456, 190.987654)
    assert tick.price == 191.1235
    assert tick.prev_price == 190.9877


def test_create_sets_iso_utc_timestamp():
    tick = PriceTick.create("AAPL", 191.0, 190.0)
    assert tick.timestamp.endswith("+00:00")


def test_to_sse_dict_shape():
    tick = PriceTick.create("AAPL", 191.0, 190.0, day_change_percent=0.53)
    payload = tick.to_sse_dict()
    assert payload == {
        "ticker": "AAPL",
        "price": 191.0,
        "prev_price": 190.0,
        "timestamp": tick.timestamp,
        "direction": "up",
        "day_change_percent": 0.53,
    }


def test_create_defaults_day_change_percent_to_none():
    tick = PriceTick.create("AAPL", 191.0, 190.0)
    assert tick.day_change_percent is None
    assert tick.to_sse_dict()["day_change_percent"] is None


def test_create_rounds_day_change_percent():
    tick = PriceTick.create("AAPL", 191.0, 190.0, day_change_percent=1.23456)
    assert tick.day_change_percent == 1.2346

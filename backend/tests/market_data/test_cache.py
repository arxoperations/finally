import asyncio

import pytest

from app.market_data.cache import PriceCache
from app.market_data.types import PriceTick


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


async def test_update_stores_latest_price(cache: PriceCache):
    tick = PriceTick.create("AAPL", 191.0, 190.0)
    await cache.update(tick)

    cached = cache.get("AAPL")
    assert cached is not None
    assert cached.price == 191.0
    assert cached.prev_price == 190.0


async def test_snapshot_returns_a_copy(cache: PriceCache):
    await cache.update(PriceTick.create("AAPL", 191.0, 190.0))

    snapshot = cache.snapshot()
    snapshot["AAPL"].price = 0.0

    assert cache.get("AAPL").price == 191.0


async def test_update_stores_day_change_percent(cache: PriceCache):
    tick = PriceTick.create("AAPL", 191.0, 190.0, day_change_percent=2.5)
    await cache.update(tick)

    assert cache.get("AAPL").day_change_percent == 2.5


async def test_snapshot_includes_day_change_percent(cache: PriceCache):
    await cache.update(PriceTick.create("AAPL", 191.0, 190.0, day_change_percent=2.5))

    assert cache.snapshot()["AAPL"].day_change_percent == 2.5


def test_get_returns_none_for_unknown_ticker(cache: PriceCache):
    assert cache.get("UNKNOWN") is None


async def test_subscribers_receive_ticks(cache: PriceCache):
    queue = cache.subscribe()
    tick = PriceTick.create("AAPL", 191.0, 190.0)
    await cache.update(tick)

    received = await asyncio.wait_for(queue.get(), timeout=1)
    assert received.ticker == "AAPL"
    assert received.price == 191.0


async def test_unsubscribe_stops_delivery(cache: PriceCache):
    queue = cache.subscribe()
    cache.unsubscribe(queue)

    await cache.update(PriceTick.create("AAPL", 191.0, 190.0))

    assert queue.empty()


async def test_full_subscriber_queue_is_dropped_without_blocking(cache: PriceCache):
    queue = cache.subscribe()
    # Llenamos la cola del suscriptor para forzar asyncio.QueueFull en el próximo update.
    for _ in range(queue.maxsize):
        queue.put_nowait(PriceTick.create("AAPL", 1.0, 1.0))

    # No debe lanzar excepción ni bloquear: el suscriptor lento se desconecta.
    await cache.update(PriceTick.create("AAPL", 191.0, 190.0))

    assert cache.get("AAPL").price == 191.0


async def test_multiple_subscribers_all_receive_the_same_tick(cache: PriceCache):
    queues = [cache.subscribe() for _ in range(3)]
    tick = PriceTick.create("AAPL", 191.0, 190.0)

    await cache.update(tick)

    for queue in queues:
        received = await asyncio.wait_for(queue.get(), timeout=1)
        assert received.ticker == "AAPL"
        assert received.price == 191.0


async def test_unsubscribing_one_does_not_affect_others(cache: PriceCache):
    keep, drop = cache.subscribe(), cache.subscribe()
    cache.unsubscribe(drop)

    await cache.update(PriceTick.create("AAPL", 191.0, 190.0))

    assert not keep.empty()
    assert drop.empty()

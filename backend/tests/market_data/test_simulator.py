import asyncio

import pytest

from app.market_data.base import MarketDataProvider
from app.market_data.simulator import MarketSimulator
from app.market_data.simulator_config import DEFAULT_TICKERS, GENERIC_SEED_PRICE_RANGE
from app.market_data.types import PriceTick


def make_simulator(seed: int = 42) -> tuple[MarketSimulator, list[PriceTick]]:
    received: list[PriceTick] = []

    async def on_tick(tick: PriceTick) -> None:
        received.append(tick)

    return MarketSimulator(on_tick, seed=seed), received


def test_implements_market_data_provider_interface():
    assert issubclass(MarketSimulator, MarketDataProvider)


def test_starts_with_default_tickers():
    sim, _ = make_simulator()
    assert sim.tickers == frozenset(DEFAULT_TICKERS.keys())


async def test_tick_once_emits_positive_prices_for_all_tickers():
    sim, received = make_simulator()
    ticks = await sim.tick_once()

    assert len(ticks) == len(DEFAULT_TICKERS)
    assert len(received) == len(DEFAULT_TICKERS)
    assert all(t.price > 0 for t in ticks)


async def test_tick_once_moves_prices_away_from_seed():
    sim, _ = make_simulator()
    seed_prices = {t: cfg.seed_price for t, cfg in DEFAULT_TICKERS.items()}

    for _ in range(20):
        await sim.tick_once()

    assert any(sim.current_price(t) != seed_prices[t] for t in DEFAULT_TICKERS)


def test_add_known_ticker_uses_its_seed_price():
    sim, _ = make_simulator()
    sim.remove_ticker("NVDA")
    assert "NVDA" not in sim.tickers

    sim.add_ticker("nvda")
    assert "NVDA" in sim.tickers
    assert sim.current_price("NVDA") == DEFAULT_TICKERS["NVDA"].seed_price


def test_add_unknown_ticker_gets_a_plausible_seed_price():
    sim, _ = make_simulator()
    sim.add_ticker("PYPL")

    assert "PYPL" in sim.tickers
    low, high = GENERIC_SEED_PRICE_RANGE
    assert low <= sim.current_price("PYPL") <= high


async def test_unknown_ticker_participates_in_ticks():
    sim, received = make_simulator()
    sim.add_ticker("PYPL")

    await sim.tick_once()

    assert any(t.ticker == "PYPL" for t in received)


def test_readding_a_previously_seen_generic_ticker_preserves_its_price():
    sim, _ = make_simulator()
    sim.add_ticker("PYPL")
    price_after_first_add = sim.current_price("PYPL")

    sim.remove_ticker("PYPL")
    assert "PYPL" not in sim.tickers

    sim.add_ticker("PYPL")
    assert "PYPL" in sim.tickers
    assert sim.current_price("PYPL") == price_after_first_add


def test_remove_ticker_excludes_it_from_future_ticks():
    sim, _ = make_simulator()
    sim.remove_ticker("AAPL")
    assert "AAPL" not in sim.tickers


async def test_removed_ticker_no_longer_emits():
    sim, received = make_simulator()
    sim.remove_ticker("AAPL")

    await sim.tick_once()

    assert all(t.ticker != "AAPL" for t in received)


def test_same_seed_produces_identical_first_tick():
    sim_a, received_a = make_simulator(seed=123)
    sim_b, received_b = make_simulator(seed=123)

    asyncio.run(sim_a.tick_once())
    asyncio.run(sim_b.tick_once())

    prices_a = {t.ticker: t.price for t in received_a}
    prices_b = {t.ticker: t.price for t in received_b}
    assert prices_a == prices_b


async def test_start_and_stop_runs_background_loop():
    sim, received = make_simulator()
    await sim.start()
    try:
        await asyncio.sleep(1.2)
    finally:
        await sim.stop()

    assert received
    assert all(t.price > 0 for t in received)


async def test_stop_is_safe_to_call_when_never_started():
    sim, _ = make_simulator()
    await sim.stop()


async def test_tick_once_computes_day_change_percent_from_seed_reference():
    sim, _ = make_simulator()

    ticks = await sim.tick_once()

    for tick in ticks:
        seed = DEFAULT_TICKERS[tick.ticker].seed_price
        expected = round((tick.price - seed) / seed * 100, 4)
        assert tick.day_change_percent == expected


async def test_day_reference_price_stays_fixed_across_ticks():
    sim, _ = make_simulator()
    reference_before = sim.day_reference_price("AAPL")

    for _ in range(10):
        await sim.tick_once()

    assert sim.day_reference_price("AAPL") == reference_before
    assert reference_before == DEFAULT_TICKERS["AAPL"].seed_price


def test_new_known_ticker_uses_its_seed_price_as_day_reference():
    sim, _ = make_simulator()
    sim.remove_ticker("NVDA")

    sim.add_ticker("nvda")
    assert sim.day_reference_price("NVDA") == DEFAULT_TICKERS["NVDA"].seed_price


def test_new_unknown_ticker_uses_its_initial_price_as_day_reference():
    sim, _ = make_simulator()
    sim.add_ticker("PYPL")

    assert sim.day_reference_price("PYPL") == sim.current_price("PYPL")


async def test_readding_a_ticker_keeps_its_original_day_reference():
    sim, _ = make_simulator()
    sim.add_ticker("PYPL")
    reference = sim.day_reference_price("PYPL")

    sim.remove_ticker("PYPL")
    for _ in range(5):
        await sim.tick_once()
    sim.add_ticker("PYPL")

    assert sim.day_reference_price("PYPL") == reference


def test_day_reference_price_is_none_for_unknown_ticker():
    sim, _ = make_simulator()
    assert sim.day_reference_price("NOPE") is None

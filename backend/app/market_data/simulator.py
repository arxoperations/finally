import asyncio
import math
import random

from .base import MarketDataProvider, TickCallback
from .correlation import correlated_shocks
from .simulator_config import (
    DEFAULT_TICKERS,
    EFFECTIVE_DT_PER_TICK,
    EVENT_MAGNITUDE_RANGE,
    EVENT_PROBABILITY,
    GENERIC_SEED_PRICE_RANGE,
    GENERIC_TICKER_DRIFT,
    GENERIC_TICKER_SECTOR,
    GENERIC_TICKER_VOLATILITY,
    TICK_INTERVAL_SECONDS,
)
from .types import PriceTick


class MarketSimulator(MarketDataProvider):
    """Simulador de mercado por movimiento browniano geométrico (GBM).

    Implementa la interfaz MarketDataProvider; ver planning/market_simulator.md
    para el modelo matemático y la justificación de las decisiones de diseño.
    """

    def __init__(self, on_tick: TickCallback, seed: int | None = None) -> None:
        super().__init__(on_tick)
        self._rng = random.Random(seed)
        self._prices: dict[str, float] = {t: cfg.seed_price for t, cfg in DEFAULT_TICKERS.items()}
        # Precio de referencia de sesión ("del día"), fijado una vez por ticker y
        # nunca reescrito hasta el siguiente reinicio del proceso (PLAN.md §6).
        self._day_reference_price: dict[str, float] = dict(self._prices)
        self._drift: dict[str, float] = {t: cfg.drift for t, cfg in DEFAULT_TICKERS.items()}
        self._volatility: dict[str, float] = {t: cfg.volatility for t, cfg in DEFAULT_TICKERS.items()}
        self._sector: dict[str, str] = {t: cfg.sector for t, cfg in DEFAULT_TICKERS.items()}
        self._tickers = set(DEFAULT_TICKERS.keys())
        self._task: asyncio.Task | None = None
        self._running = False

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        if ticker not in self._prices:
            cfg = DEFAULT_TICKERS.get(ticker)
            if cfg is not None:
                self._prices[ticker] = cfg.seed_price
                self._drift[ticker] = cfg.drift
                self._volatility[ticker] = cfg.volatility
                self._sector[ticker] = cfg.sector
            else:
                self._prices[ticker] = self._lognormal_seed_price()
                self._drift[ticker] = GENERIC_TICKER_DRIFT
                self._volatility[ticker] = GENERIC_TICKER_VOLATILITY
                self._sector[ticker] = GENERIC_TICKER_SECTOR
            self._day_reference_price[ticker] = self._prices[ticker]
        self._tickers.add(ticker)

    def day_reference_price(self, ticker: str) -> float | None:
        return self._day_reference_price.get(ticker.upper())

    def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker.upper())

    def current_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker.upper())

    def _lognormal_seed_price(self) -> float:
        low, high = GENERIC_SEED_PRICE_RANGE
        # log-uniforme: igual de probable un precio de $20 que de $200.
        return math.exp(self._rng.uniform(math.log(low), math.log(high)))

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="market-simulator")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            await self.tick_once()
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    async def tick_once(self) -> list[PriceTick]:
        """Calcula y emite un único paso de simulación para todos los tickers vigilados.

        Expuesto como método público (en lugar de solo el bucle privado) para que
        los tests puedan avanzar la simulación de forma determinista sin depender
        de temporizadores reales.
        """
        tickers = list(self._tickers)
        sectors = {t: self._sector[t] for t in tickers}
        shocks = correlated_shocks(self._rng, sectors)

        ticks: list[PriceTick] = []
        dt = EFFECTIVE_DT_PER_TICK
        for ticker in tickers:
            mu = self._drift[ticker]
            sigma = self._volatility[ticker]
            z = shocks[ticker]

            prev = self._prices[ticker]
            new_price = prev * math.exp((mu - sigma**2 / 2) * dt + sigma * math.sqrt(dt) * z)

            # Evento aleatorio idiosincrático: salto súbito del 2-5%.
            if self._rng.random() < EVENT_PROBABILITY:
                magnitude = self._rng.uniform(*EVENT_MAGNITUDE_RANGE)
                sign = self._rng.choice([-1, 1])
                new_price *= 1 + sign * magnitude

            new_price = max(new_price, 0.01)
            self._prices[ticker] = new_price

            tick = PriceTick.create(
                ticker, new_price, prev, day_change_percent=self._day_change_percent(ticker, new_price)
            )
            ticks.append(tick)
            await self._emit(tick)

        return ticks

    def _day_change_percent(self, ticker: str, price: float) -> float | None:
        reference = self._day_reference_price.get(ticker)
        if not reference:
            return None
        return (price - reference) / reference * 100

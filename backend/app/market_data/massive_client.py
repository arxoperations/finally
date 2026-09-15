import asyncio
import logging

import httpx

from .base import MarketDataProvider, TickCallback
from .massive_config import (
    MASSIVE_API_KEY,
    MASSIVE_BASE_URL,
    MASSIVE_POLL_INTERVAL_SECONDS,
)
from .types import PriceTick

logger = logging.getLogger(__name__)

SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"


class MassiveMarketDataProvider(MarketDataProvider):
    """Cliente de la API de Massive (antes Polygon.io) — sondeo REST por lotes.

    Implementa la misma interfaz MarketDataProvider que el simulador (ver
    planning/massive_api.md y planning/market_data_design.md §6). El estado
    interno de "último precio conocido" se usa para calcular `prev_price` en
    tickers ya vistos; para un ticker visto por primera vez se usa el cierre
    del día anterior (`prevDay.c`) como referencia, si está disponible.
    """

    def __init__(
        self,
        on_tick: TickCallback,
        *,
        api_key: str = MASSIVE_API_KEY,
        base_url: str = MASSIVE_BASE_URL,
        poll_interval_seconds: float = MASSIVE_POLL_INTERVAL_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(on_tick)
        self._poll_interval_seconds = poll_interval_seconds
        self._prev_prices: dict[str, float] = {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        self._task: asyncio.Task | None = None
        self._running = False

    def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker.upper())

    def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker.upper())

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="massive-poller")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._client.aclose()

    async def _run_loop(self) -> None:
        while self._running:
            if self._tickers:
                try:
                    await self.poll_once()
                except httpx.HTTPError as exc:
                    logger.warning("Massive API poll failed: %s", exc)
            await asyncio.sleep(self._poll_interval_seconds)

    async def poll_once(self) -> list[PriceTick]:
        """Realiza una única llamada de snapshot por lotes y emite los ticks resultantes.

        Público (no solo invocado desde el bucle privado) para que los tests
        puedan ejercitar el parseo y la emisión sin depender de temporizadores.
        """
        tickers_param = ",".join(sorted(self._tickers))
        resp = await self._client.get(SNAPSHOT_PATH, params={"tickers": tickers_param})
        resp.raise_for_status()
        payload = resp.json()

        ticks: list[PriceTick] = []
        for ticker, price, day_change_percent in self._parse_response(payload):
            prev = self._prev_prices.get(ticker, price)
            tick = PriceTick.create(ticker, price, prev, day_change_percent=day_change_percent)
            self._prev_prices[ticker] = price
            ticks.append(tick)
            await self._emit(tick)
        return ticks

    @staticmethod
    def _parse_response(payload: dict) -> list[tuple[str, float, float | None]]:
        """Adapta la respuesta de snapshot de Massive a (ticker, price, day_change_percent).

        El precio prioriza el último trade, y recurre al cierre del día / cierre
        anterior si el último trade no está disponible (mercado cerrado, plan con
        retraso). `day_change_percent` usa `todaysChangePerc` del snapshot cuando
        está presente, y si no, se deriva del cierre del día anterior (PLAN.md §6).
        """
        results: list[tuple[str, float, float | None]] = []
        for item in payload.get("tickers", []):
            ticker = item.get("ticker")
            if not ticker:
                continue
            price = (
                item.get("lastTrade", {}).get("p")
                or item.get("day", {}).get("c")
                or item.get("prevDay", {}).get("c")
            )
            if price is None:
                continue
            price = float(price)

            day_change_percent = item.get("todaysChangePerc")
            if day_change_percent is None:
                prev_close = item.get("prevDay", {}).get("c")
                if prev_close:
                    day_change_percent = (price - float(prev_close)) / float(prev_close) * 100

            results.append((ticker, price, day_change_percent))
        return results

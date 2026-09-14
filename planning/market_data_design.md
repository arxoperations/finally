# Diseño del Backend de Datos de Mercado

> Documento de diseño técnico para el componente de datos de mercado descrito en `PLAN.md` §6-8. Dirigido al agente de Backend. Sustituye la versión anterior de este documento, que había quedado desalineada con el código real.

## 0. Estado real y qué cubre este documento

`backend/app/market_data/` **ya existe, está probado (47 tests, `uv run pytest` en verde) y es el contrato canónico** — no una propuesta. Este documento:

1. Documenta ese código real con precisión (§§2-7), como referencia rápida para quien lo integre.
2. Diseña en detalle **todo lo que falta** para cumplir `PLAN.md` §6-8: el campo `day_change_percent` (gap conocido, ver `planning/market_data_interface.md`), la integración con el ciclo de vida de FastAPI, el endpoint SSE, el alta en caliente de tickers nuevos, la valoración de posiciones sin precio en caché, y los `portfolio_snapshots` con `is_partial` (§§8-14).

**Regla de oro:** no reescribir ni reestructurar `base.py`, `cache.py`, `simulator.py`, `simulator_config.py`, `correlation.py`, `massive_client.py`, `massive_config.py`, `factory.py`, `wiring.py` salvo la extensión puntual y mínima descrita en §8 (`day_change_percent`). Todo lo demás se construye **por encima** de esta librería (rutas, lifespan, otros módulos de dominio), tal como exige `market_data_interface.md`.

---

## 1. Objetivos y Restricciones

- Dos fuentes de datos intercambiables: **Simulador GBM** (por defecto) y **API de Massive/Polygon** (si `MASSIVE_API_KEY` está presente). Ambas implementan `MarketDataProvider`.
- Una única tarea en segundo plano por proceso escribe en la **caché de precios** compartida (`price_cache`).
- `GET /api/stream/prices` lee de esa caché y empuja actualizaciones a ~500ms a la unión de watchlist + posiciones abiertas del usuario.
- Todo async, sin bloquear el event loop de FastAPI; sin hilos, sin locking más allá del `asyncio.Lock` ya presente en `PriceCache`.

---

## 2. Modelo de Datos Compartido (código real)

```python
# backend/app/market_data/types.py — YA IMPLEMENTADO
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass(slots=True)
class PriceTick:
    ticker: str
    price: float
    prev_price: float
    timestamp: str  # ISO 8601, UTC
    direction: Direction

    @classmethod
    def create(cls, ticker: str, price: float, prev_price: float) -> "PriceTick":
        ...  # calcula direction, redondea a 4 decimales, timestamp = now UTC

    def to_sse_dict(self) -> dict:
        ...  # {ticker, price, prev_price, timestamp, direction}
```

`Direction` serializa directamente como string. `timestamp` es ISO 8601 (no epoch float) — el frontend usa `new Date(ts)` sin conversión.

---

## 3. Interfaz Abstracta del Proveedor (código real)

```python
# backend/app/market_data/base.py — YA IMPLEMENTADO
TickCallback = Callable[[PriceTick], Awaitable[None]]

class MarketDataProvider(ABC):
    def __init__(self, on_tick: TickCallback) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def add_ticker(self, ticker: str) -> None: ...
    def remove_ticker(self, ticker: str) -> None: ...

    @property
    def tickers(self) -> frozenset[str]: ...

    async def _emit(self, tick: PriceTick) -> None: ...
```

No hay `get_latest()` ni `subscribe()` en el proveedor — eso vive en `PriceCache` (§4). Las rutas **nunca** deben instanciar `MarketSimulator` o `MassiveMarketDataProvider` directamente: siempre a través de `factory.build_market_data_provider(on_tick)`.

---

## 4. Caché de Precios (código real)

```python
# backend/app/market_data/cache.py — YA IMPLEMENTADO
@dataclass(slots=True)
class CachedPrice:
    price: float
    prev_price: float
    timestamp: str


class PriceCache:
    async def update(self, tick: PriceTick) -> None: ...      # fan-out a subscribers, dropea colas llenas
    def snapshot(self) -> dict[str, CachedPrice]: ...          # copia profunda, aislada del estado interno
    def get(self, ticker: str) -> CachedPrice | None: ...
    def subscribe(self) -> asyncio.Queue[PriceTick]: ...
    def unsubscribe(self, q: asyncio.Queue[PriceTick]) -> None: ...

price_cache = PriceCache()  # singleton a nivel de módulo
```

```python
# backend/app/market_data/wiring.py — YA IMPLEMENTADO
async def on_tick(tick: PriceTick) -> None:
    await price_cache.update(tick)
```

Un `asyncio.Queue(maxsize=256)` por suscriptor SSE; si se llena (cliente lento), la cola se descarta silenciosamente (el cliente se desconecta en su próximo intento de lectura). No crear un `Broadcaster` paralelo.

---

## 5. Simulador de Mercado (código real, resumen)

Ver `planning/market_simulator.md` para la justificación matemática completa. Puntos clave del código en `backend/app/market_data/`:

- **`simulator_config.py`**: `DEFAULT_TICKERS: dict[str, TickerConfig]` con `seed_price`, `drift`, `volatility`, `sector` para los 10 tickers semilla; `GENERIC_TICKER_*` para tickers dinámicos; `TICK_INTERVAL_SECONDS = 0.5`; `EFFECTIVE_DT_PER_TICK = 1/360`; `EVENT_PROBABILITY = 0.0008` con magnitud 2-5%.
- **`correlation.py`**: `correlated_shocks(rng, sectors_by_ticker) -> dict[str, float]` — factor de mercado + factor sectorial + idiosincrático, normalizado a `Var(Z)=1`.
- **`simulator.py`**: `MarketSimulator(on_tick, seed=None)`. `add_ticker()` asigna `seed_price` conocido o un precio log-uniforme en `(10, 500)` para tickers nuevos. **`tick_once() -> list[PriceTick]` es público** — permite avanzar la simulación de forma determinista en tests, sin `asyncio.sleep`. `current_price(ticker) -> float | None` expone el último precio simulado (usado en §8.1 para el día de referencia).

No hay nada que implementar aquí: el simulador está completo y probado.

---

## 6. Cliente de la API de Massive (código real, resumen)

Ver `planning/massive_api.md` para el contexto de la API. Puntos clave:

- **`massive_config.py`**: `MASSIVE_API_KEY`, `MASSIVE_BASE_URL` (`https://api.massive.com`), `MASSIVE_POLL_INTERVAL_SECONDS` (default `15`), todos desde variables de entorno.
- **`massive_client.py`**: `MassiveMarketDataProvider(on_tick, *, api_key=..., base_url=..., poll_interval_seconds=..., client=None)`. Acepta un `httpx.AsyncClient` inyectado (los tests usan `httpx.MockTransport`). `SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"`. **`poll_once() -> list[PriceTick]` es público**, igual que `tick_once()` del simulador — sondea la unión de tickers vigilados en una sola llamada por lotes (crítico para el nivel gratuito de 5 llamadas/min). `_run_loop` traga `httpx.HTTPError` con `logger.warning` y sigue sondeando. `stop()` cierra el cliente HTTP.
- `_parse_response(payload)` prioriza `lastTrade.p` → `day.c` → `prevDay.c`.

No hay nada que implementar aquí tampoco, salvo la extensión de §8.2 para `day_change_percent`.

---

## 7. Selección del Proveedor (código real)

```python
# backend/app/market_data/factory.py — YA IMPLEMENTADO
def build_market_data_provider(on_tick: TickCallback) -> MarketDataProvider:
    massive_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if massive_key:
        return MassiveMarketDataProvider(on_tick)
    return MarketSimulator(on_tick)
```

`.strip()` maneja correctamente una clave que solo contiene espacios en blanco.

---

## 8. Extensión: `day_change_percent`

### 8.1 Por qué esto requiere tocar la librería (y por qué es aceptable)

`PLAN.md` §6 y §8 exigen `day_change_percent` en cada evento SSE y en cada entrada de `GET /api/watchlist`: el cambio porcentual respecto al **precio de referencia de la sesión** (semilla del día para el simulador, fijada al arrancar el proceso; `todaysChangePerc`/`prevDay.c` para Massive). Esto es semánticamente distinto del delta tick-a-tick `prev_price` (que solo alimenta el destello visual).

Ese precio de referencia solo lo conoce cada proveedor (el simulador sabe cuál fue el precio semilla al arrancar; Massive lo trae en el propio snapshot). Calcularlo "por fuera" en una capa de wiring genérica obligaría a: (a) para el simulador, capturar el primer tick de cada ticker como referencia — funciona, pero es frágil si se reinicia solo un ticker; (b) para Massive, volver a parsear el payload crudo del snapshot fuera de `massive_client.py`, duplicando lógica de parseo ya probada.

Por eso la decisión de diseño es: **cada proveedor calcula su propio `day_change_percent` y lo adjunta al `PriceTick`**, con un campo opcional que no rompe compatibilidad hacia atrás.

### 8.2 Cambios mínimos a `types.py`

```python
# backend/app/market_data/types.py — EXTENSIÓN
@dataclass(slots=True)
class PriceTick:
    ticker: str
    price: float
    prev_price: float
    timestamp: str
    direction: Direction
    day_change_percent: float | None = None  # NUEVO — default preserva compatibilidad

    @classmethod
    def create(
        cls,
        ticker: str,
        price: float,
        prev_price: float,
        day_change_percent: float | None = None,  # NUEVO
    ) -> "PriceTick":
        ...
        return cls(..., day_change_percent=round(day_change_percent, 4) if day_change_percent is not None else None)

    def to_sse_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.prev_price,
            "timestamp": self.timestamp,
            "direction": self.direction.value,
            "day_change_percent": self.day_change_percent,
        }
```

Los tests existentes que llaman `PriceTick.create(ticker, price, prev)` sin el nuevo argumento siguen pasando (parámetro opcional); solo el test que compara `to_sse_dict()` byte a byte contra un dict literal necesita añadir la clave nueva. Aplicar el mismo patrón (campo opcional con default `None`) a `CachedPrice` en `cache.py`, y propagarlo en `PriceCache.update()`/`snapshot()`.

### 8.3 Simulador: referencia = precio semilla del día

Como señala `simulator.py`, `tick_once()` calcula `prev = self._prices[ticker]` **antes** de mutar, y ese `prev` es exactamente el precio semilla (o el precio log-uniforme asignado) la primera vez que el ticker se simula tras un `add_ticker()`. Basta con guardar ese primer `prev` como referencia del día y no tocarlo hasta el siguiente reinicio del proceso — igual que exige `PLAN.md` §6:

```python
# backend/app/market_data/simulator.py — EXTENSIÓN
class MarketSimulator(MarketDataProvider):
    def __init__(self, on_tick: TickCallback, seed: int | None = None) -> None:
        super().__init__(on_tick)
        ...
        self._day_open_price: dict[str, float] = dict(self._prices)  # NUEVO: referencia fijada al construir

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        if ticker not in self._prices:
            ...
            self._day_open_price[ticker] = self._prices[ticker]  # NUEVO: referencia fijada al primer alta
        self._tickers.add(ticker)

    async def tick_once(self) -> list[PriceTick]:
        ...
        for ticker in tickers:
            ...
            day_open = self._day_open_price[ticker]
            day_change_percent = (new_price - day_open) / day_open * 100.0  # NUEVO
            tick = PriceTick.create(ticker, new_price, prev, day_change_percent)
            ...
```

No se recalcula nunca `day_open` dentro de la misma ejecución del proceso — reiniciar el contenedor "abre un nuevo día" simulado, tal como especifica `PLAN.md`.

### 8.4 Massive: referencia = snapshot de la propia API

Massive ya trae `todaysChangePerc` en cada entrada del snapshot (ver `planning/massive_api.md` §6); si faltara, se deriva de `prevDay.c`:

```python
# backend/app/market_data/massive_client.py — EXTENSIÓN
@staticmethod
def _parse_response(payload: dict) -> list[tuple[str, float, float | None]]:
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
        day_change_percent = item.get("todaysChangePerc")
        if day_change_percent is None:
            prev_close = item.get("prevDay", {}).get("c")
            if prev_close:
                day_change_percent = (float(price) - prev_close) / prev_close * 100.0
        results.append((ticker, float(price), day_change_percent))
    return results


async def poll_once(self) -> list[PriceTick]:
    ...
    for ticker, price, day_change_percent in self._parse_response(payload):
        prev = self._prev_prices.get(ticker, price)
        tick = PriceTick.create(ticker, price, prev, day_change_percent)
        ...
```

### 8.5 Tests a actualizar/añadir

- `test_types.py`: `to_sse_dict()` incluye `day_change_percent`; `PriceTick.create()` sin el argumento sigue defaulteando a `None`.
- `test_simulator.py`: nuevo caso — `day_change_percent` de un ticker recién añadido parte de `0.0` en su primer tick (`new_price == day_open` no es exacto tras el primer paso GBM, pero debe ser consistente con `(price - seed)/seed*100`); un reinicio (nueva instancia de `MarketSimulator`) resetea la referencia.
- `test_massive_client.py`: `_parse_response` devuelve `todaysChangePerc` cuando está presente y lo deriva de `prevDay.c` cuando falta.

---

## 9. Integración con el Ciclo de Vida de FastAPI

```python
# backend/app/main.py (fragmento relevante — NUEVO, no existe todavía)
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db.init import ensure_db_initialized
from .db.watchlist_repo import list_all_tickers  # unión watchlist + posiciones, todos los usuarios
from .market_data.factory import build_market_data_provider
from .market_data.wiring import on_tick


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_initialized()

    provider = build_market_data_provider(on_tick)
    app.state.market_data_provider = provider

    for ticker in list_all_tickers():
        provider.add_ticker(ticker)

    await provider.start()
    try:
        yield
    finally:
        await provider.stop()


app = FastAPI(lifespan=lifespan)
```

`list_all_tickers()` es responsabilidad del módulo de base de datos (`backend/db/`, fuera de alcance de este documento) — debe devolver la unión de `watchlist.ticker` y `positions.ticker` de todos los usuarios (en la práctica, solo `"default"`), para que las posiciones abiertas sigan valorándose aunque el ticker se haya quitado de la watchlist.

`app.state.market_data_provider` es el único punto de acceso al proveedor activo desde las rutas — evita un segundo singleton global además de `price_cache`.

---

## 10. Alta en Caliente de Tickers Nuevos

`PLAN.md` §6 exige que un ticker nuevo — por watchlist, por chat, o por una operación sobre un ticker fuera de la watchlist — se registre en el proveedor **antes** de confirmar la escritura en base de datos. Patrón común a los tres flujos (`POST /api/watchlist`, acción `watchlist_changes` del chat, `POST /api/portfolio/trade` sobre un ticker sin posición ni watchlist previas):

```python
# backend/app/market_data/registration.py (NUEVO)
from fastapi import Request

from .cache import price_cache


def ensure_ticker_tracked(request: Request, ticker: str) -> None:
    """Registra `ticker` en el proveedor activo si aún no se está simulando/sondeando.

    Idempotente: MarketSimulator.add_ticker y MassiveMarketDataProvider.add_ticker
    ya son no-op si el ticker ya está presente.
    """
    provider = request.app.state.market_data_provider
    ticker = ticker.upper()
    if ticker not in provider.tickers:
        provider.add_ticker(ticker)
```

Uso en una ruta (ejemplo ilustrativo, la ruta real vive en el módulo de watchlist/portfolio):

```python
@router.post("/api/watchlist")
async def add_to_watchlist(body: AddTickerRequest, request: Request):
    ticker = body.ticker.upper()
    ensure_ticker_tracked(request, ticker)   # 1. registrar en el proveedor primero
    watchlist_repo.insert(ticker)             # 2. persistir después
    cached = price_cache.get(ticker)          # puede ser None si aún no llegó el primer tick
    return watchlist_entry_response(ticker, cached)
```

El orden importa: si se persiste primero y el registro en el proveedor falla, quedaría un ticker en base de datos sin nadie simulándolo. Registrar primero es seguro porque `add_ticker()` es síncrono, no falla, y es idempotente.

Con el simulador, el ticker recibe precio (y `day_open` per §8.3) inmediatamente y se simula desde el siguiente `tick_once()` (~500ms). Con Massive, se incluye en la unión de tickers de la siguiente llamada de `poll_once()` (hasta `MASSIVE_POLL_INTERVAL_SECONDS`). Hasta que llegue ese primer precio, `price_cache.get(ticker)` devuelve `None` y aplican las reglas de §12.

Al **eliminar** un ticker de la watchlist, no debe llamarse `provider.remove_ticker()` a ciegas: si el ticker sigue teniendo una posición abierta, debe seguir vigilado.

```python
@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, request: Request):
    ticker = ticker.upper()
    watchlist_repo.delete(ticker)
    if not positions_repo.has_position(ticker):        # solo se quita si nadie más lo necesita
        request.app.state.market_data_provider.remove_ticker(ticker)
```

---

## 11. Endpoint SSE `/api/stream/prices`

```python
# backend/app/routes/stream.py (NUEVO)
import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from ..market_data.cache import price_cache

router = APIRouter()

HEARTBEAT_SECONDS = 15
REEMIT_INTERVAL_SECONDS = 0.5  # cadencia visual constante, independiente del origen (§ PLAN.md §6)


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    watched_tickers = watched_tickers_for_current_user()  # watchlist ∪ posiciones abiertas

    async def event_generator():
        # 1. Snapshot inicial: solo tickers con precio ya conocido; no se inventa nada.
        for ticker, cached in price_cache.snapshot().items():
            if ticker not in watched_tickers:
                continue
            yield {
                "event": "price",
                "data": json.dumps({
                    "ticker": ticker,
                    "price": cached.price,
                    "prev_price": cached.prev_price,
                    "timestamp": cached.timestamp,
                    "direction": "flat",
                    "day_change_percent": cached.day_change_percent,
                }),
            }

        # 2. Reemisión periódica a ritmo constante (~500ms), leyendo siempre el último
        #    estado de la caché — el stream tiene su propio reloj, independiente de la
        #    cadencia real del proveedor (0.5s para el simulador, ~15s para Massive).
        last_sent: dict[str, tuple[float, str]] = {}  # ticker -> (price, timestamp) último enviado
        while True:
            if await request.is_disconnected():
                break
            for ticker, cached in price_cache.snapshot().items():
                if ticker not in watched_tickers:
                    continue
                key = (cached.price, cached.timestamp)
                if last_sent.get(ticker) == key:
                    continue  # sin cambios desde el último envío: no reemitir (el frontend deduplica igual, pero evita tráfico)
                last_sent[ticker] = key
                yield {
                    "event": "price",
                    "data": json.dumps({
                        "ticker": ticker,
                        "price": cached.price,
                        "prev_price": cached.prev_price,
                        "timestamp": cached.timestamp,       # timestamp de la fuente, NO el de reemisión
                        "direction": _direction(cached),
                        "day_change_percent": cached.day_change_percent,
                    }),
                }
            await asyncio.sleep(REEMIT_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())


def _direction(cached) -> str:
    if cached.price > cached.prev_price:
        return "up"
    if cached.price < cached.prev_price:
        return "down"
    return "flat"
```

### 11.1 Por qué polling sobre la caché y no una suscripción directa a `price_cache.subscribe()`

`PriceCache.subscribe()` entrega un `PriceTick` por cada `update()` del proveedor — con Massive eso es un evento cada ~15s por ticker, no cada 500ms. `PLAN.md` §6 exige que el **stream** mantenga la cadencia visual de ~500ms "para conservar la misma cadencia visual ante planes de pago futuros", reemitiendo el último precio conocido aunque no haya cambiado. Por eso el generador de este endpoint no usa `queue.get()` de `subscribe()` como bucle principal, sino un `asyncio.sleep(0.5)` que relee `price_cache.snapshot()` en cada vuelta — el snapshot ya es barato (dict comprehension sobre como mucho unas pocas decenas de tickers).

`last_sent` evita reenviar un evento idéntico byte a byte si nada cambió; esto es una optimización de tráfico, no un requisito — el frontend igualmente deduplica por la tupla `(ticker, precio, timestamp)` antes de agregar un punto al sparkline, así que reenviar de más es inofensivo si se prefiere simplificar y quitar `last_sent`.

### 11.2 Reconexión

`EventSource` del navegador reintenta automáticamente; no se necesita lógica de reconexión en el backend. Lo único que debe garantizarse es que **cada nueva conexión** reciba primero el snapshot completo disponible (paso 1 del generador) antes de los eventos periódicos, para que un cliente que reconecta no empiece con un sparkline vacío.

### 11.3 Formato del evento

```
event: price
data: {"ticker":"AAPL","price":191.23,"prev_price":190.87,"timestamp":"2026-06-23T10:15:30.512Z","direction":"up","day_change_percent":0.65}
```

---

## 12. Valoración de Posiciones sin Precio en Caché

`PLAN.md` §8 exige que una posición sin precio en `price_cache` no rompa `GET /api/portfolio` ni se estime un precio falso:

```python
# backend/app/portfolio/valuation.py (NUEVO, fuera de market_data/)
from dataclasses import dataclass

from ..market_data.cache import price_cache


@dataclass(slots=True)
class ValuedPosition:
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float | None
    unrealized_pl: float | None


def value_position(ticker: str, quantity: float, avg_cost: float) -> ValuedPosition:
    cached = price_cache.get(ticker)
    if cached is None:
        return ValuedPosition(ticker, quantity, avg_cost, current_price=None, unrealized_pl=None)
    unrealized_pl = (cached.price - avg_cost) * quantity
    return ValuedPosition(ticker, quantity, avg_cost, current_price=cached.price, unrealized_pl=unrealized_pl)


def total_portfolio_value(cash_balance: float, positions: list[ValuedPosition]) -> tuple[float, bool]:
    """Devuelve (total_value, is_partial). Las posiciones sin precio no aportan al total."""
    priced = [p for p in positions if p.current_price is not None]
    is_partial = len(priced) < len(positions)
    total = cash_balance + sum(p.current_price * p.quantity for p in priced)
    return total, is_partial
```

`GET /api/portfolio` serializa `current_price: null` / `unrealized_pl: null` para las posiciones sin precio, y documenta `is_partial` (o un campo equivalente) en la respuesta si aplica, en vez de ocultar el problema.

Rechazo de operaciones sin precio disponible (`POST /api/portfolio/trade`):

```python
# backend/app/portfolio/trade.py (fragmento — NUEVO)
from fastapi import HTTPException

from ..market_data.cache import price_cache


async def execute_trade(ticker: str, quantity: float, side: str) -> ...:
    ticker = ticker.upper()
    cached = price_cache.get(ticker)
    if cached is None:
        raise HTTPException(status_code=409, detail=f"No hay precio disponible para {ticker} todavía.")
    execution_price = cached.price  # SIEMPRE el de la caché en el momento de procesar, nunca uno enviado por el cliente
    ...  # transacción SQLite atómica: cash_balance, positions, trades, portfolio_snapshots
```

---

## 13. `portfolio_snapshots` con `is_partial`

Tarea en segundo plano independiente del proveedor de datos de mercado (arranca también en `lifespan`), que registra el valor total de la cartera cada 30s **y** inmediatamente tras cada operación ejecutada:

```python
# backend/app/portfolio/snapshots.py (NUEVO)
import asyncio
import uuid
from datetime import datetime, timezone

from .valuation import total_portfolio_value, value_position

SNAPSHOT_INTERVAL_SECONDS = 30


async def record_snapshot(user_id: str = "default") -> None:
    cash_balance = get_cash_balance(user_id)                 # módulo de base de datos
    positions = [value_position(p.ticker, p.quantity, p.avg_cost) for p in get_positions(user_id)]
    total_value, is_partial = total_portfolio_value(cash_balance, positions)

    insert_portfolio_snapshot(                                 # módulo de base de datos
        id=str(uuid.uuid4()),
        user_id=user_id,
        total_value=total_value,
        is_partial=is_partial,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


async def snapshot_loop() -> None:
    while True:
        await record_snapshot()
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
```

Arranque/apagado junto al proveedor de mercado en `lifespan`:

```python
# backend/app/main.py — ampliando el lifespan de §9
from .portfolio.snapshots import snapshot_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_initialized()
    provider = build_market_data_provider(on_tick)
    app.state.market_data_provider = provider
    for ticker in list_all_tickers():
        provider.add_ticker(ticker)
    await provider.start()

    snapshot_task = asyncio.create_task(snapshot_loop(), name="portfolio-snapshots")
    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass
        await provider.stop()
```

`record_snapshot()` **no espera** a que lleguen todos los precios: calcula con lo que hay en `price_cache` en ese instante y marca `is_partial=1` si falta alguno (§12), tal como exige `PLAN.md` §7-8. El mismo `record_snapshot()` se reutiliza inmediatamente después de `execute_trade()` (§12) para registrar el snapshot post-operación.

---

## 14. Dependencias a Añadir (`backend/pyproject.toml`)

El `pyproject.toml` actual ya trae `httpx` y `pydantic-settings` (usados por `massive_client.py` y por la configuración de la app). Faltan las de servidor HTTP/SSE:

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sse-starlette>=2.1",
    "httpx>=0.27",           # ya presente
    "pydantic-settings>=2.0", # ya presente
    # litellm, etc. — fuera de alcance de este documento
]
```

`sse-starlette` provee `EventSourceResponse`, usado en §11.

---

## 15. Tests Adicionales Sugeridos

Además de la actualización de tests existentes descrita en §8.5:

```python
# backend/tests/routes/test_stream.py (NUEVO — requiere FastAPI TestClient / httpx.AsyncClient con ASGITransport)
import pytest

from app.market_data.cache import price_cache
from app.market_data.types import PriceTick


@pytest.mark.asyncio
async def test_stream_sends_initial_snapshot_before_new_ticks(async_client, monkeypatch):
    await price_cache.update(PriceTick.create("AAPL", 191.0, 190.0, day_change_percent=0.5))

    async with async_client.stream("GET", "/api/stream/prices") as response:
        first_event = await anext(response.aiter_lines())
        assert "AAPL" in first_event


@pytest.mark.asyncio
async def test_stream_only_includes_watched_tickers(async_client):
    # un ticker con precio en caché pero fuera de la watchlist/posiciones del usuario
    # no debe aparecer en el stream — ver §11.
    ...
```

```python
# backend/tests/market_data/test_registration.py (NUEVO)
def test_ensure_ticker_tracked_is_idempotent(fake_request_with_simulator):
    from app.market_data.registration import ensure_ticker_tracked

    ensure_ticker_tracked(fake_request_with_simulator, "PYPL")
    ensure_ticker_tracked(fake_request_with_simulator, "PYPL")  # segunda llamada no debe duplicar estado

    provider = fake_request_with_simulator.app.state.market_data_provider
    assert provider.tickers.count("PYPL") if hasattr(provider.tickers, "count") else "PYPL" in provider.tickers
```

```python
# backend/tests/portfolio/test_valuation.py (NUEVO)
from app.portfolio.valuation import value_position, total_portfolio_value


def test_position_without_cached_price_is_null_not_estimated(monkeypatch):
    from app.market_data.cache import price_cache
    # ticker sin ningún tick emitido todavía
    result = value_position("ZZZZ", quantity=10, avg_cost=50.0)
    assert result.current_price is None
    assert result.unrealized_pl is None


def test_total_value_excludes_unpriced_positions_and_flags_partial():
    from app.portfolio.valuation import ValuedPosition

    priced = ValuedPosition("AAPL", 10, 180.0, current_price=190.0, unrealized_pl=100.0)
    unpriced = ValuedPosition("ZZZZ", 5, 50.0, current_price=None, unrealized_pl=None)

    total, is_partial = total_portfolio_value(cash_balance=1000.0, positions=[priced, unpriced])
    assert total == 1000.0 + 190.0 * 10
    assert is_partial is True
```

---

## 16. Resumen de Archivos

```
backend/app/market_data/                  # YA IMPLEMENTADO — solo tocar según §8
├── __init__.py
├── types.py                # + day_change_percent (§8.2)
├── base.py
├── cache.py                # + day_change_percent en CachedPrice (§8.2)
├── wiring.py
├── simulator_config.py
├── correlation.py
├── simulator.py             # + _day_open_price (§8.3)
├── massive_config.py
├── massive_client.py         # + parseo de todaysChangePerc (§8.4)
├── factory.py
└── registration.py               # NUEVO (§10)

backend/app/routes/
└── stream.py                          # NUEVO (§11)

backend/app/portfolio/                       # NUEVO (fuera de market_data/, §12-13)
├── valuation.py
├── trade.py
└── snapshots.py

backend/app/main.py                              # NUEVO (§9, §13) — lifespan, app FastAPI

backend/tests/market_data/
├── test_types.py                 # actualizar (§8.5)
├── test_simulator.py                # actualizar + nuevo caso (§8.5)
├── test_massive_client.py              # actualizar (§8.5)
└── test_registration.py                   # NUEVO (§15)

backend/tests/routes/
└── test_stream.py                               # NUEVO (§15)

backend/tests/portfolio/
└── test_valuation.py                                # NUEVO (§15)
```

Este diseño conserva íntegra la librería de datos de mercado ya probada, resuelve el gap de `day_change_percent` con el mínimo cambio necesario en el lugar correcto (cada proveedor conoce su propia referencia de sesión), y especifica cómo ensamblarla en una app FastAPI real: ciclo de vida, SSE, alta en caliente de tickers, y su intersección con cartera/posiciones — todo lo que `PLAN.md` §6-8 exige y que hoy no existe en el repositorio.

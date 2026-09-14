# Contrato de Datos de Mercado

## Estado y fuente canónica

Este documento describe el contrato que ya implementa y prueba
`backend/app/market_data/`. No propone una interfaz alternativa. La referencia
de diseño ampliada es `planning/market_data_design.md`; cuando ambos difieran,
el código probado y este documento prevalecen.

El módulo existente tiene 47 tests unitarios. FastAPI, SQLite y las rutas SSE
aún no existen: deben integrarse contra este contrato, sin refactorizar la
biblioteca de datos de mercado.

## Modelo de datos

`PriceTick` (`types.py`) es el valor que un proveedor comunica al resto de la
aplicación:

```python
@dataclass(slots=True)
class PriceTick:
    ticker: str
    price: float
    prev_price: float
    timestamp: str       # ISO 8601 UTC
    direction: Direction # "up" | "down" | "flat"
```

`PriceTick.create()` centraliza el cálculo de dirección y el formato que se
emite por SSE se obtiene con `to_sse_dict()`.

### Gap conocido: `day_change_percent`

`PLAN.md` (secciones 6 y 8) exige que cada evento SSE y cada entrada de
`GET /api/watchlist` incluyan `day_change_percent`, pero ni `PriceTick` ni
`CachedPrice` lo modelan hoy: `to_sse_dict()` solo produce `ticker`, `price`,
`prev_price`, `timestamp` y `direction`. Esto es una omisión pendiente, no una
contradicción a resolver a favor de uno u otro documento.

Al implementar la integración FastAPI/SSE, quien la construya debe decidir e
implementar dónde vive el precio de referencia de sesión (semilla del día para
el simulador; `prevDay.c` de Massive) y cómo se deriva `day_change_percent` a
partir de él — extendiendo `PriceTick`/`CachedPrice` en `market_data/`, o
enriqueciendo el payload en la capa de wiring/rutas por encima de la
biblioteca ya probada. Cualquiera de las dos opciones es válida siempre que el
campo llegue tal como `PLAN.md` lo especifica; lo que no es válido es dejarlo
sin resolver silenciosamente.

## Proveedor

`MarketDataProvider` en `base.py` es una `ABC` con callback asíncrono. No se
usa un `Protocol`, ni el proveedor expone `get_latest()` o `subscribe()`.

```python
TickCallback = Callable[[PriceTick], Awaitable[None]]

class MarketDataProvider(ABC):
    def __init__(self, on_tick: TickCallback) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def add_ticker(self, ticker: str) -> None: ...
    def remove_ticker(self, ticker: str) -> None: ...
    @property
    def tickers(self) -> frozenset[str]: ...
```

Implementaciones:

- `MarketSimulator`: proveedor GBM predeterminado; `tick_once()` permite
  avanzar de forma determinista en tests.
- `MassiveMarketDataProvider`: polling REST por lotes; `poll_once()` permite
  probar el parseo sin temporizadores.

`factory.build_market_data_provider(on_tick)` selecciona Massive solo si
`MASSIVE_API_KEY` contiene un valor no vacío. Las rutas no deben construir
proveedores concretos directamente.

## Caché y difusión

`PriceCache` (`cache.py`) reúne las dos responsabilidades que algunos diseños
anteriores separaban:

```python
class PriceCache:
    async def update(self, tick: PriceTick) -> None: ...
    def snapshot(self) -> dict[str, CachedPrice]: ...
    def get(self, ticker: str) -> CachedPrice | None: ...
    def subscribe(self) -> asyncio.Queue[PriceTick]: ...
    def unsubscribe(self, queue: asyncio.Queue[PriceTick]) -> None: ...
```

- `update()` guarda el último precio y hace fan-out sin bloquear al proveedor.
- Una cola llena se descarta para desconectar al consumidor lento.
- `snapshot()` devuelve copias independientes de los valores cacheados.
- La instancia compartida es `price_cache`; `wiring.on_tick` es el callback que
  conecta cualquier proveedor con ella.

No crear un `Broadcaster` paralelo ni un segundo caché al implementar SSE.

## Integración con FastAPI y SSE

En el `lifespan` de FastAPI:

1. Inicializar la base de datos y leer la unión de watchlist y posiciones.
2. Construir una sola vez el proveedor con `build_market_data_provider(on_tick)`.
3. Añadir los tickers iniciales y ejecutar `await provider.start()`.
4. En el apagado, ejecutar `await provider.stop()`.

Las altas/bajas de watchlist llaman respectivamente a `add_ticker()` y
`remove_ticker()`. Al abrir/cerrar una posición se debe recalcular la unión de
watchlist y posiciones: no se puede eliminar del proveedor un ticker que sigue
siendo necesario para el P&L.

`GET /api/stream/prices` se suscribe a `price_cache`, emite primero el
snapshot disponible y filtra los ticks a la unión de watchlist y posiciones
del usuario. El scheduler SSE puede reemitir el caché cada ~500 ms, como exige
`PLAN.md`; debe conservar el timestamp original del tick para que el frontend
deduplique las muestras de sparkline.

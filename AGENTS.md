# Proyecto FinAlly - El Aliado Financiero

Toda la documentación del proyecto se encuentra en el directorio `planning`.

El documento clave es `planning/PLAN.md`, incluido en su totalidad a continuación. Consulta también los documentos de esa carpeta cuando sea necesario.

**Estado real del proyecto**: nada es funcional todavía. No existe app FastAPI (ni `main.py`, ni routers, ni endpoints `/api/*`), no existe base de datos, no existe `frontend/`, ni `Dockerfile`, ni `scripts/`. Lo único implementado es la librería interna de datos de mercado en `backend/app/market_data/` (simulador GBM, cliente de Massive, caché de precios, factory) con sus tests unitarios (`uv run pytest` en `backend/`, 47 tests en verde) — pero esos módulos aún no están conectados a un servidor real ni expuestos vía HTTP/SSE. Todo lo demás, incluyendo ensamblar esta librería en la app FastAPI descrita en el plan, está por desarrollarse desde cero.

@planning/PLAN.md

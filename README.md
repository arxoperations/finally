# FinAlly — AI Trading Workstation

Estación de trabajo de trading simulado con precios de mercado en tiempo real y un asistente de IA capaz de operar en nombre del usuario. Proyecto final de un curso de programación con agentes de IA: toda la app se construye mediante Agentes de Programación orquestados a través de los documentos en `planning/`.

La especificación completa vive en [`planning/PLAN.md`](planning/PLAN.md).

## Estado actual

**Nada es funcional todavía.** No existe app FastAPI, ni base de datos, ni frontend, ni Docker, ni scripts de arranque.

Lo único implementado es la librería de datos de mercado en `backend/app/market_data/`:
- Simulador de precios por movimiento browniano geométrico (GBM)
- Cliente para la API de Massive (Polygon.io)
- Caché de precios compartida y factory para elegir la fuente

Con 47 tests unitarios en verde:

```bash
cd backend
uv run pytest
```

## Arquitectura prevista

Contenedor Docker único (puerto 8000): FastAPI sirve la API REST/SSE y el build estático de un frontend Next.js. SQLite como base de datos, con inicialización diferida. Ver la sección 3 de [`planning/PLAN.md`](planning/PLAN.md) para el detalle y las justificaciones de cada decisión.

## Stack

- **Backend**: FastAPI + Python, gestionado con `uv`
- **Frontend**: Next.js (TypeScript), exportación estática
- **Base de datos**: SQLite
- **Tiempo real**: Server-Sent Events
- **IA**: LiteLLM → OpenRouter (Cerebras preferido), salidas estructuradas

## Documentación

Todos los documentos de referencia para agentes están en [`planning/`](planning/).

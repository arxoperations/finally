# Revision de cambios sin commitear contra HEAD fa3c32b

Fecha de revision: 2026-09-14

## Alcance y verificaciones

Revise los cambios listados por `git status --porcelain`:

- Modificados tracked: `.claude/skills/cerebras/SKILL.md`, `CLAUDE.md`, `backend/pyproject.toml`, `backend/uv.lock`, `planning/PLAN.md`, `planning/market_data_interface.md`.
- Nuevos untracked: `.claude/agents/change-reviewer.md`, `.claude/commands/doc-review.md`, `.env.example`, `backend/app/settings.py`, `backend/tests/test_settings.py`, `planning/review.md` (sobrescrito por este informe).

Tambien lei el contrato completo relevante en `planning/PLAN.md`, el estado real en `CLAUDE.md`, y el codigo probado actual de `backend/app/market_data/` para contrastar las afirmaciones nuevas de documentacion.

Comprobaciones ejecutadas:

- `uv run pytest` en `backend/`: 52 tests pasan.
- `uv run python -m py_compile app/settings.py tests/test_settings.py`: no pudo ejecutarse porque `uv` intento inicializar cache fuera del sandbox (`/Users/gabrielarce/.cache/uv`) y recibio `Operation not permitted`. La validez sintactica queda cubierta indirectamente por `pytest`, que importo y ejecuto `backend/app/settings.py` y `backend/tests/test_settings.py`.
- Busqueda de posibles secretos en archivos revisados: no encontre claves reales. `.env.example` usa valores vacios o placeholder.

## Hallazgos

### 1. Medium - `planning/PLAN.md` exige `day_change_percent`, pero el contrato/codigo real de `market_data` no lo produce

Archivos afectados:

- `planning/PLAN.md:197`
- `planning/PLAN.md:310`
- `planning/PLAN.md:410`
- `planning/PLAN.md:488`
- `planning/market_data_interface.md:19-30`
- `backend/app/market_data/types.py:36-43`
- `backend/app/market_data/cache.py:7-12`

El plan ahora dice que cada evento SSE incluye `day_change_percent`:

```text
Cada evento tambien incluye `day_change_percent`
```

y que `GET /api/watchlist` devuelve los mismos campos del contrato SSE, incluyendo `day_change_percent`.

Pero el contrato real documentado en `planning/market_data_interface.md:19-30` muestra `PriceTick` con solo `ticker`, `price`, `prev_price`, `timestamp` y `direction`. El codigo implementado coincide con esa version mas pequena: `PriceTick.to_sse_dict()` en `backend/app/market_data/types.py:36-43` devuelve solo esos cinco campos y `CachedPrice` en `backend/app/market_data/cache.py:7-12` tampoco conserva ningun precio de referencia diario ni porcentaje diario.

Impacto: un futuro implementador de SSE/watchlist puede seguir `PLAN.md` y esperar un campo que la libreria canonica no puede entregar sin cambios. Esto rompe la afirmacion de `planning/market_data_interface.md:5-8` de que ese documento y el codigo probado prevalecen como contrato real.

Recomendacion: elegir una de dos rutas y dejarla explicita:

- Si `day_change_percent` es requisito del producto, extender `PriceTick`, `CachedPrice`, `to_sse_dict()`, simulador, Massive y tests para producirlo.
- Si no debe tocarse todavia la libreria de market data, mover `day_change_percent` a una responsabilidad de la futura capa HTTP/SSE y documentar como se calcula a partir de `PriceCache` mas estado adicional.

### 2. Medium - `.claude/agents/change-reviewer.md` tiene frontmatter probablemente invalido

Archivo afectado:

- `.claude/agents/change-reviewer.md:1-4`

El archivo abre frontmatter con `---` pero lo cierra con cuatro guiones:

```text
---
name: change-reviewer
description: Lleva a cabo una revision exhaustiva de todos los cambios desde el ultimo commit usando codex. 
----
```

Muchas herramientas que parsean frontmatter esperan exactamente `---` como delimitador de cierre. Con `----`, el agente puede no registrarse o puede interpretar el resto del archivo como parte del bloque YAML.

Recomendacion: cambiar la linea 4 a `---` y quitar el espacio final de la descripcion.

### 3. Low - `.claude/agents/change-reviewer.md` recomienda un comando que no muestra untracked

Archivo afectado:

- `.claude/agents/change-reviewer.md:11`

La instruccion dice:

```text
usa `git diff HEAD -- <ruta>` o similar si necesitas ver el contenido de un archivo nuevo sin trackear
```

`git diff HEAD -- <ruta>` no muestra contenido de archivos untracked normales. Para untracked hay que leer el archivo directamente (`sed`, `nl`, `cat`) o usar una tecnica como `git add -N <ruta>` antes de diff, si eso es aceptable para el flujo.

Impacto: el agente podria creer que reviso archivos nuevos cuando en realidad obtuvo un diff vacio.

Recomendacion: reemplazar esa instruccion por una orden explicita de leer los archivos untracked con `sed -n`, `nl -ba`, o equivalente, sin modificar staging.

### 4. Low - La skill de Cerebras aun afirma dependencias que `pyproject.toml` no tiene

Archivos afectados:

- `.claude/skills/cerebras/SKILL.md:18-20`
- `backend/pyproject.toml:6-9`

La skill dice:

```text
El proyecto uv debe incluir litellm y pydantic.
`uv add litellm pydantic`
```

Pero el cambio de dependencias solo agrega `pydantic-settings>=2.0`; no agrega `litellm` ni `pydantic` como dependencia directa. `pydantic` entra transitivamente por `pydantic-settings` en `uv.lock`, pero `litellm` no esta disponible.

Esto no rompe nada ahora porque todavia no existe implementacion de chat LLM. Aun asi, la guia de la skill parece lista para copiar snippets que importan `litellm`, y ese import fallaria si se implementa chat sin actualizar dependencias.

Recomendacion: o bien agregar `litellm` cuando se implemente el chat real, o ajustar la skill para aclarar que esas dependencias son requeridas por la futura capa LLM y no por el cambio actual de `Settings`.

### 5. Low - `planning/PLAN.md` introduce una fecha de retirada de modelo sin mecanismo verificable

Archivo afectado:

- `planning/PLAN.md:334`

El plan dice que Dots tiene retirada anunciada para el 30 de septiembre de 2026 y exige una tarea de migracion antes de esa fecha. Como el repositorio no incluye fuente, test ni mecanismo de alerta todavia, esta afirmacion puede volverse obsoleta silenciosamente. Dado que la fecha es cercana al estado actual del proyecto, el riesgo operacional es real.

Recomendacion: convertir esto en una tarea rastreable o en un test/log de arranque cuando exista el modulo LLM. Si se mantiene en el plan, conviene citar una fuente o dejar claro que es una restriccion conocida del proyecto.

## Revision por archivo

### `.claude/skills/cerebras/SKILL.md`

Correcto en lo esencial y consistente con `backend/app/settings.py`: referencia `from app.settings import Settings`, `settings.openrouter_model` y `settings.openrouter_provider_order`, que existen exactamente en `backend/app/settings.py:12-24`.

No expone secretos. La indicacion de no ejecutar efectos secundarios si falla `model_validate_json()` es buena y coherente con `planning/PLAN.md:367-370`.

Observacion menor: los snippets importan `litellm`, pero `backend/pyproject.toml` aun no lo declara. Ver hallazgo 4.

### `CLAUDE.md`

La correccion de `planning/plan.md` a `planning/PLAN.md` es necesaria. El estado real declarado es coherente con el arbol actual: no hay `frontend/`, `Dockerfile`, `scripts/`, `main.py` ni endpoints FastAPI, y si existe `backend/app/market_data/` con tests.

No detecte secretos ni instrucciones peligrosas.

### `backend/pyproject.toml`

Agregar `pydantic-settings>=2.0` es coherente con la nueva clase `Settings`.

La dependencia esta reflejada en `backend/uv.lock` como dependencia del paquete editable (`backend/uv.lock` incluye `pydantic-settings`, `pydantic`, `python-dotenv`, `typing-inspection`, etc.). `uv run pytest` resolvio e importo correctamente.

### `backend/uv.lock`

Coherente con `backend/pyproject.toml`: incluye `pydantic-settings` y sus transitivas. No vi indicios de secretos.

### `.env.example`

Bien como plantilla:

```text
OPENROUTER_API_KEY=
MASSIVE_API_KEY=
LLM_MOCK=false
```

No contiene claves reales. Tambien es consistente con `.gitignore`, que ignora `.env` en `.gitignore:137-139`.

### `backend/app/settings.py`

La sintaxis y carga basica son correctas. La clase `Settings(BaseSettings)` implementa los campos pedidos por el plan:

- `openrouter_api_key`
- `openrouter_model`
- `openrouter_provider_order`
- `massive_api_key`
- `llm_mock`

`PROJECT_ROOT = Path(__file__).resolve().parents[2]` apunta a la raiz del repo desde `backend/app/settings.py`, por lo que `env_file=PROJECT_ROOT / ".env"` cumple el contrato de cargar `.env` de la raiz. Permite arrancar sin `OPENROUTER_API_KEY` porque el campo es opcional, y `chat_configured` solo rechaza chat real cuando falta clave y `llm_mock` es falso.

No loguea ni expone la API key. Tampoco hay valores reales hardcodeados.

Observacion menor: `massive_api_key` puede quedar como cadena vacia cuando `.env` contiene `MASSIVE_API_KEY=`, no como `None`. Eso no rompe el contrato si los consumidores hacen `.strip()` como `backend/app/market_data/factory.py:14`, pero conviene mantener esa convencion documentada o normalizar vacios en `Settings` si futuras capas van a leer `settings.massive_api_key` directamente.

### `backend/tests/test_settings.py`

Los tests son significativos para el alcance actual:

- prueban carga desde archivo `.env`;
- prueban precedencia de variable exportada;
- prueban que `LLM_MOCK=true` permite chat sin clave;
- prueban que chat real sin clave queda no configurado;
- prueban el modelo por defecto.

No contienen secretos reales; usan placeholders como `from-dotenv`.

Cobertura recomendada adicional: agregar un test para `OPENROUTER_PROVIDER_ORDER` y otro para `MASSIVE_API_KEY` vacio/no vacio, porque son parte explicita del contrato de secciones 5 y 9 del plan.

### `.claude/agents/change-reviewer.md`

La intencion general es coherente: delega la revision sustantiva a `codex exec` y advierte "No te revises a ti mismo" en `.claude/agents/change-reviewer.md:8` y `.claude/agents/change-reviewer.md:16`.

Problemas: frontmatter probablemente invalido (hallazgo 2) y comando incorrecto para leer untracked (hallazgo 3).

No detecte instrucciones destructivas. El comando sugerido escribe en `planning/review.md`, que es el objetivo esperado.

### `.claude/commands/doc-review.md`

Es breve y no contiene instrucciones peligrosas. Pide revisar un documento de `planning` y anadir preguntas/comentarios al final. Seria mas robusto si exigiera leer `planning/PLAN.md` cuando el documento revisado dependa del contrato global, pero no hay contradiccion directa.

### `planning/PLAN.md`

La mayoria de cambios mejoran el contrato:

- clarifica que el chat puede estar pendiente de configuracion;
- elimina la afirmacion insegura de que existe una `OPENROUTER_API_KEY` en `.env`;
- define `OPENROUTER_MODEL`, `OPENROUTER_PROVIDER_ORDER` y `GET /api/chat/status`;
- separa `/api/health` de estado de chat;
- exige no filtrar claves;
- actualiza el estado de market data para usar el codigo probado como fuente canonica.

Problema principal: `day_change_percent` se agrega al contrato SSE/watchlist sin existir en el codigo canonico que el propio plan declara prevalente. Ver hallazgo 1.

### `planning/market_data_interface.md`

El documento ahora refleja mucho mejor el codigo actual de `backend/app/market_data/`: `MarketDataProvider` es una `ABC`, el callback `TickCallback` existe, `PriceCache` concentra cache y fan-out, y `wiring.on_tick` conecta proveedor con cache.

Problema indirecto: al decir que `to_sse_dict()` define el formato SSE sin mencionar `day_change_percent`, contradice el nuevo contrato de `planning/PLAN.md`. Ver hallazgo 1.

## Seguridad

No encontre fugas de credenciales en los archivos modificados o nuevos revisados.

Puntos positivos:

- `.env.example` deja `OPENROUTER_API_KEY=` y `MASSIVE_API_KEY=` vacios.
- `planning/PLAN.md` ya no afirma que existe una clave real en `.env`; ahora habla de plantilla y `.env` local no versionado.
- `backend/app/settings.py` no imprime, serializa ni registra claves.
- `backend/tests/test_settings.py` usa valores falsos.

## Acciones recomendadas, priorizadas

1. Resolver el contrato de `day_change_percent`: implementarlo en `backend/app/market_data/` con tests o documentarlo como responsabilidad futura fuera del contrato canonico actual.
2. Corregir el frontmatter de `.claude/agents/change-reviewer.md` cambiando `----` por `---`.
3. Corregir la instruccion de lectura de untracked en `.claude/agents/change-reviewer.md`; `git diff HEAD -- <archivo>` no basta para untracked.
4. Decidir si `litellm` debe agregarse ya a `backend/pyproject.toml` o si la skill debe aclarar que esa dependencia llegara con la implementacion real del chat.
5. Ampliar `backend/tests/test_settings.py` con `OPENROUTER_PROVIDER_ORDER` y `MASSIVE_API_KEY`, y opcionalmente normalizar cadenas vacias a `None` en `Settings`.
6. Convertir la migracion del modelo Dots antes del 30 de septiembre de 2026 en una tarea/test verificable para que no quede como deuda silenciosa en documentacion.

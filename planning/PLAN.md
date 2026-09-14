# FinAlly — AI Trading Workstation

## Especificación del Proyecto

## 1. Visión

FinAlly (Finance Ally) es una estación de trabajo de trading impulsada por IA, visualmente espectacular, que transmite datos de mercado en tiempo real, permite a los usuarios operar con una cartera simulada e integra un asistente de chat con LLM capaz de analizar posiciones y ejecutar operaciones en nombre del usuario. Tiene el aspecto y la sensación de una terminal Bloomberg moderna con un copiloto de IA.

Este es el proyecto final de un curso de programación con IA agéntica. Está construido íntegramente por Agentes de Programación, demostrando cómo unos agentes de IA orquestados pueden producir una aplicación full-stack de calidad de producción. Los agentes interactúan a través de archivos en `planning/`.

## 2. Experiencia de Usuario

### Primer Lanzamiento

El usuario ejecuta un único comando Docker (o un script de inicio proporcionado). Se abre un navegador en `http://localhost:8000`. Sin inicio de sesión, sin registro. Inmediatamente ve:

- Una watchlist de 10 tickers predeterminados con precios actualizándose en vivo en una cuadrícula
- $10,000 en efectivo virtual
- Una estética de terminal de trading oscura y rica en datos
- Un panel de chat de IA — operativo si hay una clave de OpenRouter configurada o `LLM_MOCK=true`; si no, muestra un estado de configuración pendiente (vía `GET /api/chat/status`) en vez de fallar silenciosamente en el primer mensaje

### Qué Puede Hacer el Usuario

- **Ver el flujo de precios en directo** — los precios destellan en verde (subida) o rojo (bajada) con sutiles animaciones CSS que se desvanecen
- **Ver mini-gráficos de tipo sparkline** — la evolución del precio junto a cada ticker en la watchlist, acumulada en el frontend a partir del stream SSE desde la carga de la página (los sparklines se completan progresivamente)
- **Hacer clic en un ticker** para ver un gráfico más grande y detallado en el área principal de gráficos
- **Comprar y vender acciones** — solo órdenes de mercado, ejecución instantánea al precio actual, sin comisiones, sin diálogo de confirmación
- **Monitorizar su cartera** — un mapa de calor (treemap) que muestra las posiciones dimensionadas por peso y coloreadas por P&L, además de un gráfico de P&L que sigue el valor total de la cartera a lo largo del tiempo
- **Ver una tabla de posiciones** — ticker, cantidad, coste medio, precio actual, P&L no realizado, % de cambio
- **Chatear con el asistente de IA** — preguntar sobre su cartera, obtener análisis y hacer que la IA ejecute operaciones y gestione la watchlist mediante lenguaje natural
- **Gestionar la watchlist** — añadir/eliminar tickers manualmente o a través del chat de IA

### Diseño Visual

- **Tema oscuro**: fondos en torno a `#0d1117` o `#1a1a2e`, bordes grises apagados, sin negro puro
- **Animaciones de destello de precio**: breve resalte de fondo verde/rojo al cambiar el precio, desapareciendo en ~500ms mediante transiciones CSS
- **Indicador de estado de conexión**: un pequeño punto de color (verde = conectado, amarillo = reconectando, rojo = desconectado) visible en el encabezado
- **Diseño profesional y denso en datos**: inspirado en terminales Bloomberg/de trading — cada píxel cumple una función
- **Pensado primero para escritorio**: optimizado para pantallas anchas; no es objetivo dar soporte a tablet/móvil en esta fase

### Esquema de Colores
- Naranja de acento: `#FF6A05` (foco, selección y llamadas a la acción no destructivas)
- Rojo primario: `#6D0000` (superficies y acentos de marca; no usarlo como indicador de pérdida)
- Teal secundario: `#006E5E` (botones de envío)
- Gris/offwhite: `#DFE0DF` (texto primario e iconos sobre superficies oscuras)
- Verde (subida de precio / beneficio): `#16c784`
- Rojo (bajada de precio / pérdida): `#ea3943`

## 3. Visión General de la Arquitectura

### Contenedor Único, Puerto Único

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js con TypeScript, compilado como exportación estática (`output: 'export'`), servido por FastAPI como archivos estáticos
- **Backend**: FastAPI (Python), gestionado como un proyecto `uv`
- **Base de datos**: SQLite, un único archivo en `db/finally.db`, montado como volumen para persistencia
- **Datos en tiempo real**: Server-Sent Events (SSE) — más sencillo que WebSockets, envío unidireccional servidor→cliente, funciona en cualquier entorno
- **Integración de IA**: LiteLLM → OpenRouter (Cerebras preferido cuando sea compatible; fallback administrado por OpenRouter), con salidas estructuradas para la ejecución de operaciones
- **Datos de mercado**: controlados por variables de entorno — simulador por defecto, datos reales mediante la API de Massive si se proporciona una clave

### Por Qué Estas Decisiones

| Decisión | Justificación |
|---|---|
| SSE en lugar de WebSockets | Solo necesitamos envío unidireccional; más simple, sin complejidad bidireccional, soporte universal en navegadores |
| Exportación estática de Next.js | Mismo origen, sin problemas de CORS, un solo puerto, un solo contenedor, despliegue simple |
| SQLite en lugar de Postgres | Sin autenticación = sin multiusuario = sin necesidad de un servidor de base de datos; autocontenido, configuración cero |
| Contenedor Docker único | Los estudiantes ejecutan un solo comando; sin docker-compose en producción, sin orquestación de servicios |
| uv para Python | Gestión de proyectos Python rápida y moderna; lockfile reproducible; lo que los estudiantes deben aprender |
| Solo órdenes de mercado | Elimina el libro de órdenes, la lógica de órdenes limitadas y las ejecuciones parciales — matemática de cartera drásticamente más simple |

---

## 4. Estructura de Directorios

```
finally/
├── frontend/                 # Proyecto Next.js TypeScript (exportación estática)
├── backend/                  # Proyecto FastAPI uv (Python)
│   └── db/                   # Definiciones de esquema, datos semilla, lógica de migración
├── planning/                 # Documentación del proyecto para los agentes
│   ├── PLAN.md               # Este documento
│   └── ...                   # Documentos de referencia adicionales para agentes
├── scripts/
│   ├── start_mac.sh          # Inicia el contenedor Docker (macOS/Linux)
│   ├── stop_mac.sh           # Detiene el contenedor Docker (macOS/Linux)
│   ├── start_windows.ps1     # Inicia el contenedor Docker (Windows PowerShell)
│   └── stop_windows.ps1      # Detiene el contenedor Docker (Windows PowerShell)
├── test/                     # Tests E2E con Playwright + docker-compose.test.yml
├── db/                       # Bind mount del volumen (el archivo SQLite vive aquí en tiempo de ejecución)
│   └── .gitkeep              # El directorio existe en el repo; finally.db está en .gitignore
├── Dockerfile                # Build multi-etapa (Node → Python)
├── .env.example               # Plantilla de variables de entorno, versionada
├── .env                       # Copia local de .env.example con valores reales (no versionado, en .gitignore)
└── .gitignore
```

### Límites Clave

- **`frontend/`** es un proyecto Next.js autocontenido. No sabe nada de Python. Se comunica con el backend a través de los endpoints `/api/*` y los endpoints SSE `/api/stream/*`. La estructura interna queda a criterio del agente Ingeniero de Frontend.
- **`backend/`** es un proyecto uv autocontenido con su propio `pyproject.toml`. Es responsable de toda la lógica del servidor, incluyendo la inicialización de la base de datos, el esquema, los datos semilla, las rutas de la API, el streaming SSE, los datos de mercado y la integración con el LLM. La estructura interna queda a criterio de los agentes de Backend/Datos de Mercado.
- **`backend/db/`** contiene las definiciones SQL del esquema y la lógica de datos semilla. El backend inicializa la base de datos de forma diferida (lazy) en la primera solicitud — creando las tablas y poblando los datos predeterminados si el archivo SQLite no existe o está vacío.
- **`db/`** en el nivel superior es el punto de montaje del volumen en tiempo de ejecución. El archivo SQLite (`db/finally.db`) es creado aquí por el backend y persiste entre reinicios del contenedor gracias al volumen Docker.
- **`planning/`** contiene la documentación de todo el proyecto, incluido este plan. Todos los agentes usan los archivos de aquí como contrato compartido.
- **`test/`** contiene los tests E2E con Playwright e infraestructura de soporte (por ejemplo, `docker-compose.test.yml`). Los tests unitarios viven dentro de `frontend/` y `backend/` respectivamente, siguiendo las convenciones de cada framework.
- **`scripts/`** contiene los scripts de inicio/parada que envuelven comandos Docker.

---

## 5. Variables de Entorno

```bash
# Obligatoria salvo que LLM_MOCK=true: clave de API de OpenRouter para la funcionalidad de chat con LLM
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Modelo de OpenRouter a usar para el chat con LLM (ver sección 9)
OPENROUTER_MODEL=openrouter/dots-studio/dots-3-note-preview:free

# Proveedor preferido de OpenRouter. Es una preferencia: se permiten fallbacks
# a proveedores compatibles cuando Cerebras no sirve el modelo configurado.
OPENROUTER_PROVIDER_ORDER=cerebras

# Opcional: clave de API de Massive (Polygon.io) para datos de mercado reales
# Si no se establece, se usa el simulador de mercado integrado (recomendado para la mayoría de usuarios)
MASSIVE_API_KEY=

# Opcional: establecer en "true" para respuestas de LLM simuladas y deterministas (pruebas)
LLM_MOCK=false
```

### Comportamiento

- Si `MASSIVE_API_KEY` está establecida y no está vacía → el backend usa la API REST de Massive para los datos de mercado
- Si `MASSIVE_API_KEY` está ausente o vacía → el backend usa el simulador de mercado integrado
- Si `LLM_MOCK=true` → el backend devuelve respuestas de LLM simuladas y deterministas (para tests E2E), y no requiere `OPENROUTER_API_KEY`
- Si `LLM_MOCK=false` (o no está definida) → `OPENROUTER_API_KEY` es obligatoria para que el chat funcione
- En Docker, `--env-file .env` inyecta las variables. En local, `pydantic-settings` carga el `.env` de la raíz; las variables de entorno exportadas siempre tienen precedencia.
- `/api/health` informa que el servicio está vivo; el estado de configuración del chat debe exponerse separadamente y nunca incluir valores de claves.

---

## 6. Datos de Mercado

### Dos Implementaciones, Una Interfaz

Tanto el simulador como el cliente de Massive implementan la misma interfaz abstracta. El backend selecciona cuál usar en función de la variable de entorno. Todo el código posterior (streaming SSE, caché de precios, frontend) es agnóstico respecto a la fuente.

El contrato canónico es el código probado de `backend/app/market_data/`, en particular `base.py`, `cache.py`, `wiring.py` y `factory.py`, complementado por `planning/market_data_design.md`. `planning/market_data_interface.md` documenta ese contrato real; no define una segunda interfaz alternativa.

### Simulador (Predeterminado)

- Genera precios utilizando movimiento browniano geométrico (GBM) con deriva (drift) y volatilidad configurables por ticker
- Se actualiza en intervalos de ~500ms
- Movimientos correlacionados entre tickers (por ejemplo, las acciones tecnológicas se mueven juntas)
- "Eventos" aleatorios ocasionales — movimientos súbitos del 2-5% en un ticker para dar dramatismo
- Comienza desde precios semilla realistas (por ejemplo, AAPL ~$190, GOOGL ~$175, etc.)
- Cuando se añade un ticker nuevo (no predefinido) a la watchlist, el simulador le asigna también un precio semilla realista (generado de forma plausible) y empieza a simularlo igual que a los demás
- Se ejecuta como una tarea en segundo plano dentro del propio proceso — sin dependencias externas

### API de Massive (Opcional)

- Massive es el rebranding de Polygon.io (30 oct 2025): mismas claves de API, cuentas y endpoints; solo cambió el nombre. Ver `planning/massive_api.md` para el detalle completo.
- Sondeo (polling) mediante API REST (no WebSocket) — más simple, funciona en todos los niveles de suscripción
- Sondea la unión de todos los tickers vigilados en un intervalo configurable
- Nivel gratuito (5 llamadas/min): sondeo cada 15 segundos
- Niveles de pago: sondeo cada 2-15 segundos según el nivel
- Parsea la respuesta REST al mismo formato que el simulador

### Caché de Precios Compartida

- Una única tarea en segundo plano (el simulador o el poller de Massive) escribe en una caché de precios en memoria
- La caché guarda el último precio, el precio anterior y la marca de tiempo de cada ticker
- Los streams SSE leen de esta caché y envían actualizaciones a los clientes conectados
- Esta arquitectura permite futuros escenarios multiusuario sin cambios en la capa de datos
- Cuando aparece un ticker nuevo — por watchlist, por chat, o por una operación sobre un ticker que no está en la watchlist — el backend lo registra en caliente en la tarea de fondo antes de confirmar la escritura en base de datos: con el simulador, se le asigna un precio semilla y se simula desde el siguiente tick (~500ms); con Massive, se añade a la unión de tickers sondeados desde el siguiente ciclo de polling. Hasta que llega ese primer precio, aplican las reglas de "Valoración de Posiciones sin Precio en Caché" (sección 8) y el rechazo de operaciones sin precio disponible

### Streaming SSE

- Endpoint: `GET /api/stream/prices`
- Conexión SSE de larga duración; el cliente usa la API nativa `EventSource`
- El servidor envía actualizaciones de precio a un ritmo regular (~500ms) para la **unión** de los tickers de la watchlist del usuario y los tickers con una posición abierta (aunque ya no estén en la watchlist) — así el P&L no realizado y el mapa de calor siempre tienen precios actualizados
- Cada evento SSE contiene ticker, precio, precio anterior, marca de tiempo y dirección del cambio
- Cada evento también incluye `day_change_percent`: el cambio porcentual respecto al precio de referencia de la sesión. Con Massive, se toma del snapshot (`todaysChangePerc` / `prevDay.c`). Con el simulador, el precio semilla del día se fija como referencia al arrancar el proceso y no cambia hasta el siguiente reinicio. Este es el campo que la watchlist muestra como "% de cambio diario"; no debe confundirse con el delta tick-a-tick de `prev_price`, que solo alimenta la animación de destello
- El cliente gestiona la reconexión automáticamente (EventSource tiene reintento incorporado)
- El ritmo de ~500ms es del propio stream (lee la caché de precios en ese intervalo), no de la fuente subyacente: con el simulador el precio cambia en cada tick, pero con Massive (nivel gratuito, sondeo cada 15s) la caché solo cambia cada ~15s — el stream sigue enviando el último precio conocido cada ~500ms para conservar la misma cadencia visual ante planes de pago futuros
- La marca de tiempo de cada evento es la de la fuente/caché, no la hora de reemisión. El frontend solo agrega una muestra al sparkline si cambió la tupla `(ticker, precio, marca_de_tiempo)`; las repeticiones mantienen el precio mostrado y el estado de conexión, pero no añaden puntos. Cada serie conserva como máximo los últimos 120 puntos.
- Al conectar, el stream emite el snapshot disponible de la caché antes de los eventos periódicos. Si todavía no hay precio para un ticker, no inventa uno: espera la primera actualización del proveedor.

---

## 7. Base de Datos

### SQLite con Inicialización Diferida (Lazy)

El backend comprueba la existencia de la base de datos SQLite al arrancar (o en la primera solicitud). Si el archivo no existe o faltan tablas, crea el esquema y puebla los datos predeterminados. Esto significa:

- Sin paso de migración independiente
- Sin configuración manual de la base de datos
- Los volúmenes Docker nuevos arrancan automáticamente con una base de datos limpia y poblada

### Esquema

Todas las tablas de datos del usuario, salvo `users_profile` (cuyo propio `id` cumple ese rol), incluyen una columna `user_id` con valor predeterminado `"default"`. Esto está fijado por ahora (usuario único) pero permite un futuro soporte multiusuario sin migración de esquema.

**users_profile** — Estado del usuario (saldo de efectivo)
- `id` TEXT PRIMARY KEY (predeterminado: `"default"`)
- `cash_balance` REAL (predeterminado: `10000.0`)
- `created_at` TEXT (marca de tiempo ISO)

**watchlist** — Tickers que el usuario está vigilando
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (predeterminado: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (marca de tiempo ISO)
- Restricción UNIQUE en `(user_id, ticker)`

**positions** — Posiciones actuales (una fila por ticker por usuario)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (predeterminado: `"default"`)
- `ticker` TEXT
- `quantity` REAL (se admiten acciones fraccionarias)
- `avg_cost` REAL
- `updated_at` TEXT (marca de tiempo ISO)
- Restricción UNIQUE en `(user_id, ticker)`

**trades** — Historial de operaciones (registro de solo adición)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (predeterminado: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` o `"sell"`)
- `quantity` REAL (se admiten acciones fraccionarias)
- `price` REAL
- `executed_at` TEXT (marca de tiempo ISO)

**portfolio_snapshots** — Valor de la cartera a lo largo del tiempo (para el gráfico de P&L). Se registra cada 30 segundos mediante una tarea en segundo plano, e inmediatamente después de cada ejecución de operación.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (predeterminado: `"default"`)
- `total_value` REAL
- `is_partial` INTEGER (0/1; 1 si al menos una posición no tenía precio en `price_cache` en el momento de este snapshot)
- `recorded_at` TEXT (marca de tiempo ISO)

**chat_messages** — Historial de conversación con el LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (predeterminado: `"default"`)
- `role` TEXT (`"user"` o `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — operaciones ejecutadas, cambios realizados en la watchlist; null para mensajes del usuario)
- `created_at` TEXT (marca de tiempo ISO)

### Datos Semilla Predeterminados

- Un perfil de usuario: `id="default"`, `cash_balance=10000.0`
- Diez entradas en la watchlist: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. Endpoints de la API

### Datos de Mercado
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/stream/prices` | Stream SSE de actualizaciones de precios en vivo |

### Cartera
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/portfolio` | Posiciones actuales, saldo de efectivo, valor total, P&L no realizado |
| POST | `/api/portfolio/trade` | Ejecuta una operación: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Capturas del valor de la cartera a lo largo del tiempo (para el gráfico de P&L) |

#### Semántica de Ejecución de Operaciones (`POST /api/portfolio/trade`)

- El ticker no necesita estar en la watchlist para operar, pero sí necesita un precio disponible en la caché de precios (`price_cache`); si no hay precio para el ticker, la operación se rechaza con un error controlado (por ejemplo, HTTP 409) en vez de estimar un precio.
- El precio de ejecución es siempre el último precio de `price_cache` en el momento de procesar la solicitud — nunca un precio enviado por el cliente.
- La actualización de `cash_balance`, la fila de `positions`, el nuevo registro en `trades` y el snapshot en `portfolio_snapshots` ocurren dentro de una única transacción SQLite; si cualquier paso falla, no se aplica ninguno.
- Al ser SQLite de escritor único, las operaciones concurrentes se serializan por el propio motor; el backend no necesita bloqueo optimista adicional, pero debe reintentar ante `SQLITE_BUSY` con un backoff corto.
- Los tickers se normalizan a mayúsculas antes de tocar la base de datos, igual que en el flujo del chat.
- Si una venta deja la cantidad de una posición por debajo de un epsilon (p. ej. `1e-9`), la posición se elimina en vez de conservar un residuo por redondeo de punto flotante.

#### Valoración de Posiciones sin Precio en Caché

- Si una posición no tiene precio en `price_cache` (por ejemplo, justo tras añadir un ticker nuevo, antes de su primer tick), `GET /api/portfolio` devuelve esa posición con `current_price: null` y `unrealized_pl: null`.
- `total_value` se calcula como efectivo + suma de las posiciones que sí tienen precio; las posiciones sin precio no aportan al total hasta que llega su primer tick, y esto se documenta explícitamente en la respuesta en vez de ocultarse.
- La tarea en segundo plano que registra `portfolio_snapshots` cada 30 segundos aplica la misma regla: si hay posiciones sin precio, el snapshot se calcula igualmente con el resto de posiciones valoradas, marca `is_partial=1` (ver esquema en la sección 7) y no se bloquea a la espera de todos los precios.
- El frontend usa `is_partial` para distinguir visualmente esos tramos en el gráfico de P&L (por ejemplo, con una línea discontinua) en vez de dibujar un salto como si fuera una variación real de mercado cuando llega tarde el primer precio de una posición.

### Watchlist
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/watchlist` | Tickers actuales de la watchlist con sus últimos precios |
| POST | `/api/watchlist` | Añade un ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Elimina un ticker |

#### Forma de la Respuesta de `GET /api/watchlist`

Cada entrada usa los mismos campos que el contrato SSE (sección 6): `ticker`, `price`, `prev_price`, `day_change_percent`, `timestamp`, `direction`. Si el ticker todavía no tiene precio en `price_cache` (por ejemplo, justo tras añadirlo), esos campos se devuelven como `null` en vez de omitir la entrada de la lista.

### Chat
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/chat` | Envía un mensaje, recibe una respuesta JSON completa (mensaje + acciones ejecutadas) |
| GET | `/api/chat/messages` | Historial de `chat_messages` (más recientes primero, máx. los últimos 20) para repoblar la UI al recargar la página |
| GET | `/api/chat/status` | Indica si el chat está operativo (`LLM_MOCK=true` o `OPENROUTER_API_KEY` configurada), sin exponer valores de claves |

### Sistema
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Comprobación de estado (para Docker/despliegue) |

---

## 9. Integración con el LLM

Al escribir código que realice llamadas a LLMs, usa la skill `cerebras-inference` si está disponible en el entorno del agente — es una ayuda de conveniencia, no un requisito bloqueante. El contrato real e implementable sin depender de la skill es: llamar a LiteLLM apuntando al proveedor `openrouter`, con `model=OPENROUTER_MODEL`, pasando `provider.order=[OPENROUTER_PROVIDER_ORDER]` en `extra_body` y solicitando `response_format` para Salidas Estructuradas (Structured Outputs). El modelo se configura mediante `OPENROUTER_MODEL` y por defecto es `openrouter/dots-studio/dots-3-note-preview:free`.

`OPENROUTER_PROVIDER_ORDER=cerebras` prioriza Cerebras mediante `provider.order`, pero permite fallbacks de OpenRouter. Dots no se sirve actualmente en Cerebras, por lo que normalmente se ejecutará en un proveedor compatible (AtlasCloud actualmente); no se debe afirmar lo contrario. Esta preferencia conserva compatibilidad si se cambia más adelante a un modelo servido por Cerebras. Se registra el proveedor efectivo de cada respuesta para diagnóstico.

`OPENROUTER_API_KEY`, `OPENROUTER_MODEL` y `OPENROUTER_PROVIDER_ORDER` se definen en el archivo `.env` local de la raíz del proyecto (no versionado, está en `.gitignore`); el repositorio versiona `.env.example` como plantilla.

Dots es un modelo preview con retirada anunciada para el 30 de septiembre de 2026. Antes de esa fecha debe completarse una tarea explícita de migración: elegir el modelo de reemplazo, actualizar `OPENROUTER_MODEL` en `.env.example`, revalidar las salidas estructuradas de chat contra el nuevo modelo, y añadir una comprobación (test o log de arranque) que advierta si `OPENROUTER_MODEL` sigue apuntando a un modelo cuya fecha de retirada ya pasó.

### Cómo Funciona

Cuando el usuario envía un mensaje de chat, el backend:

1. Carga el contexto actual de la cartera del usuario (efectivo, posiciones con P&L, watchlist con precios en vivo, valor total de la cartera)
2. Carga el historial de conversación reciente desde la tabla `chat_messages` (máximo los últimos 20 mensajes)
3. Construye un prompt con un mensaje de sistema, el contexto de la cartera, el historial de conversación y el nuevo mensaje del usuario
4. Llama al LLM a través de LiteLLM → OpenRouter, solicitando salida estructurada, con Cerebras como preferencia y fallback permitido a proveedores compatibles
5. Valida el JSON completo contra el modelo Pydantic de respuesta antes de efectuar cambios
6. Ejecuta automáticamente cualquier operación o cambio de watchlist válido especificado en la respuesta
7. Almacena el mensaje y las acciones efectivamente ejecutadas en `chat_messages`
8. Devuelve la respuesta JSON completa al frontend (sin streaming token a token; un indicador de carga es suficiente)

### Esquema de Salida Estructurada

Se instruye al LLM para que responda con un JSON que coincida con este esquema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"},
    {"ticker": "NFLX", "action": "remove"}
  ]
}
```

- `message` (obligatorio): el texto conversacional mostrado al usuario
- `trades` (opcional): array de operaciones a ejecutar automáticamente. Cada operación pasa por la misma validación que las operaciones manuales (efectivo suficiente para compras, acciones suficientes para ventas)
- `watchlist_changes` (opcional): array de modificaciones de la watchlist. `action` admite `"add"` o `"remove"`

El esquema se solicita mediante `response_format` y se valida con Pydantic. Los tickers se normalizan a mayúsculas y las cantidades deben ser números finitos mayores que cero. Si la respuesta no valida como JSON estructurado, no se ejecuta ninguna acción, se registra el error sin secretos y el endpoint devuelve un error controlado. No hay fallback a texto libre para respuestas que puedan producir efectos secundarios.

### Ejecución Automática

Las operaciones especificadas por el LLM se ejecutan automáticamente — sin diálogo de confirmación. Esta es una decisión de diseño deliberada:
- Es un entorno simulado con dinero ficticio, por lo que el riesgo es nulo
- Crea una experiencia de demostración impresionante y fluida
- Demuestra capacidades de IA agéntica — el tema central del curso

Si una operación no pasa la validación (por ejemplo, efectivo insuficiente), el error se incluye en la respuesta del chat para que el LLM pueda informar al usuario.

### Orientación del Prompt de Sistema

Se debe indicar al LLM que actúe como "FinAlly, un asistente de trading con IA", con instrucciones para:
- Analizar la composición de la cartera, la concentración de riesgo y el P&L
- Sugerir operaciones con su razonamiento
- Ejecutar operaciones cuando el usuario lo solicite o esté de acuerdo
- Gestionar la watchlist de forma proactiva
- Ser conciso y basarse en datos en sus respuestas
- Responder siempre con un JSON estructurado válido

### Modo Simulado del LLM

Cuando `LLM_MOCK=true`, el backend devuelve respuestas simuladas deterministas en lugar de llamar a OpenRouter. Esto permite:
- Tests E2E rápidos, gratuitos y reproducibles
- Desarrollo sin una clave de API
- Pipelines de CI/CD

### Configuración de Aplicación

La aplicación centraliza su configuración en una clase `BaseSettings` de `pydantic-settings`. `OPENROUTER_API_KEY` no se escribe en logs ni se devuelve por API. La configuración debe permitir que el proceso arranque sin clave para servir el simulador y `LLM_MOCK`; únicamente el endpoint de chat real rechaza solicitudes cuando falta la clave.

---

## 10. Diseño del Frontend

### Disposición (Layout)

El frontend es una aplicación de una sola página con una disposición densa, inspirada en una terminal. La arquitectura de componentes específica y el sistema de disposición quedan a criterio del Ingeniero de Frontend, pero la interfaz debe incluir estos elementos:

- **Panel de watchlist** — cuadrícula/tabla de tickers vigilados con: símbolo del ticker, precio actual (destellando en verde/rojo al cambiar), % de cambio diario (campo `day_change_percent` del contrato SSE, no el delta tick-a-tick), y un mini-gráfico tipo sparkline (acumulado desde el SSE desde la carga de la página)
- **Área principal de gráficos** — gráfico más grande para el ticker actualmente seleccionado, mostrando como mínimo el precio a lo largo del tiempo. Al hacer clic en un ticker de la watchlist se selecciona aquí.
- **Mapa de calor de la cartera** — visualización treemap donde cada rectángulo es una posición, dimensionado por peso en la cartera y coloreado por P&L (verde = beneficio, rojo = pérdida)
- **Gráfico de P&L** — gráfico de líneas que muestra el valor total de la cartera a lo largo del tiempo, usando datos de `portfolio_snapshots`
- **Tabla de posiciones** — vista tabular de todas las posiciones: ticker, cantidad, coste medio, precio actual, P&L no realizado, % de cambio
- **Barra de operaciones** — área de entrada sencilla: campo de ticker, campo de cantidad, botón de compra, botón de venta. Órdenes de mercado, ejecución instantánea.
- **Panel de chat de IA** — barra lateral acoplada/colapsable. Entrada de mensajes, historial de conversación con desplazamiento, indicador de carga mientras se espera la respuesta del LLM. Las ejecuciones de operaciones y los cambios de watchlist se muestran en línea como confirmaciones.
- **Encabezado** — valor total de la cartera (actualizándose en vivo), indicador de estado de conexión, saldo de efectivo

### Notas Técnicas

- Usar `EventSource` para la conexión SSE a `/api/stream/prices`
- Se prefiere una librería de gráficos basada en canvas (Lightweight Charts o Recharts) por rendimiento
- Efecto de destello de precio: al recibir un nuevo precio, aplicar brevemente una clase CSS con transición de color de fondo, y luego eliminarla
- Todas las llamadas a la API van al mismo origen (`/api/*`) — no se necesita configuración de CORS
- Tailwind CSS para los estilos, con un tema oscuro personalizado

---

## 11. Docker y Despliegue

### Dockerfile Multi-Etapa

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI sirve los archivos estáticos del frontend y todas las rutas de la API en el puerto 8000.

### Volumen Docker

La base de datos SQLite persiste mediante un bind mount del directorio `db/` de la raíz del proyecto:

```bash
docker run -v $(pwd)/db:/app/db -p 8000:8000 --env-file .env finally
```

El directorio `db/` en la raíz del proyecto se mapea a `/app/db` en el contenedor. El backend escribe `finally.db` en esta ruta, por lo que el archivo es directamente inspeccionable/respaldable desde el host.

### Scripts de Inicio/Parada

**`scripts/start_mac.sh`** (macOS/Linux):
- Construye la imagen Docker si aún no está construida (o si se pasa el flag `--build`)
- Ejecuta el contenedor con el montaje del volumen, el mapeo de puertos y el archivo `.env`
- Imprime la URL para acceder a la aplicación
- Opcionalmente abre el navegador

**`scripts/stop_mac.sh`** (macOS/Linux):
- Detiene y elimina el contenedor en ejecución
- NO elimina el volumen (los datos persisten)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: equivalentes en PowerShell para Windows.

Todos los scripts deben ser idempotentes — seguros de ejecutar varias veces.

### Despliegue en la Nube (Opcional)

El contenedor está diseñado para desplegarse en AWS App Runner, Render o cualquier plataforma de contenedores. Como objetivo adicional (stretch goal) podría proporcionarse una configuración de Terraform para App Runner en un directorio `deploy/`, pero no forma parte de la construcción principal.

---

## 12. Estrategia de Pruebas

### Tests Unitarios (dentro de `frontend/` y `backend/`)

**Backend (pytest)**:
- Datos de mercado: el simulador genera precios válidos, la matemática del GBM es correcta, el parseo de la respuesta de la API de Massive funciona, ambas implementaciones cumplen con la interfaz abstracta
- Cartera: lógica de ejecución de operaciones, cálculos de P&L, casos límite (vender más de lo que se posee, comprar con efectivo insuficiente, vender con pérdidas), rechazo de `POST /api/portfolio/trade` cuando el ticker no tiene precio en `price_cache`, atomicidad de la transacción y reintento ante `SQLITE_BUSY`
- Streaming SSE y watchlist: cálculo de `day_change_percent`, deduplicación de sparklines cuando se repite la tupla `(ticker, precio, timestamp)`, `null` en los campos de precio para tickers sin dato aún
- Snapshots: `portfolio_snapshots.is_partial` se marca correctamente cuando falta el precio de alguna posición
- LLM: el parseo de la salida estructurada maneja todos los esquemas válidos, manejo correcto de respuestas malformadas, validación de operaciones dentro del flujo de chat, `GET /api/chat/status` refleja `LLM_MOCK`/`OPENROUTER_API_KEY` sin filtrar su valor
- Configuración: carga desde `.env` local, precedencia de variables de entorno y chat simulado sin clave
- Rutas de la API: códigos de estado correctos, formas de respuesta, manejo de errores

**Frontend (React Testing Library o similar)**:
- Renderizado de componentes con datos simulados
- La animación de destello de precio se activa correctamente ante cambios de precio
- Operaciones CRUD de la watchlist
- Cálculos de visualización de la cartera
- Renderizado de mensajes de chat y estado de carga

### Tests E2E (en `test/`)

**Infraestructura**: un `docker-compose.test.yml` independiente en `test/` que levanta el contenedor de la aplicación junto con un contenedor de Playwright. Esto mantiene las dependencias del navegador fuera de la imagen de producción.

**Entorno**: los tests se ejecutan con `LLM_MOCK=true` por defecto, para mayor velocidad y determinismo.

**Escenarios Clave**:
- Inicio limpio: aparece la watchlist predeterminada, se muestra el saldo de $10k, los precios se están transmitiendo
- Añadir y eliminar un ticker de la watchlist
- Comprar acciones: el efectivo disminuye, aparece la posición, la cartera se actualiza
- Vender acciones: el efectivo aumenta, la posición se actualiza o desaparece
- Visualización de la cartera: el mapa de calor se renderiza con los colores correctos, el gráfico de P&L tiene puntos de datos
- Chat de IA (simulado): enviar un mensaje, recibir una respuesta, la ejecución de la operación aparece en línea
- Resiliencia del SSE: desconectar y verificar la reconexión
- Reemisión SSE con Massive: comprobar que los eventos siguen llegando cada ~500ms, pero que una serie de sparkline no agrega duplicados entre dos sondeos

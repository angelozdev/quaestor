# Quaestor — P2 MCP server (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** P0 (core: domain + services base)
**Parte de:** `2026-06-16-quaestor-general-design.md` (ver arquitectura §3, despliegue/auth §4, services §7)

---

## Objetivo

Exponer Quaestor como **interfaz en lenguaje natural** para cualquier cliente MCP (hoy Claude Code; mañana MiniMax u otro). El usuario le habla a un agente —"gasté 40 mil en mercado", "¿qué tengo que pagar esta semana?"— y el agente registra, consulta y opera el backend a través de **tools MCP**. El servidor es un **adaptador delgado** sobre `services`: traduce intención del agente a llamadas de caso de uso y devuelve texto/markdown que el agente le explica al usuario. Es **LLM-agnóstico**: ningún cliente está cableado, solo el protocolo MCP.

## Alcance

- **MCP server con el SDK oficial de Python**, expuesto vía transporte remoto **streamable-HTTP** en la ruta `/mcp`, protegido por el mismo **bearer token (`APP_TOKEN`)** que la API, en el header de auth.
- **Por qué remoto y no stdio local:** el usuario no quiere correr nada en su laptop. Quaestor vive en el VPS. Con stdio habría que mantener un proceso (o un shim) local apuntando al `quaestor.db`, lo que rompe el modelo "solo el browser y el cliente MCP en la laptop" (§4). Con streamable-HTTP, Claude Code se conecta a una URL remota detrás de Caddy/HTTPS y el servidor corre junto a `services`/DB en el VPS.
- **Tools del core (arranque P2):** `registrar_gasto`, `registrar_ingreso`, `transferir`, `fijar_tasa_fx`, y las lecturas (`consultar_*` / `listar_*`: transacciones, cuentas, categorías, tags, tasa vigente).
- **No incluye** las tools de features: `crear_recurrente`/`listar_recurrentes`, `planear_pago`/`confirmar_pago`/`por_pagar`, `cerrar_mes` (P3); `fijar_presupuesto`/`estado_presupuesto`/`crear_meta`/`aporte_meta`/`progreso_metas` (P4); `reporte_mensual`/`importar_csv` (P5). P2 deja el **patrón de registro listo** para que cada uno enchufe sus tools sin tocar el transporte ni la auth.
- **Fuera de alcance:** lógica de dominio (vive en `services`/`domain`, P0), la API REST (P1), el frontend (P6).

## Aporte al modelo de datos

**Ninguno.** P2 no crea entidades, columnas ni migraciones. Es un puro adaptador de entrada: cada tool desemboca en un service que ya opera sobre el modelo definido en §5 del general. Igual que la API (P1), el MCP server **es el mismo cerebro visto por otra puerta**; añadir tablas aquí violaría la regla de oro (§3: los adaptadores nunca tocan la DB ni redefinen el modelo).

## Componentes

Bajo `backend/src/quaestor/mcp/`:

- `server.py` — construye la instancia MCP del SDK oficial, monta el transporte streamable-HTTP en `/mcp`, aplica el middleware de auth, registra las tools. Punto de entrada `python -m quaestor.mcp`.
- `auth.py` — verifica el bearer `APP_TOKEN` del header en cada request al transporte; rechaza si falta o no coincide.
- `registry.py` — el **patrón de registro**: una función `register_core_tools(mcp, ...)` que P2 implementa, y la convención para que P3/P4/P5 expongan su propio `register_*_tools(mcp, ...)` y el `server.py` los invoque todos. Crecer = añadir una línea, no tocar transporte.
- `tools/core.py` — las tools del core (gastos, ingresos, transferencias, FX, lecturas). Cada una: parsea entrada (schema Pydantic), llama al service, formatea la salida en texto/markdown.
- `format.py` — helpers para renderizar resultados de service (transacción registrada, lista, balance, tasa) a markdown legible, y para convertir errores de dominio en texto claro.

Una sesión de DB por request (igual disciplina que la API), pasada al service. Las tools no abren engines ni sesiones propias fuera de ese scope.

## Interfaz pública (tools MCP)

1 tool = 1 service, mismos verbos. Los **schemas se derivan de Pydantic** (un modelo de entrada por tool → JSON Schema que el SDK publica al cliente). La salida es **texto/markdown estructurado**, no objetos crudos.

Tools del core en P2:

| Tool | Service | Entrada (campos clave) | Salida (texto/markdown) |
|---|---|---|---|
| `registrar_gasto` | `transactions.registrar_gasto` | `payee`, `amount`, `currency`, `account`, `category?`, `date?`, `tags?`, `notes?` | confirmación: monto, cuenta, `to_base` COP, nuevo balance |
| `registrar_ingreso` | `transactions.registrar_ingreso` | igual que gasto | confirmación equivalente |
| `transferir` | `transactions.transferir` | `from_account`, `to_account`, `amount`, `currency`, `date?`, `notes?` | par creado (origen/destino), balances resultantes |
| `fijar_tasa_fx` | `fx.fijar_tasa` | `date`, `usd_cop` | tasa registrada para la fecha |
| `consultar_transacciones` | reads | filtros: `desde?`, `hasta?`, `account?`, `category?`, `tag?`, `type?`, `status?` | tabla markdown + totales |
| `listar_cuentas` | reads | — | cuentas con balance y moneda |
| `listar_categorias` | reads | — | categorías + grupo + flags |
| `consultar_tasa_fx` | `fx.tasa_vigente` | `date?` | tasa vigente para la fecha |

Convenciones que heredan las tools: montos como **enteros en centavos** en moneda original; **signo por `type`** (no en el monto); agregados/balances en `to_base` COP; al registrar, `status=posted` por defecto y `source=agent`. Aceptan nombres legibles (cuenta/categoría/tag por nombre, no por id) y el adaptador los resuelve antes de llamar al service.

## Lógica y reglas clave

- **Cero lógica de dominio en P2.** Validar, convertir FX, cuadrar transferencias, actualizar balance → todo en `services`/`domain`. La tool solo adapta forma de entrada/salida.
- **Cada tool llama a un service; nunca toca la DB.** Idéntico cerebro que la API.
- **Resolución de nombres:** el agente habla con nombres ("Bancolombia", "Mercado"); la tool los resuelve a entidades vía service de lectura. Si no existe, devuelve texto que sugiere la opción correcta o crear la entidad.
- **Defaults amables:** `date` ausente → hoy; `currency` ausente → moneda base (COP). Esto reduce fricción en lenguaje natural, pero el monto siempre se pasa explícito.
- **Salida pensada para el agente:** markdown corto y estructurado que el LLM pueda parafrasear (no JSON crudo). Incluye el dato que cierra el loop: balance nuevo tras un gasto, `to_base` en una tx USD, total en una consulta.
- **Patrón de crecimiento:** cuando P3/P4/P5 aterricen, registran sus tools vía `register_*_tools` sin tocar `server.py` salvo una línea de wiring. El transporte y la auth no se re-litigan.

## Errores

- Los **errores de dominio se devuelven como texto claro, no excepciones crudas.** El adaptador captura los errores tipados de `domain` (`ValidationError`, `MissingRate`, `TransferImbalance`…) y los formatea para que el agente los explique. Ej.: `MissingRate` → "No tengo la tasa USD→COP para esa fecha. Dime la tasa con `fijar_tasa_fx` y reintento." Nunca llega un stack trace al cliente.
- **Auth:** request sin bearer válido → el transporte responde rechazado a nivel de protocolo (no se ejecuta ninguna tool).
- **Atomicidad:** transferencias commit/rollback en el service (las dos transactions o ninguna); si falla, la tool reporta texto y la DB queda intacta.
- **Entrada inválida** (campo faltante/tipo errado) → la valida el schema Pydantic antes de tocar el service; el SDK devuelve el detalle al cliente.

## Testing y criterio de "listo"

- **Unit/adaptador:** cada tool con service real sobre **SQLite in-memory** — registrar gasto/ingreso, transferir, fijar/consultar FX, listar/consultar. Verifica formateo de salida y traducción de errores de dominio a texto (sin excepciones crudas).
- **Auth:** request sin token o con token errado → rechazado; con `APP_TOKEN` correcto → pasa.
- **Patrón de registro:** todas las tools esperadas quedan expuestas tras `register_core_tools`; un `register_*` adicional se monta sin tocar el transporte.
- **Criterio de "listo":** desde **Claude Code conectado al `/mcp` remoto**, el usuario **registra una transacción hablando en lenguaje natural** (ej. "gasté 50 mil en almuerzo con la débito") y luego **consulta el resultado** ("¿cuánto llevo gastado hoy?") obteniendo la transacción recién creada. El loop completo NL → tool → service → texto funciona contra el backend real.

## Integración con otros sub-proyectos

- **Cómo conecta Claude Code:** config de MCP remoto apuntando a `https://quaestor.tudominio.com/mcp`, con el `APP_TOKEN` en el header de auth. Caddy enruta `/mcp` → MCP server (§4) sobre HTTPS. **MiniMax:** se enchufa igual cuando soporte MCP remoto; no requiere cambios en el servidor (es LLM-agnóstico).
- **P0 (core):** dependencia dura. P2 consume `services` y `domain` tal cual; no los modifica.
- **P1 (API):** hermano simétrico. Mismos services, distinta puerta (REST vs tools). Cero lógica duplicada; comparten `APP_TOKEN`.
- **P3/P4/P5:** registran sus tools de features mediante el patrón de `registry.py`. Cada uno aporta sus services y su `register_*_tools`; P2 ya dejó el transporte, la auth y el formateo listos.
- **P7 (despliegue):** corre el MCP server como servicio `mcp` en `docker-compose.yml`, detrás de Caddy, con `APP_TOKEN` por env y el mismo `quaestor.db` (volumen) que API y rollover.

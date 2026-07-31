---
slug: fx-read-time-conversion
checkpoint: 4
plan_status: approved
created: 2026-07-30
---

# Plan — 005 fx-read-time-conversion

Arquitectura confirmada por Angelo en sesión 2026-07-30.

## Architecture

### Dónde vive la TRM

Campo nuevo en `Settings` — la tabla de una sola fila que ya existe
(`id=1`, `base_currency`, `default_source_account_id`):

```python
class Settings(SQLModel, table=True):
    ...
    usd_cop: Decimal | None = None   # Numeric(18,6); None = TRM nunca fijada
```

Se eliminan la tabla `fx_rate` y el modelo `FxRate` (ADR-0031 enmendado:
TRM escalar).

**Alternativa descartada:** tabla propia de una fila (`trm`) — más
ceremonia (modelo + migración + queries) sin ganancia; `Settings` ya es
el hogar de la config global.

### Núcleo de conversión (domain, puro)

`domain/money.py`:

- `to_cop_cents(amount_cents: int, currency: str, trm: Decimal) -> int`
  — COP = identidad; USD × trm con redondeo half-up al centavo COP.
  Reemplaza a `to_base_cents`. **Única puerta de conversión**: regla de
  code-review del ADR-0031 — ningún caller guarda montos convertidos.
- `implied_rate(sent_cents: int, received_cents: int) -> Decimal` — el
  rate informativo de transfers cross-currency (AC-8).

`services/fx.py` queda en dos funciones:

- `set_trm(session, usd_cop) -> Decimal` — valida > 0, sobreescribe
  `Settings.usd_cop` (last write wins: job diario y corrección manual
  usan la misma puerta).
- `get_trm(session) -> Decimal` — `Settings.usd_cop is None` →
  `MissingRate("set the TRM")` (mapea a 409 en REST, igual que hoy).

`get_current_rate(session, date)` y `set_fx_rate(session, date, rate)`
mueren.

### Lecturas (services)

Cada read path que produce cifras COP — `reports`, `budgets`,
`month_aggregate`, `goals`, `planned`, `recurring`, formatters de
`mcp/format.py` — hace **un solo** `get_trm(session)` al inicio del
request y pasa el valor hacia abajo; la suma por fila usa
`to_cop_cents(t.amount, t.currency, trm)` en Python.

- "Siempre exigir TRM" (decisión AC-9): el `get_trm` va incondicional al
  tope del read path — sin TRM fijada, el read falla claro aunque todos
  los datos sean COP.
- `month_aggregate` hoy suma `to_base` en SQL (`func.sum`); pasa a suma
  en Python. Single-user local, miles de filas: trivial (presupuesto en
  Performance budgets).
- `reports.usd_share`: numerador = gasto USD convertido, denominador =
  total convertido; misma puerta.

### Registro y transfers (services)

- `register_expense` / `register_income`: pierden el parámetro
  `fx_rate`; `_resolve_fx` se elimina. Solo `amount` + `currency` se
  guardan. Registrar funciona sin TRM fijada (AC-1).
- `transfer()`: firma pasa a montos explícitos sent/received.
  - Leg origen: `amount=sent`, `currency=cuenta_origen.currency`.
  - Leg destino: `amount=received`, `currency=cuenta_destino.currency`.
  - Misma moneda: un monto (received = sent) — comportamiento actual.
  - La validación "P0 transfer: both accounts must use the transfer
    currency" se elimina; se mantienen: montos > 0, cuentas distintas.
  - Cada balance se mueve por el monto físico de su leg. No se guarda
    rate (implícito = ratio).
- `Transaction` modelo: se eliminan las columnas `fx_rate` y `to_base`.

### Superficie REST/MCP (api, mcp)

- Schemas de transacción: fuera `to_base` y `fx_rate`; entra
  `cop_equivalent: int` **calculado al leer** (el pipeline de aceptación
  ya bindea ese nombre). Si la TRM falta, el request entero falla 409.
- `/fx`: `GET` devuelve la TRM actual (sin parámetro de fecha); `POST`
  la fija. `FxIn`/`FxOut` pierden `date`.
- Tools MCP `set_fx_rate` / `get_fx_rate`: mantienen nombre y tier
  (write-safe / read, ADR-0020), semántica escalar. Formatters computan
  equivalentes al leer. Paridad REST/MCP intacta (ADR-0006/0009).

### Migración (una revisión Alembic)

Orden dentro de la misma revisión:

1. Añadir `settings.usd_cop` (nullable).
2. **Precargar**: copiar el `usd_cop` de la fila más reciente de
   `fx_rate` a `Settings.usd_cop` — se sale de la migración con la TRM
   poblada, sin `MissingRate` sorpresa post-upgrade.
3. Drop columnas `transaction.fx_rate`, `transaction.to_base`.
4. Drop tabla `fx_rate`.

SQLite (dev) vía `batch_alter_table`; Postgres (real) directo. En datos
reales: humano al volante (gate de autonomía del manifest) + `just
backup` inmediatamente antes — pasos de operador en `runbook.md`.

### Job diario

`run_daily` llama `set_trm(session, rate)` — mismo fetch, sin fecha. El
fallo de fetch sigue siendo no-fatal (ADR-011): la TRM anterior queda
vigente.

### Frontend

- `transaction-create-dialog` / `transaction-edit-dialog`: fuera el
  campo `fxRate`.
- Transfer: cuando las monedas de las cuentas difieren, segundo campo de
  monto (recibido) + rate implícito (recibido ÷ enviado) mostrado en
  vivo, solo informativo.
- Lista de transacciones: usa `cop_equivalent` de la API.
- Página Settings (ya consume `/fx` hoy): pasa a un solo campo "TRM
  actual" editable, sin fecha — la vía manual principal para corregirla.
  Las otras vías: tool MCP `set_fx_rate` (chat) y `POST /fx` directo; el
  job diario la refresca cada día.

### Data flow (resumen)

```
escritura:  dialog/MCP → services.transactions (solo amount+currency) → DB
TRM:        job diario ─┐
            corrección ─┴→ services.fx.set_trm → Settings.usd_cop
lectura:    services.<read path> → fx.get_trm (1 vez) → money.to_cop_cents
            por fila → cifras COP → REST schema (cop_equivalent) / MCP format
```

## Charter Check

| Regla del charter | Estado | Nota |
|---|---|---|
| §1 DAE + ATDD: feature nace por el pipeline de aceptación | ✅ | spec.md aprobado + pipeline rojo (24/2) antes de implementar |
| §1 Decisiones arquitectónicas como ADR | ✅ | ADR-0031 (enmendado a TRM escalar) cubre la decisión completa |
| §2 Postura local-only (ADR-0026/0030) | ✅ | Todo local; migración real en el Postgres local; Render intocado |
| §2 Layering api → services → domain → db | ✅ | Conversión pura en domain, TRM en services, routers thin |
| §2 Paridad MCP + tiers (ADR-0006/0009/0020) | ✅ | Tools mantienen nombre/tier; AC-13 la bloquea en aceptación |
| §3 Código/identificadores en inglés (ADR-0001); UI copy español | ✅ | `usd_cop`, `to_cop_cents`, `cop_equivalent`; copy del segundo monto en español |
| §3 pnpm only / Biome / vitest colocado | ✅ | Sin dependencias nuevas; tests colocados |
| §3 Soft-delete uniforme (ADR-0005) | n/a | No se tocan masters |
| §6 Strict gate: tests backend Y frontend de la superficie tocada | ✅ | Test strategy abajo; ambos streams antes de merge |
| §7 Autonomía medium + gates de datos | ✅ | Migración real = humano (path override del manifest) — runbook.md |
| Auto: stance de autonomía | ✅ | medium; `migrations/**` y `.dev-data/**` → low per manifest |
| Auto: independencia de verificación (Principio 7) | ✅ | CP7 verify correrá con `agent_id` distinto al implementador de CP5 |
| Auto: política de mutación | ✅ | `atdd:mutate` sobre módulos cambiados en CP8 Harden |
| Auto: presupuestos de performance | ✅ | Sección abajo (autonomía medium: informativos, no gate) |

**Amendments:** ninguno — sin desviaciones ⚠️. La única decisión nueva
(TRM escalar) ya está registrada como enmienda del ADR-0031.

## Phasing

Fases = slices verticales; las tareas concretas emergen de los specs
(un spec = un ciclo TDD, vía `atdd:atdd-team`). La suite completa gatea
el cierre de cada fase, no cada commit intermedio.

- **F1 — Núcleo TRM** (suite verde se mantiene): `Settings.usd_cop` en
  el modelo, `fx.set_trm`/`get_trm`, `money.to_cop_cents`/`implied_rate`
  + unit tests. Los paths viejos siguen intactos.
- **F2 — Corte del snapshot** (el slice grande): drop de columnas en el
  modelo + migración 0005 (con precarga de TRM) + reescritura de TODOS
  los consumidores de `to_base` (write paths: register/goals/planned/
  recurring; read paths: reports/budgets/month_aggregate) + schemas REST
  (`cop_equivalent`, `/fx` escalar) + job diario. Al cierre: backend
  verde, mayoría de escenarios de aceptación verdes.
- **F3 — Transfers cross-currency**: `transfer()` sent/received, REST +
  MCP, validaciones atómicas. Cierra AC-6/7/8(parcial)/11.
- **F4 — Frontend**: dialogs sin fxRate, segundo monto + rate implícito,
  Settings de TRM única, lista con `cop_equivalent` + vitest.
- **F5 — Cierre**: run completo de aceptación verde (24 rojos → 0),
  ajuste fino de wrappers de handlers si algún nombre difiere,
  re-check de spec-guardian.

## Performance budgets

(Autonomía medium — informativos, no gate de CI.)

- 1 sola query de TRM por request de lectura; prohibido el lookup por
  fila (N+1).
- Reporte mensual < 100 ms con ~10k transacciones locales (suma en
  Python, conversión O(1) por fila).
- La migración corre en segundos sobre los datos reales (drop de 2
  columnas + 1 tabla + 1 update de Settings).

## Collaboration schedule

- **Hecho**: arquitectura confirmada (este plan).
- **Auto**: CP5 implement se despacha solo (autonomía medium) al cerrar
  este checkpoint.
- **Humano re-entra en**: (1) handoff de CP5 — revisión del diff; (2)
  CP7 verify — resultados; (3) runbook — migración sobre datos reales
  (`just backup` + upgrade, pasos en runbook.md); (4) merge a main
  (siempre humano, §7).
- Stuck-loop threshold 3 (manifest): al tercer intento fallido sobre lo
  mismo, el agente para y pregunta.

## Execution modes

- CP5 vía `atdd:atdd-team` (implementer role), branch
  `fx-read-time-conversion`, autonomía medium.
- Paths a autonomía low (manifest): `backend/src/quaestor/migrations/**`
  y `.dev-data/**` — el implementador escribe la migración pero NO la
  ejecuta contra datos reales; eso es del runbook.
- `acceptance.impact_analysis` no está activado — cada ciclo corre el
  run completo (26 ejecuciones, 0.4 s: barato).

## Test strategy

`feature.md` no trae `validation_method` → stack DAE por defecto,
explícito:

- **Aceptación**: `./run-acceptance-tests.sh features/005-...` — 26
  ejecuciones generadas del spec. Baseline rojo 24/2; meta 26/26 verdes.
  Los 2 verdes actuales (AC-7 misma moneda, AC-11 misma cuenta) son
  candados de regresión: si se rompen, F3 rompió comportamiento vivo.
- **Unit backend**: pytest host-side (SQLite in-memory), baseline 91
  archivos. Nuevos: money (conversión/redondeo half-up/implied_rate),
  fx (set/get TRM, MissingRate), transfer legs, migración (seed rev-0004
  → upgrade head, ya cubierta por AC-12 host-side).
- **Unit frontend**: vitest colocado — dialog de transfer (segundo
  monto condicional + implied rate), settings TRM.
- **Mutación**: `atdd:mutate` sobre `money.py`/`fx.py`/`transactions.py`
  en CP8 Harden.
- **Gate estricto (§6)**: backend + frontend verdes para la superficie
  tocada antes de merge; el run de aceptación completo antes de push
  (regla del pipeline).
- **Datos reales**: la validación final de la migración es el runbook
  (humano) — AC-12 no se declara cerrado en CP7 sin sus pasos
  completados.

# Quaestor — P3 Motor temporal (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** P0 (se expone vía P1/P2)
**Parte de:** 2026-06-16-quaestor-general-design.md

## Objetivo

Dar a Quaestor la dimensión **temporal**: obligaciones recurrentes (gastos e ingresos, automáticos y manuales), pagos sueltos a futuro, la vista **"Por pagar"** y el **cierre de mes** (rollover) que materializa lo que toca cada periodo. P3 implementa la semántica `planned` sobre `Transaction.status` (campo definido por P0) y responde el dolor central: *"¿qué me falta por pagar esta semana?"*.

## Alcance

**En:**
- Modelos `RecurringItem` y `RecurringOccurrence` (+ sus migraciones).
- Services de recurrentes, pagos planeados/por-pagar, confirmación y omisión.
- `cerrar_mes(YYYY-MM)`: rollover **atómico e idempotente** con mecanismo de **hooks** extensible.
- Semántica `planned` → `posted` end-to-end (sin tocar balance hasta confirmar).

**Fuera:**
- Presupuestos y metas (P4). P3 solo deja **registrados los seams de hooks** (rollover y post-confirm) para que P4 enganche `proponer_aportes_meta` y `registrar_aporte_confirmado`.
- Reportes y agregados de pendientes en el reporte mensual (P5 consume `por_pagar`).
- Wiring concreto de tools/endpoints (P1/P2 los exponen; aquí se especifica el contrato).
- Cualquier cambio a reglas de dinero/FX/signo/balance: P3 las **reusa** de P0/domain, no las redefine.

## Aporte al modelo de datos

P3 añade dos entidades (ninguna redefine lo de P0):

| Entidad | Campos clave |
|---|---|
| **RecurringItem** | `name`, `payee`, `type` (expense/income), `mode` (auto/manual), `amount` (default, centavos moneda original), `currency`, `category_id`, `account_id`, `frequency` (monthly/weekly/biweekly/yearly), `due_day`, `start_date`, `end_date?`, `active` |
| **RecurringOccurrence** | `recurring_id`, `period` (YYYY-MM), `status` (posted/planned/skipped), `transaction_id?`, `created_at` |

- `RecurringOccurrence` es la **marca de idempotencia** del rollover: índice **único** `(recurring_id, period)` → garantiza una sola occurrence por recurrente y periodo.
- P3 da uso real a `Transaction.status` ∈ `{planned, posted}` (columna ya creada por P0) y a `Transaction.recurring_id?` (FK a `RecurringItem`).
- Una occurrence con `transaction_id` apunta a la tx que materializó (auto→`posted`, manual→`planned`). `skipped` no tiene tx.

## Componentes

- `services/recurring.py` — alta/listado de recurrentes, omisión de recurrente.
- `services/planned.py` — `planear_pago`, `confirmar_pago`, `omitir_pago`, `por_pagar`.
- `services/rollover.py` — `cerrar_mes` + **registro de hooks de rollover**.
- `domain/rules.py` (extensión) — `toca_periodo(item, period)` (¿el recurrente aplica a ese mes según frequency/start/end?) y `fecha_vencimiento(item, period)` (due_day → date, con clamp de fin de mes).
- Todo escribe vía la session/transacción de P0; ninguna lógica de dinero se duplica (montos en centavos, `to_base` COP, signo por `type`, balance solo en `posted`).

## Interfaz pública (services)

Firmas (params relevantes; devuelven el objeto creado/afectado o la vista pedida):

- `crear_recurrente(name, payee, type, mode, amount, currency, category_id, account_id, frequency, due_day, start_date, end_date=None) -> RecurringItem`
- `listar_recurrentes(active=None) -> list[RecurringItem]`
- `planear_pago(payee, amount, currency, due_date, account_id, category_id, notes=None) -> Transaction` — crea tx **`planned`** suelta (sin `recurring_id`). No afecta balance.
- `confirmar_pago(tx_id, amount=None, date=None) -> Transaction` — `planned` → `posted`; aplica el monto/fecha reales si vienen, recalcula `to_base`, actualiza balance de la cuenta. Si la tx proviene de una **occurrence manual**, sincroniza esa occurrence a `status=posted`.
  - **Transferencia planeada:** si la tx es `type=transfer`, en vez de postear un solo lado, **materializa la transferencia real** vía `transferir` de P0 (par posted, atómico) hacia la cuenta destino. Capacidad genérica (no específica de metas).
  - Al final dispara los **hooks post-confirm** (seam abajo) en la misma transacción — así P4 registra la `GoalContribution` cuando la tx lleva `goal_id`, sin que P3 conozca metas.
- `omitir_pago(tx_id) -> Transaction` — marca una tx `planned` suelta como omitida (cancelada); si viene de occurrence, la occurrence pasa a `skipped`.
- `omitir_recurrente(recurring_id, period) -> RecurringOccurrence` — crea/marca la occurrence de ese periodo como `skipped` (el rollover no la volverá a tocar).
- `por_pagar(desde, hasta) -> {items: list[Transaction], total_base: int}` — todas las tx `planned` con vencimiento en la ventana `[desde, hasta]`, ordenadas por fecha, + total en `to_base` COP. Es la **cola única de confirmación** (ADR-007): incluye recurrentes manuales, pagos sueltos (`planear_pago`) y aportes de meta propuestos (P4) — los tres son tx `planned`, sin ramas especiales.

`cerrar_mes` y el registro de hooks se especifican abajo.

## Lógica y reglas clave

### Reglas firmes (heredadas, no re-litigadas)
- Solo `posted` afecta balance y reportes. `planned` **solo** vive en `por_pagar` (y, vía P5, en el reporte como alerta).
- **`confirmar_pago` es la única transición `planned` → `posted`.** Nada más cambia ese estado hacia adelante.
- `planear_pago` y el brazo manual del rollover crean tx `planned` **sin tocar balance**.
- Rollover **atómico** (commit/rollback) e **idempotente**.

### `cerrar_mes(YYYY-MM)` — rollover idempotente con hooks
**Disparo automático (ADR-017):** lo invoca el `scheduler` de P7, **diario**, vía `ensure_mes_cerrado(mes_actual)` — el día 1 materializa el mes, los demás días son no-op, un día perdido se auto-cura. **No es una tool de usuario**; el rollover se opera solo. Por eso la idempotencia (abajo) es requisito de robustez, no solo de corrección.

`cerrar_mes` no hardcodea los pasos: ejecuta, en orden, una **lista registrada de hooks de rollover**, todo dentro de **una sola transacción**. Si cualquier paso falla, rollback completo.

```
ROLLOVER_HOOKS: list[Callable[[period, session], None]] = []

def registrar_hook_rollover(fn): ROLLOVER_HOOKS.append(fn)

def cerrar_mes(period):
    with session.begin():            # atómico
        for hook in ROLLOVER_HOOKS:  # orden de registro
            hook(period, session)
```

**Paso que registra P3** — `aplicar_recurrentes(period, session)`:
1. Por cada `RecurringItem` con `active=True` y `toca_periodo(item, period)` **que aún no tenga `RecurringOccurrence` para ese `period`**:
   - `mode=auto` → crea tx **`posted`** con el `amount` default (signo por `type`, `to_base` congelado), actualiza balance; crea occurrence `status=posted` enlazada a la tx.
   - `mode=manual` → crea tx **`planned`** con vencimiento `fecha_vencimiento(item, period)`, **sin tocar balance**; crea occurrence `status=planned` enlazada a la tx (aparecerá en `por_pagar`).
2. Si ya existe occurrence (cualquier status: posted/planned/skipped) para `(recurring_id, period)` → **se salta**. Por eso re-ejecutar `cerrar_mes` del mismo periodo **no duplica** nada.

Idempotencia garantizada por el único `(recurring_id, period)`: el chequeo de existencia + el constraint hacen que un segundo `cerrar_mes` sea no-op para recurrentes ya procesados.

### Seam con P4 (hooks de rollover) — explícito
El rollover también debe **proponer aportes de metas**, pero **las metas las define P4** y el orden de build es **P3 → P4**. Para no acoplar P3 a un modelo que aún no existe, `cerrar_mes` se diseña como **lista extensible de hooks**:

- **P3** registra `aplicar_recurrentes` (este sub-proyecto).
- **P4**, cuando exista, registrará `proponer_aportes_meta` vía `registrar_hook_rollover(...)` **sin modificar `cerrar_mes`**. Aporte **flexible** (ADR-006): ese hook **no transfiere plata**; por cada `Goal` activa crea una tx **`planned`** (aporte propuesto a la cuenta de ahorro, vence fin de periodo) que cae en "Por pagar". La `GoalContribution` se registra al **confirmar** (ver seam post-confirm), no aquí. Idempotencia: P4 la define (una propuesta `planned` por `(goal_id, period)`).
- Contrato del seam: cada hook es `(period, session) -> None`, corre dentro de la misma transacción del rollover, debe ser **idempotente por sí mismo**, y un fallo en cualquier hook aborta todo el cierre. El orden es el de registro (recurrentes antes que aportes de meta).

Esto deja a P3 cerrado y testeable sin P4, y a P4 enganchándose por composición.

### Seam post-confirm (para que P4 registre la `GoalContribution`)
Un aporte de meta propuesto es una tx `planned` que pasa por la **misma cola "Por pagar"** que todo lo demás (ADR-007). Cuando se confirma, además de volverse `posted` (transfer interna a la cuenta de ahorro), P4 necesita registrar la `GoalContribution`. Para que **P3 no conozca metas**, `confirmar_pago` expone un **hook post-confirm** simétrico al de rollover:

```
POST_CONFIRM_HOOKS: list[Callable[[tx, session], None]] = []
def registrar_hook_post_confirm(fn): POST_CONFIRM_HOOKS.append(fn)
# dentro de confirmar_pago, tras posted, en la misma transacción:
for hook in POST_CONFIRM_HOOKS: hook(tx, session)
```

- **P4** registra un hook que, si la tx confirmada lleva `goal_id` (FK que P4 agrega vía migración), crea la `GoalContribution(source=confirmado, amount=tx.amount, transaction_id=tx.id)`.
- El hook corre **dentro de la transacción** de `confirmar_pago`; si falla, la confirmación entera hace rollback. P3 ignora qué hace el hook.
- Para una tx `planned` sin `goal_id` (pago suelto, recurrente manual), no hay hook que aplique → comportamiento idéntico al actual.

## Errores

Errores tipados de `domain`, mapeados por P1 a 4xx y por P2 a texto estructurado:
- `ValidationError` — `due_day` fuera de rango para la frequency, `end_date < start_date`, `amount ≤ 0`, `currency`/`type`/`mode`/`frequency` inválidos, ventana de `por_pagar` invertida.
- `NotFound` — `recurring_id` / `tx_id` inexistente.
- `IllegalTransition` — `confirmar_pago`/`omitir_pago` sobre una tx que no está en `planned`.
- `MissingRate` (de P0) — `confirmar_pago`/rollover de una tx en moneda extranjera sin tasa FX para la fecha; el rollover hace rollback completo.

## Testing y criterio de "listo"

`pytest` sobre `services` + `domain` con SQLite in-memory:
- **Idempotencia del rollover:** `cerrar_mes(M)` dos (y tres) veces no crea occurrences ni tx duplicadas; balances iguales tras la 2.ª corrida.
- **Auto vs manual:** auto deja tx `posted` y mueve balance; manual deja tx `planned`, occurrence `planned`, **balance sin cambios**.
- **`planned` no afecta balance:** `planear_pago` y manual no alteran `Account.balance` ni agregados.
- **`por_pagar` por ventana:** devuelve solo las `planned` dentro de `[desde, hasta]`, ordenadas, con `total_base` correcto; excluye `posted` y `skipped`.
- **`confirmar_pago` con monto ajustado:** `planned` → `posted` con monto/fecha reales, `to_base` recalculado, balance movido; si venía de occurrence manual, la occurrence pasa a `posted`.
- **Omitir:** `omitir_recurrente` deja `skipped` y el rollover lo respeta (no recrea); `omitir_pago` cancela la tx suelta.
- **Atomicidad:** fallo a mitad de rollover (p. ej. `MissingRate`) revierte todo.
- **Seam:** un hook de prueba registrado vía `registrar_hook_rollover` corre dentro de la misma transacción y un fallo suyo aborta el cierre.

**Listo cuando** todos los tests anteriores pasan en verde, el constraint único `(recurring_id, period)` está aplicado, y existen las **tools MCP** de usuario (`crear_recurrente`, `listar_recurrentes`, `planear_pago`, `confirmar_pago`, `omitir_pago`, `omitir_recurrente`, `por_pagar`) y los **endpoints REST** correspondientes. **`cerrar_mes` NO es tool de usuario** (ADR-017): lo invoca el `scheduler` de P7; queda como service (+ endpoint `/rollover` interno opcional para admin/debug). El **wire concreto** lo hacen P2 (`/recurring`, `/planned`) y P1 sobre estos services, sin lógica duplicada.

## Integración con otros sub-proyectos

- **P0 (depende):** consume models/db/session, reglas de dinero/FX/signo, `Transaction.status` y `Transaction.recurring_id`. No redefine nada de P0.
- **P1 (HTTP API):** expone routers `/recurring`, `/planned`, `/rollover` como espejo de estos services; mapea errores tipados a 4xx.
- **P2 (MCP):** expone una tool por service de usuario (mismos verbos en lenguaje natural: *"¿qué me falta por pagar esta semana?"* → `por_pagar`; *"confirma el pago de la luz"* → `confirmar_pago`). `cerrar_mes` no se expone (lo corre el scheduler, ADR-017).
- **P4 (Presupuestos + Metas):** se engancha por **dos seams** sin tocar P3: al **hook de rollover** con `proponer_aportes_meta` (crea aportes `planned`, no transfiere) y al **hook post-confirm** de `confirmar_pago` (registra la `GoalContribution` al confirmar). P4 agrega `goal_id` a `Transaction` por migración propia. Orden de build P3 → P4. El `safe_to_spend` de P4 **consume las obligaciones del mes** que expone P3 (`por_pagar` / `planned` + recurrentes) para calcular "comprometido".
- **P5 (Reportes + Importer):** consume `por_pagar` para la línea de "recurrentes / pagos pendientes" y la alerta de manuales sin confirmar en el reporte mensual.

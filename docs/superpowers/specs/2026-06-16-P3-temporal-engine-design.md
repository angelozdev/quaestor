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
| **RecurringItem** | `name`, `payee`, `type` (expense/income), `mode` (auto/manual), `amount` (default, centavos moneda original), `currency`, `category_id`, `account_id`, **`interval_unit`** (day/week/month/year), **`interval_count`** (≥1), `start_date` (ancla), `end_date?`, `active` |
| **RecurringOccurrence** | `recurring_id`, **`due_date`** (fecha de vencimiento concreta), `status` (posted/planned/skipped), `transaction_id?`, `created_at` |

- **Frecuencia genérica cada-N (ADR-020):** la frecuencia es `interval_count × interval_unit` anclada en `start_date`. Cada vencimiento = `start_date + k × intervalo`, con **clamp de fin de mes** para unit `month`/`year` (día 31 → 30/28). Mapea mensual=`1 month`, trimestral=`3 month`, cada-4-meses=`4 month`, semestral=`6 month`, anual=`12 month`, semanal=`1 week`, quincenal=`2 week`.
- `RecurringOccurrence` es la **marca de idempotencia**: índice **único** `(recurring_id, due_date)` → una sola occurrence por recurrente y fecha de vencimiento (un recurrente sub-mensual genera varias en el mes, una por `due_date`).
- P3 da uso real a `Transaction.status` ∈ `{planned, posted}` (columna ya creada por P0) y a `Transaction.recurring_id?` (FK a `RecurringItem`).
- Una occurrence con `transaction_id` apunta a la tx que materializó (auto→`posted`, manual→`planned`). `skipped` no tiene tx.

## Componentes

- `services/recurring.py` — alta/listado de recurrentes, omisión de recurrente, y **`materializar_vencidos(hasta_fecha)`** (due-driven: crea las occurrences con `due_date ≤ hasta_fecha` aún no existentes).
- `services/planned.py` — `planear_pago`, `confirmar_pago`, `omitir_pago`, `por_pagar`.
- `services/rollover.py` — `cerrar_mes` (cierre del **mes calendario**: rollover de sobres + hooks) + **registro de hooks de rollover**.
- `domain/rules.py` (extensión) — `fechas_vencimiento(item, desde, hasta)` (genera las `due_date` del recurrente en la ventana `[desde, hasta]` por intervalo `interval_count × interval_unit` desde `start_date`, respetando `end_date` y con **clamp de fin de mes** para unit month/year).
- Todo escribe vía la session/transacción de P0; ninguna lógica de dinero se duplica (montos en centavos, `to_base` COP, signo por `type`, balance solo en `posted`).

## Interfaz pública (services)

Firmas (params relevantes; devuelven el objeto creado/afectado o la vista pedida):

- `crear_recurrente(name, payee, type, mode, amount, currency, category_id, account_id, interval_unit, interval_count, start_date, end_date=None) -> RecurringItem` — frecuencia genérica cada-N (ADR-020).
- `listar_recurrentes(active=None) -> list[RecurringItem]`
- `materializar_vencidos(hasta_fecha, session) -> list[RecurringOccurrence]` — **due-driven** (lo corre el scheduler diario, P7): por cada recurrente activo crea las occurrences con `due_date ≤ hasta_fecha` que aún no existen (`auto`→tx `posted` en su fecha y balance; `manual`→tx `planned`, sin balance). Idempotente por `(recurring_id, due_date)`. **No es tool de usuario.**
- `planear_pago(payee, amount, currency, due_date, account_id, category_id, notes=None) -> Transaction` — crea tx **`planned`** suelta (sin `recurring_id`). No afecta balance.
- `confirmar_pago(tx_id, amount=None, date=None) -> Transaction` — `planned` → `posted`; aplica el monto/fecha reales si vienen, recalcula `to_base`, actualiza balance de la cuenta. Si la tx proviene de una **occurrence manual**, sincroniza esa occurrence a `status=posted`.
  - **Transferencia planeada:** si la tx es `type=transfer`, en vez de postear un solo lado, **materializa la transferencia real** vía `transferir` de P0 (par posted, atómico) hacia la cuenta destino. Capacidad genérica (no específica de metas).
  - Al final dispara los **hooks post-confirm** (seam abajo) en la misma transacción — así P4 registra la `GoalContribution` cuando la tx lleva `goal_id`, sin que P3 conozca metas.
- `omitir_pago(tx_id) -> Transaction` — marca una tx `planned` suelta como omitida (cancelada); si viene de occurrence, la occurrence pasa a `skipped`.
- `omitir_recurrente(recurring_id, due_date) -> RecurringOccurrence` — crea/marca la occurrence de esa fecha de vencimiento como `skipped` (`materializar_vencidos` no la volverá a tocar). Omite **una ocurrencia puntual** (no todo el recurrente; para eso, `active=False`).
- `por_pagar(desde, hasta) -> {items: list[Transaction], total_base: int}` — todas las tx `planned` con vencimiento en la ventana `[desde, hasta]`, ordenadas por fecha, + total en `to_base` COP. Es la **cola única de confirmación** (ADR-007): incluye recurrentes manuales, pagos sueltos (`planear_pago`) y aportes de meta propuestos (P4) — los tres son tx `planned`, sin ramas especiales.

`cerrar_mes` y el registro de hooks se especifican abajo.

## Lógica y reglas clave

### Reglas firmes (heredadas, no re-litigadas)
- Solo `posted` afecta balance y reportes. `planned` **solo** vive en `por_pagar` (y, vía P5, en el reporte como alerta).
- **`confirmar_pago` es la única transición `planned` → `posted`.** Nada más cambia ese estado hacia adelante.
- `planear_pago` y el brazo manual del rollover crean tx `planned` **sin tocar balance**.
- Rollover **atómico** (commit/rollback) e **idempotente**.

**Dos relojes (ADR-020/022).** El motor separa lo que va **por fecha** de lo que va **por mes calendario**: la **materialización de recurrentes** es diaria due-driven (soporta cualquier intervalo); el **cierre de presupuesto/metas** es por mes. Ambos los corre el `scheduler` de P7 (P3 no es tool de usuario en ninguno).

### Materialización de recurrentes — `materializar_vencidos(hasta_fecha)`, due-driven (ADR-020)
**Disparo automático:** el `scheduler` lo corre **diario** con `hasta_fecha=hoy`. Materializa por **fecha**, no por mes → un sub-mensual (semanal, quincenal) genera varias occurrences en el mes, una por `due_date`.

1. Por cada `RecurringItem` con `active=True`, genera las `due_date ≤ hasta_fecha` aún no materializadas vía `fechas_vencimiento(item, ...)` (intervalo `interval_count × interval_unit` desde `start_date`, clamp fin de mes, respetando `end_date`).
2. Para cada `due_date` **que aún no tenga `RecurringOccurrence`**:
   - `mode=auto` → crea tx **`posted`** en esa `due_date` con el `amount` default (signo por `type`, `to_base` congelado), actualiza balance; occurrence `status=posted` enlazada. (Postea en cada fecha real, **no el mes entero por adelantado** → el balance no adelanta gastos.)
   - `mode=manual` → crea tx **`planned`** que vence en `due_date`, **sin tocar balance**; occurrence `status=planned` enlazada (aparece en `por_pagar`).
3. Si ya existe occurrence (cualquier status) para `(recurring_id, due_date)` → **se salta**.

**Idempotencia** por el único `(recurring_id, due_date)`: un día perdido se auto-cura en la siguiente corrida; re-ejecutar es no-op para fechas ya materializadas.

### Cierre mensual — `cerrar_mes(YYYY-MM)`, idempotente con hooks (ADR-017/022)
**Disparo automático:** el `scheduler` corre diario `ensure_mes_cerrado(mes_actual)` — el día 1 cierra el **mes calendario**, demás días no-op, día perdido se auto-cura. La idempotencia es requisito de robustez, no solo de corrección.

`cerrar_mes` cubre lo genuinamente **mensual** (ya **no** la materialización de recurrentes, que es diaria por fecha): el **rollover de sobres** y la **propuesta de aportes de meta**. No hardcodea los pasos: ejecuta una **lista registrada de hooks de rollover** en **una sola transacción**; si cualquier paso falla, rollback completo.

```
ROLLOVER_HOOKS: list[Callable[[period, session], None]] = []

def registrar_hook_rollover(fn): ROLLOVER_HOOKS.append(fn)

def cerrar_mes(period):
    with session.begin():            # atómico
        for hook in ROLLOVER_HOOKS:  # orden de registro
            hook(period, session)
```

**Hooks registrados (todos de P4):** `proponer_aportes_meta` (crea los aportes `planned` del mes, ADR-006) y, opcionalmente, el snapshot de `rollover_in` de los sobres. Cada hook es idempotente por su propia clave `(…, period)` (la propuesta / snapshot del periodo ya existe → se salta). Re-ejecutar `cerrar_mes` no duplica.

### Seam con P4 (hooks de rollover) — explícito
El cierre mensual debe **proponer aportes de metas**, pero **las metas las define P4** y el orden de build es **P3 → P4**. Para no acoplar P3 a un modelo que aún no existe, `cerrar_mes` se diseña como **lista extensible de hooks** (la materialización de recurrentes **no** pasa por aquí: es el `materializar_vencidos` diario por fecha):

- **P3** no registra ningún hook propio en `cerrar_mes` (su trabajo temporal vive en `materializar_vencidos`). Deja el seam listo y vacío.
- **P4**, cuando exista, registrará `proponer_aportes_meta` vía `registrar_hook_rollover(...)` **sin modificar `cerrar_mes`**. Aporte **flexible** (ADR-006): ese hook **no transfiere plata**; por cada `Goal` activa crea una tx **`planned`** (aporte propuesto a la cuenta de ahorro, vence fin de periodo) que cae en "Por pagar". La `GoalContribution` se registra al **confirmar** (ver seam post-confirm), no aquí. Idempotencia: P4 la define (una propuesta `planned` por `(goal_id, period)`).
- Contrato del seam: cada hook es `(period, session) -> None`, corre dentro de la misma transacción del cierre, debe ser **idempotente por sí mismo**, y un fallo en cualquier hook aborta todo el cierre.

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
- `ValidationError` — `interval_count < 1`, `interval_unit` inválido, `end_date < start_date`, `amount ≤ 0`, `currency`/`type`/`mode` inválidos, ventana de `por_pagar` invertida.
- `NotFound` — `recurring_id` / `tx_id` inexistente.
- `IllegalTransition` — `confirmar_pago`/`omitir_pago` sobre una tx que no está en `planned`.
- `MissingRate` (de P0) — `confirmar_pago`/rollover de una tx en moneda extranjera sin tasa FX para la fecha; el rollover hace rollback completo.

## Testing y criterio de "listo"

`pytest` sobre `services` + `domain` con SQLite in-memory:
- **Frecuencia genérica + fechas (ADR-020):** `fechas_vencimiento` genera las `due_date` correctas para mensual, quincenal (`2 week`), cada-3-meses, anual…; **clamp fin de mes** (recurrente día 31 → 30/28). `materializar_vencidos(hoy)` crea una occurrence por `due_date ≤ hoy`; un sub-mensual genera **varias** en el mes.
- **Idempotencia (due-driven):** `materializar_vencidos` repetido no duplica occurrences ni tx (único `(recurring_id, due_date)`); un "día perdido" se materializa en la corrida siguiente. `cerrar_mes(M)` dos/tres veces no duplica aportes propuestos; balances iguales tras la 2.ª corrida.
- **Auto vs manual:** auto deja tx `posted` **en su `due_date`** y mueve balance (no postea el mes entero por adelantado); manual deja tx `planned`, occurrence `planned`, **balance sin cambios**.
- **`planned` no afecta balance:** `planear_pago` y manual no alteran `Account.balance` ni agregados.
- **`por_pagar` por ventana:** devuelve solo las `planned` dentro de `[desde, hasta]`, ordenadas, con `total_base` correcto; excluye `posted` y `skipped`.
- **`confirmar_pago` con monto ajustado:** `planned` → `posted` con monto/fecha reales, `to_base` recalculado, balance movido; si venía de occurrence manual, la occurrence pasa a `posted`.
- **Omitir:** `omitir_recurrente` deja la occurrence de esa `due_date` en `skipped` y `materializar_vencidos` lo respeta (no recrea); `omitir_pago` cancela la tx suelta.
- **Atomicidad:** fallo a mitad de rollover (p. ej. `MissingRate`) revierte todo.
- **Seam:** un hook de prueba registrado vía `registrar_hook_rollover` corre dentro de la misma transacción y un fallo suyo aborta el cierre.

**Listo cuando** todos los tests anteriores pasan en verde, el constraint único `(recurring_id, due_date)` está aplicado, y existen las **tools MCP** de usuario (`crear_recurrente`, `listar_recurrentes`, `planear_pago`, `confirmar_pago`, `omitir_pago`, `omitir_recurrente`, `por_pagar`) y los **endpoints REST** correspondientes. **`materializar_vencidos` y `cerrar_mes` NO son tools de usuario** (ADR-017/020): los invoca el `scheduler` de P7 (diario); quedan como services (+ endpoint `/rollover` interno opcional para admin/debug). El **wire concreto** lo hacen P2 (`/recurring`, `/planned`) y P1 sobre estos services, sin lógica duplicada.

## Integración con otros sub-proyectos

- **P0 (depende):** consume models/db/session, reglas de dinero/FX/signo, `Transaction.status` y `Transaction.recurring_id`. No redefine nada de P0.
- **P1 (HTTP API):** expone routers `/recurring`, `/planned`, `/rollover` como espejo de estos services; mapea errores tipados a 4xx.
- **P2 (MCP):** expone una tool por service de usuario (mismos verbos en lenguaje natural: *"¿qué me falta por pagar esta semana?"* → `por_pagar`; *"confirma el pago de la luz"* → `confirmar_pago`). `cerrar_mes` no se expone (lo corre el scheduler, ADR-017).
- **P4 (Presupuestos + Metas):** se engancha por **dos seams** sin tocar P3: al **hook de rollover** con `proponer_aportes_meta` (crea aportes `planned`, no transfiere) y al **hook post-confirm** de `confirmar_pago` (registra la `GoalContribution` al confirmar). P4 agrega `goal_id` a `Transaction` por migración propia. Orden de build P3 → P4. El `safe_to_spend` de P4 **consume las obligaciones del mes** que expone P3 (`por_pagar` / `planned` + recurrentes) para calcular "comprometido".
- **P5 (Reportes + Importer):** consume `por_pagar` para la línea de "recurrentes / pagos pendientes" y la alerta de manuales sin confirmar en el reporte mensual.

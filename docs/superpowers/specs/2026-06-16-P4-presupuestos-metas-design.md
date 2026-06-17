# Quaestor — P4 Presupuestos + Metas (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** **P0** (domain/money/FX, db, `transferir`, transactions) y **P3** (seams de rollover y post-confirm de `cerrar_mes`/`confirmar_pago`; `por_pagar` para el "comprometido" del safe-to-spend).
**Expone vía:** **P1** (routers REST) y **P2** (tools MCP) — esos sub-proyectos cablean los services aquí definidos.
**Parte de:** `2026-06-16-quaestor-general-design.md` (diseño general). Hereda sus convenciones (ver §5 modelo, §6 metas/presupuesto, §11).

---

## Objetivo

Dar a Quaestor las capacidades de planeación que son **el diferenciador de producto** frente a Lunch Money (ADR-001/002):

1. **Presupuesto híbrido** (ADR-002/003): **sobres por categoría con rollover** (lo no gastado se arrastra) + un **safe-to-spend** global = plata que aún no asignaste a ningún sobre. El safe-to-spend integra recurrentes + planned + metas — algo que LM estructuralmente no hace.
2. **Metas de ahorro** de **monto fijo mensual**, en dos sabores: **definida** (con `target`+`deadline` → ETA y on-track/atrasado) e **indefinida** (solo acumula). Aporte **flexible** (ADR-006): el rollover lo **propone**, tú lo confirmas en "Por pagar".

El presupuesto es **lógica de lectura/cálculo** sobre transactions reales; no inventa dinero. Los aportes de meta son transferencias internas a la cuenta de ahorro, **disparadas por confirmación** (no automáticas): P4 los propone vía el hook de rollover de P3 y los registra vía el hook post-confirm de P3.

---

## Alcance

**Dentro:**
- Modelos `Budget` (con semántica de rollover), `Goal`, `GoalContribution` (+ migración). Migración que agrega `goal_id?` a `Transaction`.
- Services de presupuesto: `fijar_presupuesto`, `estado_presupuesto` (estado del sobre con rollover), **`safe_to_spend`** (número global).
- Services de metas: `crear_meta`, `aporte_meta` (aporte manual suelto), `progreso_metas`.
- Cálculo de meta **definida** (requerido mensual, on-track/atrasado, ETA) e **indefinida** (solo acumulado).
- El hook de rollover **`proponer_aportes_meta(period)`** (crea aportes `planned`, no transfiere) y el hook **post-confirm** que registra la `GoalContribution` al confirmar — ambos registrados en los seams de P3.

**Fuera:**
- Metas por % de ingreso (fuera de v1, ver general §1).
- Recurrentes y `planned`/Por-pagar (eso es P3; P4 los **consume** para "comprometido" y propone aportes sobre esa cola).
- Reportes y su markdown (P5 consume `estado_presupuesto`, `safe_to_spend` y `progreso_metas`).
- Endpoints/tools concretos: P4 define las firmas; P1/P2 las exponen.

---

## Aporte al modelo de datos

P4 agrega tres entidades (las demás ya existen en P0/P3). Migración propia; no redefine nada ajeno.

| Entidad | Campos clave |
|---|---|
| **Budget** (sobre) | `category_id` (FK Category), `year_month` (TEXT `YYYY-MM`), `amount_assigned` (centavos COP, int ≥ 0 — lo que asignas al sobre ese mes). Único por `(category_id, year_month)`. El **rollover_in es derivado** (saldo positivo del mes anterior), no se almacena; opcionalmente `cerrar_mes` lo snapshotea para rendimiento. |
| **Goal** | `name`, `target_amount?` (centavos COP, nullable), `deadline?` (date, nullable), `monthly_amount` (centavos COP, int > 0, **fijo**), `savings_account_id` (FK Account, `type=savings`), `status` ∈ `active`/`reached`/`paused`. |
| **GoalContribution** | `goal_id` (FK Goal), `date`, `amount` (centavos COP), `source` ∈ `confirmado`/`manual` (`confirmado` = aporte propuesto por rollover y confirmado en Por-pagar; `manual` = aporte suelto), `transaction_id?` (FK Transaction — la transferencia que respalda el aporte; nullable solo para aportes históricos sin tx). |
| **Transaction.goal_id?** | columna que **P4 agrega por migración** a la tabla `Transaction` de P0: enlaza una tx `planned` (aporte propuesto) a su `Goal`. Al confirmarla, el hook post-confirm de P3 lee `goal_id` y crea la `GoalContribution`. |

**Invariantes:**
- `Goal` es **definida** sii tiene `target_amount` **y** `deadline`; es **indefinida** sii no tiene ninguno. Tener solo uno → `ValidationError` al crear.
- `monthly_amount > 0` siempre (ambos tipos).
- `savings_account_id` debe apuntar a una `Account` con `type=savings` y no `archived`.
- Montos en centavos COP (los aportes ya son moneda base; las metas no manejan FX).

---

## Componentes

- `domain/rules.py` (extiende): funciones **puras** de cálculo — `estado_sobre_calc(...)` (asignado + rollover_in − gastado), `safe_to_spend_calc(...)` (cascada), `progreso_meta_calc(...)`. Reciben datos ya consultados, no tocan DB. Aquí vive la matemática de rollover, % usado, requerido mensual, ETA, on-track, y la cascada del safe-to-spend.
- `services/budgets.py`: `fijar_presupuesto`, `estado_presupuesto` (estado del sobre con rollover), **`safe_to_spend`** (consulta ingreso forecast + comprometido vía P3 + asignaciones, delega la cascada a `rules`).
- `services/goals.py`: `crear_meta`, `aporte_meta` (suelto), `progreso_metas`, el hook de rollover **`proponer_aportes_meta`** y el hook **post-confirm** `registrar_aporte_confirmado`.
- `domain/models.py` (extiende): `Budget`, `Goal`, `GoalContribution` + la columna `goal_id?` en `Transaction`.
- Migración: crea las tres tablas + índices (`Budget(category_id, year_month)` único; `GoalContribution(goal_id, date)`) y **agrega `goal_id?` a `Transaction`**.
- **Registro de seams** (en el bootstrap de P4): `registrar_hook_rollover(proponer_aportes_meta)` y `registrar_hook_post_confirm(registrar_aporte_confirmado)`.

`proponer_aportes_meta` **crea tx `planned`** (con `goal_id`), no transfiere. `registrar_aporte_confirmado` se dispara al confirmar esa tx (ya `posted`, transfer interna hecha por `confirmar_pago`) y solo **registra la `GoalContribution`**. Ningún paso escribe transactions de transfer a mano fuera de `confirmar_pago`/`transferir` de P0/P3.

---

## Interfaz pública

Firmas de `services` (lo que P1/P2/P5 consumen). Montos en centavos COP.

```python
# budgets.py
def fijar_presupuesto(session, category_id: int, year_month: str, amount_assigned: int) -> Budget:
    """Asigna (upsert) el sobre de una categoría para un mes."""

def estado_presupuesto(session, category_id: int, year_month: str) -> BudgetStatus:
    """Estado del sobre con rollover: asignado, rollover_in, gastado, disponible, pct_usado, estado."""

def safe_to_spend(session, year_month: str) -> SafeToSpend:
    """Número de cabecera (cascada) + desglose: ingreso forecast, comprometido, asignado, libre."""

# goals.py
def crear_meta(session, name: str, monthly_amount: int, savings_account_id: int,
               target_amount: int | None = None, deadline: date | None = None) -> Goal:
    """Definida si target+deadline; indefinida si ninguno; error si solo uno."""

def aporte_meta(session, goal_id: int, amount: int, date: date) -> GoalContribution:
    """Aporte suelto manual (source=manual) + transferencia interna a la cuenta de ahorro. Atómico."""

def progreso_metas(session, goal_ids: list[int] | None = None) -> list[GoalProgress]:
    """Estado de cada meta (todas las activas si goal_ids=None)."""

# hooks registrados en los seams de P3 (no se llaman directo desde P1/P2):
def proponer_aportes_meta(period: str, session) -> list[Transaction]:
    """Hook de rollover: por cada Goal activa crea una tx `planned` (aporte propuesto). Idempotente."""

def registrar_aporte_confirmado(tx, session) -> GoalContribution | None:
    """Hook post-confirm: si tx.goal_id, registra GoalContribution(source=confirmado). Si no, no-op."""
```

**DTOs de salida** (dataclasses/Pydantic, no modelos DB):

```python
BudgetStatus  = {category_id, year_month, asignado, rollover_in, gastado, disponible, pct_usado, estado}
SafeToSpend   = {year_month, ingreso_forecast, comprometido, asignado_sobres, libre, desglose_comprometido[]}
GoalProgress  = {goal_id, name, tipo("definida"|"indefinida"), monthly_amount, ahorrado,
                 # solo definida:
                 target_amount?, deadline?, requerido_mensual?, on_track?, eta?, faltante?}
```

---

## Lógica y reglas clave

### Presupuesto híbrido (ADR-002/003/005)

**Sobre por categoría (con rollover).**
- `gastado = Σ to_base(tx)` sobre transactions con `type=expense`, `status=posted`, `category_id` dado, `date` dentro de `year_month`.
- **Respeta los flags de Category:** si la categoría tiene `exclude_from_budget` **o** `exclude_from_totals`, su gasto **no** se agrega → no se presupuesta (informativo, no se bloquea).
- `rollover_in(cat, mes) = max(disponible(cat, mes−1), 0)` — lo no gastado del mes anterior se arrastra; un sobre sobregirado se absorbe en el pozo global y **resetea a 0** (ADR-005), no arrastra negativo.
- `disponible = rollover_in + amount_assigned − gastado`.
- `pct_usado = round(gastado / (rollover_in + amount_assigned) * 100)` (0 si el denominador es 0).
- `estado = "over"` si `gastado > rollover_in + amount_assigned`, si no `"under"`.
- Siempre en `to_base` (COP), nunca moneda original.

**Safe-to-spend global (cascada, ADR-003/005/014/016).** Sobres **opcionales** (A4): solo algunas categorías llevan sobre; el resto gasta directo del pozo.
```
safe_to_spend(mes) = ingreso_forecast(mes)
                   − comprometido(mes)
                   − Σ amount_assigned(mes)            # categorías CON sobre
                   − Σ gasto_no_presupuestado(mes)      # gasto posted en categorías SIN sobre
                   − Σ sobregiro(mes)                   # por sobre: max(gastado − (asignado + rollover_in), 0)
```
- `ingreso_forecast(mes)` = suma de los `RecurringItem` de `type=income` que tocan el mes (ADR-004/A2); **sin override teclado**. Ingreso atípico (prima) se registra suelto y cuenta al postear.
- `comprometido(mes)` = obligaciones del mes **contadas una sola vez** (ADR-014): recurrentes `auto` que tocan el mes + tx `planned` del mes (recurrentes manuales, pagos sueltos, aportes de meta propuestos). Una obligación que ya posteó **no se vuelve a contar**: unión por origen (occurrence de recurrente / tx), no la suma de planned+posted. → cuando algo postea, el safe-to-spend **no se mueve**.
- `Σ amount_assigned` = lo asignado a sobres este mes (la plata ya está "reclamada" exista o no gasto).
- `Σ gasto_no_presupuestado` = gasto `posted` en categorías **sin sobre** (descontando transfers y `exclude_*`). Sin esto, el pozo sobreestimaría la plata libre (A4).
- `Σ sobregiro` = lo gastado de más en un sobre por encima de `asignado + rollover_in` (ADR-005). El `rollover_in` (plata de meses previos) **no** suma al pozo de este mes y **protege** contra sobregiro falso.
- Las interacciones rollover × sobregiro × no-presupuestado las **fijan los tests** (abajo).

### Metas (monto fijo)
- **Indefinida:** `ahorrado = Σ GoalContribution.amount`. Sin `requerido_mensual`, sin `eta`, sin `on_track`. Solo total acumulado.
- **Definida:**
  - `faltante = max(target_amount − ahorrado, 0)`.
  - `meses_restantes = #meses calendario desde el mes actual hasta el mes de deadline` (≥ 1; si ya pasó el deadline → 1 para no dividir por cero).
  - `requerido_mensual = ceil(faltante / meses_restantes)`.
  - `on_track = (monthly_amount >= requerido_mensual)`. Si `False` → "atrasado".
  - `eta` = al ritmo actual (`monthly_amount`): `ceil(faltante / monthly_amount)` meses → fecha proyectada; si `faltante=0` la meta está alcanzada (ETA = hoy).
  - Si `ahorrado >= target_amount` → la meta pasa a `status=reached` (en `progreso_metas` se marca; el cambio de status persistente se hace al detectar en aporte/rollover).

### Aporte de meta = transferencia interna, **flexible** (ADR-006/007)
El aporte mensual **no es automático**. El ciclo es **propone → confirmas**, reusando la cola "Por pagar" y los seams de P3:

1. **Proponer (rollover).** `proponer_aportes_meta(period, session)` —hook de rollover— por cada `Goal` `active` crea una tx **`planned`** (`type=transfer`, `goal_id` set, **origen `Settings.default_source_account_id`** (ADR-015), destino `savings_account_id`, `amount=monthly_amount`, vence fin de periodo). **No mueve plata** (regla `planned` de P3). Cae en "Por pagar".
2. **Confirmar.** El usuario confirma vía `confirmar_pago` (P3). Como la tx es `type=transfer` planned, `confirmar_pago` **no postea un solo lado**: materializa la **transferencia interna real** vía `transferir` de P0 (par posted, atómico) hacia `savings_account_id`. El **hook post-confirm** (`registrar_aporte_confirmado`, de P4) registra entonces la `GoalContribution(source=confirmado, amount, transaction_id=transfer)`. Si el mes vino flojo, el usuario confirma con `amount` menor u **omite** (`omitir_pago`).
3. **Aporte suelto manual.** `aporte_meta(goal_id, amount, date)` crea directamente `GoalContribution(source=manual)` + transferencia, sin pasar por la cola (para aportes extra fuera del ritmo).

- El aporte (transferencia interna) **no es gasto ni ingreso** → fuera de todos los totales/reportes (general §5).
- **Atómico:** transferencia + `GoalContribution` se crean juntas o ninguna (la atomicidad la garantiza la transacción de `confirmar_pago` / `aporte_meta`).
- **Idempotencia de la propuesta:** `proponer_aportes_meta` no crea una segunda propuesta `planned` si ya existe una para `(goal_id, period)`. Re-ejecutar `cerrar_mes` no duplica propuestas. Metas `paused`/`reached` se saltan.
- Tras un aporte confirmado, si una meta definida alcanza su `target` → `status=reached`.

> **Nota de integración P3↔P4:** que `confirmar_pago` materialice un `planned` de `type=transfer` como transferencia real es una **capacidad genérica de P3** (no específica de metas): P3 soporta transferencias planeadas y delega el efecto monetario; P4 solo aporta el `goal_id` y el hook que registra la `GoalContribution`. P3 sigue **ignorando qué es una meta**.

---

## Errores

Errores tipados de `domain` (general §11). API (P1) → 4xx; MCP (P2) → texto estructurado.

- `ValidationError`: `monthly_amount <= 0`; meta con solo `target` o solo `deadline`; `amount_assigned < 0`; `year_month` mal formado (no `YYYY-MM`).
- `ValidationError`: `savings_account_id` no existe, no es `type=savings`, o está `archived`.
- `NotFound`: `category_id` / `goal_id` inexistente.
- Aporte confirmado / suelto **atómicos**: si la transferencia falla (cuenta inválida según P0), se revierte la `GoalContribution` (rollback dentro de `confirmar_pago` / `aporte_meta`).
- Proponer aportes en rollover **no mueve plata** → no puede fallar por fondos; solo crea `planned`. Falla solo por datos inválidos (cuenta de ahorro archivada, etc.) y aborta el cierre (atomicidad de `cerrar_mes`, P3).
- `MissingRate` no aplica: aportes y presupuestos son COP base, sin FX.

---

## Testing y criterio de "listo"

`pytest` sobre `domain` + `services` con SQLite in-memory (general §11). **Listo** cuando pasan:

- **`estado_presupuesto` (sobre con rollover):** suma solo `expense`+`posted` del mes/categoría; ignora `planned`, transfers, otros meses/categorías; **respeta `exclude_from_budget`/`exclude_from_totals`**; `rollover_in = max(disponible mes anterior, 0)` (positivo arrastra, negativo resetea, ADR-005); `disponible`, `pct_usado`, `over`/`under` correctos; denominador 0 no divide por cero.
- **`safe_to_spend` (cascada):** `libre = ingreso_forecast − comprometido − asignado − gasto_no_presupuestado − sobregiro`; ingreso = suma de recurrentes `income` del mes (sin override, A2). **Sobres opcionales (A4):** gasto en categoría **sin sobre** reduce el pozo; gasto en categoría **con sobre** ya está reclamado por la asignación (no resta doble). **Double-count guard (ADR-014):** una obligación contada una sola vez esté `planned` o `posted` → confirmar un `planned` (o postear un recurrente auto) **no cambia** el safe-to-spend. **Sobregiro (ADR-005):** `max(gastado−(asignado+rollover_in),0)` reduce el pozo; `rollover_in` protege contra sobregiro falso.
- **Meta definida:** `requerido_mensual = ceil(faltante/meses_restantes)`; `on_track` true/false según `monthly_amount` vs requerido; `eta` proyectada al ritmo actual; deadline vencido no rompe; `ahorrado >= target` → `reached`.
- **Meta indefinida:** solo `ahorrado` acumulado; sin `requerido_mensual`/`eta`/`on_track`.
- **`aporte_meta` (suelto):** crea `GoalContribution(source=manual)` + transferencia interna; no aparece como gasto/ingreso; atómico.
- **Proponer + confirmar (flexible, ADR-006):** `proponer_aportes_meta(period)` crea por cada meta activa una tx **`planned`** (`goal_id`, `monthly_amount`, destino ahorro), **sin mover balance**; saltea `paused`/`reached`; **idempotente** (re-ejecutar no duplica la propuesta). Al **confirmar** esa tx: se materializa la transferencia real y el hook post-confirm registra `GoalContribution(source=confirmado)`; confirmar con monto menor ajusta el aporte; **omitir** no aporta. Tras confirmar, meta definida que alcanza target → `reached`.
- **Wire:** P1 expone los services en `/budgets` (incl. `/budgets/safe-to-spend`) y `/goals`; P2 los expone como tools MCP (incl. "¿cuánto me queda libre?"). (Verificación de cableado vive en P1/P2; P4 entrega services estables.)

---

## Integración con otros sub-proyectos

- **P0 (Core):** consume `transferir` (aportes = transferencias internas), el modelo `Transaction`/`Account`/`Category`, `to_base`, y el patrón atómico. No reimplementa transferencias. Agrega `goal_id?` a `Transaction` por migración.
- **P3 (Motor temporal):** P4 se engancha por **dos seams** sin tocar `cerrar_mes`/`confirmar_pago`: registra `proponer_aportes_meta` en el hook de rollover (crea aportes `planned`) y `registrar_aporte_confirmado` en el hook post-confirm (registra `GoalContribution`). Además **consume** las obligaciones del mes (`por_pagar`/planned + recurrentes) para el "comprometido" del `safe_to_spend`. Idempotencia de la propuesta por `(goal_id, period)`.
- **P1 (HTTP API):** routers `/budgets` (`fijar_presupuesto`, `estado_presupuesto`, **`safe_to_spend`** en `/budgets/safe-to-spend`) y `/goals` (`crear_meta`, `aporte_meta`, `progreso_metas`) sobre estos services.
- **P2 (MCP):** tools espejo (mismos verbos) para que el agente fije presupuesto, consulte estado, cree meta, aporte y pregunte por el avance en lenguaje natural.
- **P5 (Reportes):** consume `estado_presupuesto` (sobres con rollover), **`safe_to_spend`** (número de cabecera) y `progreso_metas` (acumulado + ETA de definidas) para el reporte mensual. P4 no genera markdown.
- **P6 (Frontend):** el dashboard v1 (general §8, ADR-008) muestra `safe_to_spend` + el widget "Por pagar"; las rutas `/budgets` y `/goals` quedan en backlog y pegan a los endpoints de P1 cuando aterricen.

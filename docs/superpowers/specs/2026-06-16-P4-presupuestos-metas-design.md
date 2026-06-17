# Quaestor — P4 Presupuestos + Metas (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** **P0** (domain/money/FX, db, `transferir`, transactions) y **P3** (hook de rollover: `cerrar_mes`).
**Expone vía:** **P1** (routers REST) y **P2** (tools MCP) — esos sub-proyectos cablean los services aquí definidos.
**Parte de:** `2026-06-16-quaestor-general-design.md` (diseño general). Hereda sus convenciones (ver §5 modelo, §6 metas/presupuesto, §11).

---

## Objetivo

Dar a Quaestor dos capacidades de planeación sobre los datos que ya registra P0:

1. **Presupuestos** por categoría y mes: cuánto pienso gastar vs cuánto llevo gastado (`posted`).
2. **Metas de ahorro** de **monto fijo mensual**, en dos sabores: **definida** (con `target`+`deadline` → ETA y on-track/atrasado) e **indefinida** (solo acumula).

Ambos son **lógica de lectura/cálculo** sobre transactions reales; no inventan dinero. El único efecto de escritura es el aporte automático de meta (una transferencia interna a la cuenta de ahorro), que P4 **enchufa al rollover de P3** pero implementa aquí.

---

## Alcance

**Dentro:**
- Modelos `Budget`, `Goal`, `GoalContribution` (+ migración).
- Services de presupuesto: `fijar_presupuesto`, `estado_presupuesto`.
- Services de metas: `crear_meta`, `aporte_meta` (manual), `progreso_metas`.
- Cálculo de meta **definida** (requerido mensual, on-track/atrasado, ETA) e **indefinida** (solo acumulado).
- El paso de rollover `aplicar_aportes_meta(period)` que P3 invoca dentro de `cerrar_mes`.

**Fuera:**
- Metas por % de ingreso (fuera de v1, ver general §1).
- Rollover de presupuesto no gastado al mes siguiente (no en v1).
- Recurrentes y `planned`/Por-pagar (eso es P3).
- Reportes y su markdown (P5 consume `estado_presupuesto` y `progreso_metas`).
- Endpoints/tools concretos: P4 define las firmas; P1/P2 las exponen.

---

## Aporte al modelo de datos

P4 agrega tres entidades (las demás ya existen en P0/P3). Migración propia; no redefine nada ajeno.

| Entidad | Campos clave |
|---|---|
| **Budget** | `category_id` (FK Category), `year_month` (TEXT `YYYY-MM`), `amount_base` (centavos COP, int ≥ 0). Único por `(category_id, year_month)`. |
| **Goal** | `name`, `target_amount?` (centavos COP, nullable), `deadline?` (date, nullable), `monthly_amount` (centavos COP, int > 0, **fijo**), `savings_account_id` (FK Account, `type=savings`), `status` ∈ `active`/`reached`/`paused`. |
| **GoalContribution** | `goal_id` (FK Goal), `date`, `amount` (centavos COP), `source` ∈ `auto`/`manual`, `transaction_id?` (FK Transaction — la transferencia que respalda el aporte; nullable solo para aportes históricos sin tx). |

**Invariantes:**
- `Goal` es **definida** sii tiene `target_amount` **y** `deadline`; es **indefinida** sii no tiene ninguno. Tener solo uno → `ValidationError` al crear.
- `monthly_amount > 0` siempre (ambos tipos).
- `savings_account_id` debe apuntar a una `Account` con `type=savings` y no `archived`.
- Montos en centavos COP (los aportes ya son moneda base; las metas no manejan FX).

---

## Componentes

- `domain/rules.py` (extiende): funciones **puras** de cálculo — `estado_presupuesto_calc(...)`, `progreso_meta_calc(...)`. Reciben datos ya consultados, no tocan DB. Aquí vive la matemática de % usado, requerido mensual, ETA, on-track.
- `services/budgets.py`: `fijar_presupuesto`, `estado_presupuesto`. Consulta transactions y delega el cálculo a `rules`.
- `services/goals.py`: `crear_meta`, `aporte_meta`, `progreso_metas`, y el paso de rollover `aplicar_aportes_meta`.
- `domain/models.py` (extiende): los tres SQLModel nuevos.
- Migración: crea las tres tablas + índices (`Budget(category_id, year_month)` único; `GoalContribution(goal_id, date)`).

`aplicar_aportes_meta` **reusa `transferir` de P0** para crear la transferencia interna; no escribe transactions a mano.

---

## Interfaz pública

Firmas de `services` (lo que P1/P2/P5 consumen). Montos en centavos COP.

```python
# budgets.py
def fijar_presupuesto(session, category_id: int, year_month: str, amount_base: int) -> Budget:
    """Crea o actualiza (upsert) el presupuesto de una categoría para un mes."""

def estado_presupuesto(session, category_id: int, year_month: str) -> BudgetStatus:
    """BudgetStatus: presupuestado, gastado, restante, pct_usado, estado(under/over)."""

# goals.py
def crear_meta(session, name: str, monthly_amount: int, savings_account_id: int,
               target_amount: int | None = None, deadline: date | None = None) -> Goal:
    """Definida si target+deadline; indefinida si ninguno; error si solo uno."""

def aporte_meta(session, goal_id: int, amount: int, date: date,
                source: str = "manual") -> GoalContribution:
    """Aporte (default manual) + transferencia interna a la cuenta de ahorro. Atómico."""

def progreso_metas(session, goal_ids: list[int] | None = None) -> list[GoalProgress]:
    """Estado de cada meta (todas las activas si goal_ids=None)."""

def aplicar_aportes_meta(session, period: str) -> list[GoalContribution]:
    """Paso de rollover: aporte auto por cada Goal activa. Idempotente. Lo llama P3."""
```

**DTOs de salida** (dataclasses/Pydantic, no modelos DB):

```python
BudgetStatus  = {category_id, year_month, presupuestado, gastado, restante, pct_usado, estado}
GoalProgress  = {goal_id, name, tipo("definida"|"indefinida"), monthly_amount, ahorrado,
                 # solo definida:
                 target_amount?, deadline?, requerido_mensual?, on_track?, eta?, faltante?}
```

---

## Lógica y reglas clave

### Presupuesto
- `gastado = Σ to_base(tx)` sobre transactions con `type=expense`, `status=posted`, `category_id` dado, `date` dentro de `year_month`.
- **Respeta los flags de Category:** si la categoría tiene `exclude_from_budget` **o** `exclude_from_totals`, su gasto **no** se agrega → `gastado = 0` y el estado es informativo (no tiene sentido presupuestar una categoría excluida; se documenta, no se bloquea).
- `restante = presupuestado − gastado`; `pct_usado = round(gastado / presupuestado * 100)` (0 si `presupuestado=0`).
- `estado = "over"` si `gastado > presupuestado`, si no `"under"`.
- Siempre en `to_base` (COP), nunca moneda original.

### Metas (monto fijo)
- **Indefinida:** `ahorrado = Σ GoalContribution.amount`. Sin `requerido_mensual`, sin `eta`, sin `on_track`. Solo total acumulado.
- **Definida:**
  - `faltante = max(target_amount − ahorrado, 0)`.
  - `meses_restantes = #meses calendario desde el mes actual hasta el mes de deadline` (≥ 1; si ya pasó el deadline → 1 para no dividir por cero).
  - `requerido_mensual = ceil(faltante / meses_restantes)`.
  - `on_track = (monthly_amount >= requerido_mensual)`. Si `False` → "atrasado".
  - `eta` = al ritmo actual (`monthly_amount`): `ceil(faltante / monthly_amount)` meses → fecha proyectada; si `faltante=0` la meta está alcanzada (ETA = hoy).
  - Si `ahorrado >= target_amount` → la meta pasa a `status=reached` (en `progreso_metas` se marca; el cambio de status persistente se hace al detectar en aporte/rollover).

### Aporte de meta = transferencia interna
- Todo aporte (auto o manual) crea **una `GoalContribution`** + **una transferencia** (`transferir` de P0) desde una cuenta corriente hacia `savings_account_id`. **No es gasto ni ingreso**; queda fuera de todos los totales/reportes de gasto/ingreso (regla de transferencias internas, general §5).
- `GoalContribution.transaction_id` apunta a la transferencia creada (su `transfer_group_id` / pata, según contrato de P0).
- Atómico: contribución + transferencia se crean juntas o ninguna.

### Hook de rollover (`aplicar_aportes_meta`, enganchado a `cerrar_mes` de P3)
- **P3 define** el orquestador `cerrar_mes(period)` (general §6) y **llama a este paso** después de procesar recurrentes. P4 **registra/implementa** el paso; P3 lo invoca. Acuerdo de integración: P3 expone una lista ordenada de pasos de cierre y P4 aporta `aplicar_aportes_meta`; o bien `cerrar_mes` lo llama directo. Cualquiera de las dos, el orden es **recurrentes → aportes de meta**.
- Comportamiento por `period` (`YYYY-MM`): por cada `Goal` con `status=active`, crea **una** `GoalContribution(source=auto, amount=monthly_amount, date=último día del period)` + su transferencia.
- **Idempotencia:** antes de aportar, verifica si ya existe una `GoalContribution(goal_id, source=auto)` en ese `period`. Si existe, **no** duplica (igual que las occurrences de recurrentes marcan idempotencia en P3). Re-ejecutar `cerrar_mes` no crea aportes dobles.
- Metas `paused`/`reached` se saltan. Tras el aporte, si una meta definida alcanza su `target` → se actualiza a `status=reached`.

---

## Errores

Errores tipados de `domain` (general §11). API (P1) → 4xx; MCP (P2) → texto estructurado.

- `ValidationError`: `monthly_amount <= 0`; meta con solo `target` o solo `deadline`; `amount_base < 0`; `year_month` mal formado (no `YYYY-MM`).
- `ValidationError`: `savings_account_id` no existe, no es `type=savings`, o está `archived`.
- `NotFound`: `category_id` / `goal_id` inexistente.
- Aporte/rollover **atómicos**: si la transferencia falla (p. ej. fondos/cuenta inválida según P0), se revierte la `GoalContribution` (rollback).
- `MissingRate` no aplica: aportes y presupuestos son COP base, sin FX.

---

## Testing y criterio de "listo"

`pytest` sobre `domain` + `services` con SQLite in-memory (general §11). **Listo** cuando pasan:

- **`estado_presupuesto`:** suma solo `expense`+`posted` del mes y categoría correctos; ignora `planned`, transfers, otros meses/categorías; **respeta `exclude_from_budget` y `exclude_from_totals`** (gasto excluido no cuenta); `pct_usado`, `restante`, `over`/`under` correctos; `presupuestado=0` no divide por cero.
- **Meta definida:** `requerido_mensual = ceil(faltante/meses_restantes)`; `on_track` true/false según `monthly_amount` vs requerido; `eta` proyectada al ritmo actual; deadline vencido no rompe; `ahorrado >= target` → `reached`.
- **Meta indefinida:** solo `ahorrado` acumulado; sin `requerido_mensual`/`eta`/`on_track`.
- **`aporte_meta` (manual):** crea contribución + transferencia interna a la cuenta de ahorro; no aparece como gasto/ingreso; atómico.
- **Hook de rollover:** `aplicar_aportes_meta(period)` crea, por cada meta activa, contribución (`source=auto`, `monthly_amount`) + transferencia **correctas**; saltea `paused`/`reached`; **idempotente** (re-ejecutar no duplica); el monto y la cuenta destino son los esperados.
- **Wire:** P1 expone los services en `/budgets` y `/goals`; P2 los expone como tools MCP. (Verificación de cableado vive en P1/P2; P4 entrega services estables.)

---

## Integración con otros sub-proyectos

- **P0 (Core):** consume `transferir` (aportes = transferencias internas), el modelo `Transaction`/`Account`/`Category`, `to_base`, y el patrón atómico. No reimplementa transferencias.
- **P3 (Motor temporal):** `cerrar_mes` **invoca** `aplicar_aportes_meta(period)` tras los recurrentes. P3 fija el orden y la atomicidad/idempotencia del cierre global; P4 aporta el paso de metas. Contrato: P4 garantiza que el paso es idempotente por `period`.
- **P1 (HTTP API):** routers `/budgets` (`fijar_presupuesto`, `estado_presupuesto`) y `/goals` (`crear_meta`, `aporte_meta`, `progreso_metas`) sobre estos services.
- **P2 (MCP):** tools espejo (mismos verbos) para que el agente fije presupuesto, consulte estado, cree meta, aporte y pregunte por el avance en lenguaje natural.
- **P5 (Reportes):** consume `estado_presupuesto` (presupuesto vs real) y `progreso_metas` (acumulado + ETA de definidas) para el reporte mensual. P4 no genera markdown.
- **P6 (Frontend):** las rutas `/budgets` y `/goals` (general §8) pegan a los endpoints de P1.

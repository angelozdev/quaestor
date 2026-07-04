# Default transaction listing order — design

**Date:** 2026-06-28
**Status:** design (pending approval)
**Amends:** `docs/adr/0021-default-transaction-listing-order-created-at-desc.md`
**Refines:** the original proposed option (single service default flip) into a hybrid that adds a `sort`/`order` escape hatch for callers whose ordering semantics differ from the listing default.

## Context

`/transactions` es la superficie principal para revisar actividad reciente, y el modelo mental del usuario es "lo que acabo de registrar está arriba". Hoy `services.transactions.list_transactions` ordena por `date` ASC: una transacción con `date` 10-jun registrada hoy (28-jun) queda debajo de cargos del 27-jun, aunque sea el write más reciente al ledger. El mismo default lo heredan el tool MCP `list_transactions` y el endpoint REST, así que la inconsistencia es transversal.

El ADR-0021 propuesto original sugería cambiar el default del servicio a `created_at DESC` sin más. Pero al revisar contra el código se descubre que **`services.planned.to_pay` también llama a `list_transactions`** para alimentar la cola de confirmación `/to-pay` y la sección `pending` del reporte mensual. Para items `planned`, `date` es la fecha de vencimiento — el orden cronológico ahí no es accidental, es funcional.

## Objetivo

- El default de `/transactions` (REST) y de la tool MCP `list_transactions` debe mostrar primero lo más recién creado, independientemente de la fecha lógica de la transacción.
- `planned.to_pay` debe seguir devolviendo los pagos pendientes ordenados por fecha de vencimiento ascendente (lo próximo a vencer primero).
- El cambio no debe romper ningún test existente.

## No-objetivos

- Controles de sort en la UI de `/transactions` (YAGNI; el default nuevo ya da la UX correcta, los kwargs quedan listos para uso futuro).
- Índice en `created_at` (defer; tamaño actual lo hace innecesario; queda como follow-up en el ADR).
- Paginación / cursor-based traversal.
- Cualquier cambio a `Transaction` schema o migraciones Alembic.

## Decisión

Combinar la opción 1 (cambiar el default del servicio) con la opción 2 (parámetro `sort`/`order` opcional) del ADR-0021:

- `services.transactions.list_transactions` gana dos kwargs keyword-only opcionales: `sort` ∈ `{"date", "created_at"}` y `order` ∈ `{"asc", "desc"}`.
- **Default**: `sort="created_at"`, `order="desc"`. La query ordena `created_at <order>, id <order>` (el `id` como tiebreaker determinístico).
- **`planned.to_pay` pasa explícitamente** `sort="date", order="asc"` — candado intencional que cualquier reviewer ve en el call site.
- REST `GET /transactions` y MCP `list_transactions` exponen los mismos kwargs. Pydantic los valida en el límite (Literal types) → fail-fast antes de tocar el servicio.

## Diseño (patrones aplicados)

| Patrón | Dónde | SOLID |
|---|---|---|
| Value Object | `SortSpec` (dataclass frozen + slots) | SRP — la política de orden vive aparte de la query |
| Registry / Lookup table | `_TRANSACTION_SORTABLE: dict[str, ColumnElement]` | OCP — añadir campo ordenable = 1 línea |
| Parse, don't validate | `Literal["date","created_at"]` validado por Pydantic | — fail-fast en el límite |
| Keyword-only args | `*, sort, order` | ISP — no se acoplan posicionalmente |
| Dependency injection (de spec) | `SortSpec.resolve(sortable, tiebreaker)` | DIP — el spec no conoce el modelo concreto |
| Fail-fast | `ValidationError` en `resolve()` con allowed list | — defensivo en el límite interno |

### Nuevo módulo `backend/src/quaestor/domain/sort.py`

```python
"""Sort policy: immutable spec + per-service column registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import ColumnElement

from .errors import ValidationError

SortField = Literal["date", "created_at"]
Order = Literal["asc", "desc"]

# Registry shape — each service instantiates its own mapping.
SortableColumns = dict[str, ColumnElement]


@dataclass(frozen=True, slots=True)
class SortSpec:
    """Immutable (field, order) pair. Resolves to (primary, tiebreaker)."""
    field: SortField
    order: Order

    def resolve(
        self,
        sortable: SortableColumns,
        tiebreaker: ColumnElement,
    ) -> tuple[ColumnElement, ColumnElement]:
        col = sortable.get(self.field)
        if col is None:
            raise ValidationError(
                f"unknown sort field: {self.field!r}; allowed: {sorted(sortable)}"
            )
        desc = self.order == "desc"
        return (col.desc() if desc else col.asc(),
                tiebreaker.desc() if desc else tiebreaker.asc())
```

### Servicio `backend/src/quaestor/services/transactions.py`

```python
from ..domain.sort import SortField, Order, SortSpec, SortableColumns

_TRANSACTION_SORTABLE: SortableColumns = {
    "date":       Transaction.date,
    "created_at": Transaction.created_at,
}

def list_transactions(
    session: Session,
    account_id: int | None = None,
    category_id: int | None = None,
    tag: str | None = None,
    type=None,
    status=None,
    date_from: Date | None = None,
    date_to: Date | None = None,
    *,
    sort: SortField = "created_at",
    order: Order = "desc",
) -> list[Transaction]:
    """... existing docstring ...
    Default order is `created_at DESC, id DESC` — 'what I just entered is on top'.
    Pass `sort="date", order="asc"` for chronological-by-due-date (used by to_pay).
    """
    stmt = select(Transaction)
    # ... filtros existentes sin cambios ...
    if tag is not None:
        stmt = stmt.join(...).where(...)

    spec = SortSpec(field=sort, order=order)
    primary, secondary = spec.resolve(_TRANSACTION_SORTABLE, Transaction.id)
    return list(session.exec(stmt.order_by(primary, secondary)).all())
```

### Servicio `backend/src/quaestor/services/planned.py`

```python
items = _tx.list_transactions(
    session, status="planned", date_from=since, date_to=until,
    sort="date", order="asc",   # candado: por fecha de vencimiento
)
```

### REST `backend/src/quaestor/api/routers/transactions.py`

```python
from ...domain.sort import SortField, Order

@router.get("", response_model=list[TransactionOut])
def list_transactions(
    date_from: Date | None = None,
    # ... otros params existentes ...
    sort: SortField = "created_at",
    order: Order = "desc",
    session: Session = Depends(get_session),
):
    return transactions.list_transactions(
        session, account_id=..., ..., sort=sort, order=order,
    )
```

### MCP `backend/src/quaestor/mcp/tools/core.py`

```python
class ListTransactionsInput(BaseModel):
    date_from: Date | None = None
    # ... campos existentes ...
    sort: Literal["date", "created_at"] = Field(
        default="created_at", description="Primary sort field"
    )
    order: Literal["asc", "desc"] = Field(
        default="desc", description="Sort direction"
    )
```

## Tests (TDD)

| Test | Ubicación | Contrato |
|---|---|---|
| `test_sort_spec_resolves_primary_and_tiebreaker` | `backend/tests/domain/test_sort.py` | `SortSpec.resolve` con field+order conocidos devuelve primary y tiebreaker en la dirección correcta |
| `test_sort_spec_rejects_unknown_field` | mismo | field desconocido → `ValidationError` con mensaje listando los allowed |
| `test_sort_spec_is_frozen` | mismo | `SortSpec(field="x", order="y")` no es mutable |
| `test_list_transactions_default_orders_by_created_at_desc` | `backend/tests/services/test_transactions.py` | Insertar 3 txs con fechas invertidas; el default devuelve la más recién creada primero |
| `test_list_transactions_sort_date_asc_orders_chronologically` | mismo | `sort="date", order="asc"` → txs en orden de fecha asc |
| `test_list_transactions_sort_date_desc_orders_reverse_chronologically` | mismo | `sort="date", order="desc"` → txs en orden de fecha desc |
| `test_to_pay_orders_by_due_date_asc` | `backend/tests/services/test_planned.py` | Candado: 2 planned con due_dates invertidas; `to_pay` devuelve la próxima a vencer primero |
| `test_list_endpoint_default_order` | `backend/tests/api/test_transactions.py` | `GET /transactions` sin params devuelve newest-created-first |
| `test_list_endpoint_sort_query_param` | mismo | `?sort=date&order=asc` devuelve chronological |
| `test_list_endpoint_invalid_sort_returns_422` | mismo | `?sort=amount` → 422 con mensaje claro |
| `test_mcp_list_transactions_default_order` | `backend/tests/mcp/test_core_reads.py` | Tool con input vacío → output refleja newest-created-first |
| `test_mcp_list_transactions_explicit_sort_date_asc` | mismo | Tool con `sort="date", order="asc"` → chronological |

## Enmiendas al ADR-0021

- **Status**: se mantiene `proposed` durante la implementación. Pasa a `accepted` tras merge.
- **Decision outcome**: cambiar la opción elegida de "1" a "1 + 2 combinado", redactado para indicar que el default del servicio cambia y se añade un escape hatch `sort`/`order` para callers cuyo significado del orden sea distinto al del listado general.
- **Consequences**:
  - Añadir bullet sobre el carve-out de `planned.to_pay` (candado explícito).
  - Añadir follow-up del índice `created_at` cuando el ledger crezca.
  - Suavizar el bullet de chat narration ("el LLM recibe el tool output como data y ordena la narrativa; impacto neutro-a-positivo, no regresión visible").

## Riesgos y follow-ups

- **Compatibilidad con consumers REST no testeados**: cualquier script externo que itere `GET /transactions` verá el nuevo orden. Mitigación: los scripts que asuman `date ASC` y paginen pueden romperse; documentar en CHANGELOG / release notes del deploy.
- **Índice `created_at`**: defer. Cuando la tabla supere ~10⁴ filas, crear migration con `CREATE INDEX ix_transaction_created_at ON transaction(created_at DESC, id DESC)`.
- **Tiebreaker `id`**: válido bajo SQLite autoincrement con un solo writer. Si en el futuro se migra a Postgres con sequences con gaps, reevaluar (probablemente innecesario porque `id` sigue siendo monotónico en practice).

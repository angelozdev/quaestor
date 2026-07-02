# Outstanding Queue — `to_pay` siempre incluye vencidos

**Date:** 2026-07-02
**Status:** design (pending approval)
**ADR:** `docs/adr/0023-outstanding-queue-buckets.md` (proposed, lives next to this spec)
**Refines:** el contrato de `services.planned.to_pay` para que el bucket de items vencidos sea invariante, sin importar la ventana `[since, until]`.

## Contexto

El usuario reportó el 2026-07-02 que cuatro pagos planeados con vencimiento 2026-06-27 y 2026-06-28 (Tigo, Claro, Uber, CC San Diego) habían desaparecido de la cola "Por pagar" del dashboard y de la página `/to-pay`. Confirmado por queries directos a la API:

- `GET /api/planned/to-pay?since=2026-06-29&until=2026-07-05` (la ventana que usa el widget "Esta semana" en lunes 2026-06-29) → **4 items**, ninguno de los 4 reportados.
- `GET /api/planned/to-pay?since=2026-06-15&until=2026-07-31` → **9 items**, sí incluye los 4 reportados (más EPM del 2026-06-22).

**Causa raíz:** `services.planned.to_pay` filtra con `date_from=since, date_to=until`. El widget y la página calculan `since = startOfWeek(now, Mon)` o `since = startOfMonth(now)`. Hoy es miércoles 2026-07-02; por tanto `since` = lunes 2026-06-29 (semana) o miércoles 2026-07-01 (mes). Todo item con `date < since` queda excluido del response. El contrato de visibilidad está roto: un item "vencido" (date < today) no se muestra en la cola hasta que se confirma, se omite, o la ventana se ensancha.

Esto NO es regresión de ADR-0021 (ese cambió el orden, no el filtro). Es un bug preexistente que el usuario descubre ahora que la fecha cruzó el 2026-07-01. Antes de julio, los vencidos caían dentro de la ventana mensual (junio); a partir de julio, caen fuera.

## Contrato del usuario (invariante)

> "Lo que está vencido debe aparecer SIEMPRE hasta que se resuelva. No se puede desaparecer de una semana a otra o de un mes a otro."

Un item `planned` con `date < today` debe estar visible en la cola de confirmación sin importar el rango `[since, until]` que el caller pase, hasta que el usuario lo confirme (`confirm_payment`) o lo omita (`skip_payment`).

## Decisión

Introducir un value object `OutstandingQueue` que se compone de dos buckets mutuamente excluyentes — `overdue` y `upcoming` — y modificar el servicio `to_pay` para producirlo. El caller decide si quiere vista operativa (overdue + upcoming) o retrospectiva (solo upcoming) vía el kwarg `include_prior_overdue`.

- **`overdue`**: `status=planned AND date < today AND date <= until` (ordenado por date ASC).
- **`upcoming`**: `status=planned AND date in [max(since, today), until]` (ordenado por date ASC).
- Los dos buckets nunca se solapan (las dos condiciones de fecha son disjuntas por construcción).
- `total_base` = suma de `to_base` de ambos buckets, precomputada en el VO.

### SOLID check

| Principio | Cómo se cumple |
|---|---|
| **SRP** | `to_pay` produce un `OutstandingQueue`; el VO solo sabe "outstanding queue"; cada caller (widget, page, reporte) decide qué hacer con los buckets. |
| **OCP** | Añadir un tercer bucket (ej. `forecast` para items > until) es aditivo: un campo nuevo en el VO, un branch nuevo en `to_pay`, cero cambios en callers existentes. |
| **LSP** | N/A — no hay herencia. |
| **ISP** | Los callers leen solo los campos que necesitan. El reporte mensual solo lee `queue.upcoming`; el widget lee ambos. |
| **DIP** | El REST router y el MCP tool retornan el VO (no un dict sin tipo). |

## Diseño

### Capa de Dominio — `backend/src/quaestor/domain/planned.py` (nuevo)

```python
"""Outstanding-queue value object for the planned-payments domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .models import Transaction


@dataclass(frozen=True, slots=True)
class OutstandingQueue:
    """The user's outstanding obligations: past-due + upcoming.

    `overdue` and `upcoming` are mutually exclusive — a planned tx is
    classified by whether its `date` is strictly before today (overdue) or
    in [since, until] (upcoming). The two lists together cover "what the
    user owes or is about to owe" through `until`. `total_base` is the
    COP-cents sum of both, precomputed at construction.
    """

    overdue: list[Transaction] = field(default_factory=list)
    upcoming: list[Transaction] = field(default_factory=list)

    @property
    def total_base(self) -> int:
        return sum(t.to_base for t in self.overdue) + sum(
            t.to_base for t in self.upcoming
        )

    @property
    def is_empty(self) -> bool:
        return not self.overdue and not self.upcoming

    def all_items(self) -> list[Transaction]:
        """Flat list, overdue first then upcoming, each in date-ascending order."""
        return [*self.overdue, *self.upcoming]

    @classmethod
    def from_lists(
        cls, overdue: Iterable[Transaction], upcoming: Iterable[Transaction]
    ) -> "OutstandingQueue":
        """Construct with eager evaluation; both iterables are consumed once."""
        return cls(overdue=list(overdue), upcoming=list(upcoming))
```

### Capa de Servicio — `backend/src/quaestor/services/planned.py` (modificación)

```python
def to_pay(
    session: Session,
    since: Date,
    until: Date,
    *,
    include_prior_overdue: bool = True,
) -> OutstandingQueue:
    """Build the user's outstanding queue for the [since, until] window.

    Behavior:
    - `upcoming` = planned txs with `date in [max(since, today), until]`,
      ordered by date ASC.
    - `overdue`  = planned txs with `date < today` AND `date <= until`,
      ordered by date ASC, iff `include_prior_overdue` is True. Otherwise
      the bucket is empty (retrospective view: monthly report, where
      items overdue from prior months belong to their own retrospective,
      not this month's).

    Both buckets are mutually exclusive by construction (the date ranges
    don't overlap). The union covers all planned txs the user might need
    to act on through `until`.

    Args:
        session: DB session.
        since: Lower bound for the upcoming bucket (inclusive).
        until: Hard cap for both buckets (inclusive). Items with
            date > until are excluded even from the overdue bucket.
        include_prior_overdue: When True (default), the overdue bucket
            contains ALL planned txs with `date < today` whose `date <=
            until` (so we never surface items that the caller has
            explicitly scoped out by `until`). When False, the overdue
            bucket is empty — the caller only wants items in [since, until].

    Raises:
        ValidationError: `since > until` (inverted window).
    """
    if since > until:
        raise ValidationError("to_pay window is inverted (since > until)")

    today = date.today()  # local date for "is it overdue"

    # Overdue bucket: items past due that the user hasn't actioned yet.
    # Constrained by `until` so callers that scope to a window don't get
    # items from a future retrospective they didn't ask for.
    if include_prior_overdue:
        # list_transactions filter is `date <= date_to`; we want strictly
        # < today, so pass min(today, until) and trim the day-of rows.
        overdue_items = _tx.list_transactions(
            session,
            status="planned",
            date_to=min(today, until),
            sort="date",
            order="asc",
        )
        overdue_items = [t for t in overdue_items if t.date < today]
    else:
        overdue_items = []

    # Upcoming bucket: planned txs from max(since, today) through until.
    # Skip the query if the floor is past the cap (only happens when
    # include_prior_overdue=False and the entire window is historical).
    upcoming_since = max(since, today)
    if upcoming_since > until:
        upcoming_items: list[Transaction] = []
    else:
        upcoming_items = _tx.list_transactions(
            session,
            status="planned",
            date_from=upcoming_since,
            date_to=until,
            sort="date",
            order="asc",
        )

    return OutstandingQueue.from_lists(overdue_items, upcoming_items)
```

### Migración del Monthly Report — `backend/src/quaestor/services/reports.py` (línea 201)

```python
def _pending_lines(session: Session, start: Date, end: Date) -> list[str]:
    """Alert lines for unconfirmed (planned) entries in the month.

    Retrospective view: pass `include_prior_overdue=False` so the report
    for 2026-07 doesn't show items overdue from June. The retrospective
    only counts what was planned IN this month.
    """
    queue = _planned.to_pay(session, start, end, include_prior_overdue=False)

    by_account: dict[int, int] = {}
    for tx in queue.upcoming:  # ← only the upcoming bucket is in-scope
        by_account[tx.account_id] = by_account.get(tx.account_id, 0) + tx.to_base
    rows: list[tuple[str, int]] = []
    for account_id, total in by_account.items():
        acc = session.get(Account, account_id)
        name = acc.name if acc is not None else f"account {account_id}"
        rows.append((name, total))
    rows.sort(key=lambda r: r[0])
    return [f"{name}: {money(total)} pending" for name, total in rows]
```

### Capa de Presentación

**`backend/src/quaestor/mcp/format.py`** (modificación de `to_pay_table`):

```python
def to_pay_table(queue: OutstandingQueue) -> str:
    """Render the outstanding queue as markdown.

    Layout: overdue section first (with ⚠️ marker), then upcoming. Empty
    bucket → omitted entirely (silence is the right state). Both empty
    → "Nothing outstanding."
    """
    if queue.is_empty:
        return "Nothing outstanding."

    sections: list[str] = []
    if queue.overdue:
        sections.append("## ⚠️ Overdue\n")
        sections.append(_table(queue.overdue))
    if queue.upcoming:
        if sections:
            sections.append("")  # blank line between sections
        sections.append("## Upcoming\n")
        sections.append(_table(queue.upcoming))
    return "\n".join(sections)
```

**Wire format REST `/api/planned/to-pay`** (cambia):

```json
{
  "overdue":  [ { "id": 1540, "payee": "Tigo", "date": "2026-06-28", ... }, ... ],
  "upcoming": [ { "id": 1462, "payee": "Goal: Korea", "date": "2026-06-30", ... }, ... ],
  "total_base": 26579412
}
```

**Frontend `to-pay-widget.tsx` y `app/(app)/to-pay/page.tsx`** — render dos secciones condicionalmente:

```tsx
{query.data && (
  <>
    <p className="font-display text-3xl font-bold tabular-nums tracking-tight">
      {formatCents(query.data.total_base, "COP")}
    </p>

    {query.data.overdue.length > 0 && (
      <section>
        <header>
          <span aria-hidden>⚠️</span>
          <h3>Vencidos</h3>
          <span>{query.data.overdue.length}</span>
        </header>
        <ul>{query.data.overdue.map((item) => <OverdueRow ... />)}</ul>
      </section>
    )}

    {query.data.upcoming.length > 0 && (
      <section>
        <header>
          <h3>{scope === "week" ? "Esta semana" : "Este mes"}</h3>
          <span>{query.data.upcoming.length}</span>
        </header>
        <ul>{query.data.upcoming.map((item) => <UpcomingRow ... />)}</ul>
      </section>
    )}

    {query.data.overdue.length === 0 && query.data.upcoming.length === 0 && (
      <p>Nada pendiente en este periodo.</p>
    )}
  </>
)}
```

- `OverdueRow` = el row actual con badge "Vencido" (reusado, sin cambios).
- `UpcomingRow` = el mismo row SIN el badge (date no está vencida).

## Tests (TDD — todos RED primero)

**`backend/tests/domain/test_planned_queue.py`** (nuevo)

| Test | Contrato |
|---|---|
| `test_outstanding_queue_buckets_are_mutually_exclusive` | overdue y upcoming nunca comparten un tx. |
| `test_outstanding_queue_total_is_sum_of_both_buckets` | `total_base` = `sum(overdue.to_base) + sum(upcoming.to_base)`. |
| `test_outstanding_queue_is_empty_when_both_buckets_empty` | `is_empty` True. |
| `test_outstanding_queue_all_items_overdue_first` | `all_items()` = `[*overdue, *upcoming]`. |
| `test_outstanding_queue_is_frozen` | No se puede mutar. |

**`backend/tests/services/test_planned.py`** (extender)

| Test | Contrato |
|---|---|
| `test_to_pay_includes_overdue_before_since` | Item con `date < since` y `date < today` aparece en `overdue` (default). **Reproduce el bug del usuario.** |
| `test_to_pay_overdue_excludes_items_on_or_after_today` | Items con `date == today` van a `upcoming`, no a `overdue`. |
| `test_to_pay_overdue_excludes_items_after_until` | Item con `date > until` no aparece en ningún bucket. |
| `test_to_pay_upcoming_respects_since_floor` | `upcoming` arranca en `max(since, today)`, no antes. |
| `test_to_pay_include_prior_overdue_false_omits_overdue_bucket` | Retrospectiva: el bucket `overdue` está vacío. |
| `test_to_pay_inverted_window_raises` | (existente, sin cambios) |
| `test_to_pay_excludes_posted` | (existente, ahora verifica que `posted` no aparece en ningún bucket) |

**`backend/tests/mcp/test_temporal.py`** (extender)

| Test | Contrato |
|---|---|
| `test_to_pay_table_renders_two_sections` | Cuando overdue y upcoming están presentes, la tabla tiene "## ⚠️ Overdue" y "## Upcoming". |
| `test_to_pay_table_omits_empty_overdue_section` | Sin overdue: solo "## Upcoming". |
| `test_to_pay_table_omits_empty_upcoming_section` | Sin upcoming: solo "## ⚠️ Overdue". |
| `test_to_pay_table_empty_queue` | Cola vacía: "Nothing outstanding." |

**`backend/tests/api/test_planned.py`** (extender)

| Test | Contrato |
|---|---|
| `test_to_pay_response_has_overdue_and_upcoming_keys` | Wire format nuevo. |
| `test_to_pay_response_includes_overdue_before_since` | Reproducción del bug: EPM del 2026-06-22 aparece en `overdue` con `since=2026-07-01`. |

**`frontend/components/to-pay-widget.test.tsx`** (nuevo, Vitest + Testing Library)

| Test | Contrato |
|---|---|
| `renders_overdue_section_when_overdue_items_present` | Header "Vencidos" visible. |
| `renders_upcoming_section_when_upcoming_items_present` | Header "Esta semana" / "Este mes" visible. |
| `does_not_render_overdue_section_when_overdue_empty` | Sin header "Vencidos" si no hay vencidos. |
| `shows_total_base_from_sum_of_both_buckets` | Total visible = `formatCents(total_base)`. |

## Enmiendas y follow-ups

- **ADR-0021**: no se toca. El cambio de default de orden sigue válido; este spec opera encima sin contradicción.
- **ADR nuevo (0023)**: documenta este cambio de contrato. Status: `proposed` durante implementación, `accepted` post-merge.
- **Breaking change del wire format**: `{items, total_base}` → `{overdue, upcoming, total_base}`. No hay consumers REST externos fuera del codebase (verificado: el único consumer es el frontend interno). Si en el futuro un script externo asume el shape anterior, el cambio se nota en release notes del próximo deploy.
- **Follow-up futuro**: si se quiere un bucket `forecast` (items due > until, ej. para mostrar "próximos vencimientos más allá del horizonte"), es un campo nuevo en el VO, sin breaking change.

## No-objetivos

- Cambios al orden de la cola (eso es ADR-0021, ya merged).
- Notificaciones push/email de items vencidos (out of scope; requiere canal de notificaciones).
- Auto-archive después de N días sin acción (YAGNI; hoy el reporte mensual lo refleja como "no se contabilizó").
- Cambios al esquema de la base de datos o migraciones Alembic (el campo `date` ya existe en `transaction`).
- Reescritura del widget de chat o de la narración LLM (sin efecto: el chat recibe el tool output como data y compone su propia narrativa).

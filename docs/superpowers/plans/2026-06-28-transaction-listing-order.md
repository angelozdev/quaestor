# Transaction Listing Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the default order of `services.transactions.list_transactions` to `created_at DESC, id DESC` via a registry-driven `SortSpec` primitive, lock `planned.to_pay` to chronological-by-due-date, and expose `sort`/`order` kwargs at the REST and MCP surfaces. Amend ADR-0021 to reflect the actual design.

**Architecture:** Introduce `domain/sort.py` with an immutable `SortSpec` value object and a per-service column registry. The service uses `SortSpec.resolve()` to translate `(field, order)` into a SQLAlchemy `(primary, tiebreaker)` tuple. The service default flips; `planned.to_pay` opts out by passing `sort="date", order="asc"` explicitly. REST and MCP layers accept the same kwargs; Pydantic validates at the boundary.

**Tech Stack:** Python 3.12 · SQLModel · Pydantic v2 · FastAPI · FastMCP · pytest · `uv` · SQLite in-memory for tests.

**Spec:** `docs/superpowers/specs/2026-06-28-transaction-listing-order-design.md`

## Global Constraints

- **ADR-0001 (language):** All code, identifiers, comments, docstrings, and commit messages in English.
- **ADR-0009 / -0006 (parity):** REST and MCP must stay behaviorally aligned. Adding `sort`/`order` to one means adding to the other.
- **TDD discipline:** Every task writes the failing test FIRST and runs it to confirm the red. No implementation without a red test.
- **Commit cadence:** Every task that modifies tracked files ends in a commit. No WIP / fixup / squash commits inside a task.
- **No new dependencies.** The implementation uses stdlib `dataclasses`, existing SQLModel/Pydantic surface, no new pip packages.
- **Don't break existing tests.** Every existing test in `tests/services/test_transactions.py`, `tests/services/test_planned.py`, `tests/api/test_transactions.py`, `tests/mcp/test_core_reads.py` must keep passing. The change is a default flip + opt-out, not a removal.
- **Tests run with:** `cd backend && uv run pytest <path> -v`. Working directory for every command is the repo root unless stated.

## File Structure

### New files

| Path | Responsibility |
|---|---|
| `backend/src/quaestor/domain/sort.py` | `SortField` / `Order` Literal types, `SortableColumns` registry type, `SortSpec` value object with `resolve()`. |
| `backend/tests/domain/test_sort.py` | Behavior tests for `SortSpec` (rejection, error message, SQL ordering). |

### Modified files

| Path | Change |
|---|---|
| `backend/src/quaestor/services/transactions.py` | Add `*_TRANSACTION_SORTABLE` registry; add `sort`/`order` keyword-only kwargs to `list_transactions`; default flips to `created_at DESC, id DESC`. |
| `backend/src/quaestor/services/planned.py` | `to_pay` passes `sort="date", order="asc"` explicitly. |
| `backend/src/quaestor/api/routers/transactions.py` | Add `sort` / `order` query params; pass through to service. |
| `backend/src/quaestor/mcp/tools/core.py` | Add `sort` / `order` fields to `ListTransactionsInput`; pass through to service. |
| `backend/tests/services/test_transactions.py` | Add sort-behavior tests. |
| `backend/tests/services/test_planned.py` | Add `to_pay` chronological-order lock test. |
| `backend/tests/api/test_transactions.py` | Add REST sort/order tests. |
| `backend/tests/mcp/test_core_reads.py` | Add MCP sort/order tests. |
| `docs/adr/0021-default-transaction-listing-order-created-at-desc.md` | Amend Decision outcome and Consequences. Status stays `proposed` until merge. |
| `docs/adr/README.md` | No status flip yet (Status flips post-merge in a follow-up commit). |

---

## Task 1: `domain/sort.py` — SortSpec value object

**Files:**
- Create: `backend/src/quaestor/domain/sort.py`
- Create: `backend/tests/domain/test_sort.py`

**Interfaces:**
- Produces (consumed by Task 2): `SortSpec(field, order).resolve(sortable: dict[str, ColumnElement], tiebreaker: ColumnElement) -> tuple[ColumnElement, ColumnElement]`.
- Produces: `SortField = Literal["date", "created_at"]`, `Order = Literal["asc", "desc"]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/domain/test_sort.py`:

```python
"""Behavior tests for the SortSpec value object.

Every test exercises an observable outcome — input rejected with a useful
error, or a SQL query returns rows in a specific order. Tests of pure
implementation details (e.g. that SortSpec is a frozen dataclass, or that
the Literal types compile to certain strings) are intentionally omitted:
the runtime ordering tests below would catch any mutation that actually
broke behavior, and the Literal types are validated by Pydantic at the
REST/MCP boundary in Tasks 4 and 5.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import select

from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType, Transaction
from quaestor.domain.sort import SortSpec
from quaestor.services import accounts, transactions


def _sortable() -> dict[str, object]:
    return {"date": Transaction.date, "created_at": Transaction.created_at}


def _seed(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=100_000)
    t1 = transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 1), "first")
    t2 = transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 2), "second")
    t3 = transactions.record_expense(session, a.id, 300, "COP", date(2026, 6, 3), "third")
    return t1, t2, t3


def test_sort_spec_rejects_unknown_field():
    """An unknown field is rejected at the boundary instead of silently
    passing through to SQL."""
    spec = SortSpec(field="amount", order="asc")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="unknown sort field"):
        spec.resolve(_sortable(), Transaction.id)  # type: ignore[arg-type]


def test_sort_spec_error_lists_allowed_fields():
    """An unknown-field error must enumerate the allowed values so callers
    can self-correct without reading the source."""
    spec = SortSpec(field="amount", order="asc")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc_info:
        spec.resolve(_sortable(), Transaction.id)  # type: ignore[arg-type]
    msg = str(exc_info.value)
    assert "date" in msg and "created_at" in msg


def test_sort_spec_resolve_desc_orders_newest_creation_first(session):
    """resolved (created_at, desc) applied to a real query returns
    newest-created row first."""
    _seed(session)
    spec = SortSpec(field="created_at", order="desc")
    primary, secondary = spec.resolve(_sortable(), Transaction.id)
    rows = session.exec(select(Transaction).order_by(primary, secondary)).all()
    assert [r.payee for r in rows] == ["third", "second", "first"]


def test_sort_spec_resolve_asc_orders_oldest_date_first(session):
    """resolved (date, asc) returns oldest-date row first."""
    _seed(session)
    spec = SortSpec(field="date", order="asc")
    primary, secondary = spec.resolve(_sortable(), Transaction.id)
    rows = session.exec(select(Transaction).order_by(primary, secondary)).all()
    assert [r.payee for r in rows] == ["first", "second", "third"]


def test_sort_spec_resolve_date_desc_orders_newest_date_first(session):
    """resolved (date, desc) returns newest-date row first."""
    _seed(session)
    spec = SortSpec(field="date", order="desc")
    primary, secondary = spec.resolve(_sortable(), Transaction.id)
    rows = session.exec(select(Transaction).order_by(primary, secondary)).all()
    assert [r.payee for r in rows] == ["third", "second", "first"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd backend && uv run pytest tests/domain/test_sort.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.domain.sort'`.

- [ ] **Step 3: Implement `domain/sort.py`**

Create `backend/src/quaestor/domain/sort.py`:

```python
"""Sort policy: immutable spec + per-service column registry.

`SortSpec` is the value object that callers build and pass to services that
accept `sort` / `order` kwargs. The service resolves the spec against its
own `SortableColumns` registry to produce a SQLAlchemy `(primary, tiebreaker)`
tuple suitable for `.order_by(*spec.resolve(...))`.

Pattern: Value Object + Registry / Lookup table.
SOLID: SRP (the spec only knows about ordering, not filters); OCP (adding a
new sortable field is one line in the service's registry, zero changes here);
DIP (`resolve` accepts the column map and tiebreaker, so the spec has no
direct dependency on a specific SQLModel class).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import ColumnElement

from .errors import ValidationError

# Public API surface — exposed to REST/MCP for input validation.
SortField = Literal["date", "created_at"]
Order = Literal["asc", "desc"]

# Per-service mapping of `sort` value -> SQLAlchemy column attribute.
SortableColumns = dict[str, ColumnElement]


@dataclass(frozen=True, slots=True)
class SortSpec:
    """Immutable (field, order) pair. Resolves to a (primary, tiebreaker)
    tuple suitable for SQLAlchemy `.order_by(*spec.resolve(...))`.

    Frozen + slots: hashable, can't drift between construction and use.
    """

    field: SortField
    order: Order

    def resolve(
        self,
        sortable: SortableColumns,
        tiebreaker: ColumnElement,
    ) -> tuple[ColumnElement, ColumnElement]:
        """Translate (field, order) into a (primary, tiebreaker) tuple.

        Both expressions share the same direction (so that the tiebreaker
        is consistent when two rows share the primary value).

        Raises:
            ValidationError: `field` is not in `sortable`. The Literal type
                prevents this at type-check time, but a caller that bypasses
                the type system (e.g. dict-construction) will hit this.
        """
        col = sortable.get(self.field)
        if col is None:
            raise ValidationError(
                f"unknown sort field: {self.field!r}; "
                f"allowed: {sorted(sortable)}"
            )
        desc = self.order == "desc"
        return (
            col.desc() if desc else col.asc(),
            tiebreaker.desc() if desc else tiebreaker.asc(),
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `cd backend && uv run pytest tests/domain/test_sort.py -v`
Expected: PASS — 6 tests green (2 rejection + 3 SQL ordering + 1 error-message).

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass (no `domain.sort` consumers exist yet, so no surface area changed).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/domain/sort.py backend/tests/domain/test_sort.py
git commit -m "feat(domain): add SortSpec value object + per-service column registry"
```

---

## Task 2: `services.transactions.list_transactions` — accept `sort`/`order` and flip default

**Files:**
- Modify: `backend/src/quaestor/services/transactions.py:298-342` (`list_transactions` function)
- Modify: `backend/tests/services/test_transactions.py` (append new tests)

**Interfaces:**
- Consumes (from Task 1): `SortSpec`, `SortField`, `Order` from `quaestor.domain.sort`.
- Produces (consumed by Tasks 3, 4, 5): `transactions.list_transactions(session, ..., *, sort="created_at", order="desc")`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_transactions.py`:

```python
# --- sort / order behaviour (ADR-0021 amended) ---


def test_list_transactions_default_orders_by_created_at_desc(session):
    """Default: newest-created first, regardless of logical date."""
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    # Insert in deliberately misleading order: mid (oldest created) first.
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 15), "mid")
    transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    txs = transactions.list_transactions(session)
    # Creation order: mid, old, new. Default = created_at DESC, id DESC.
    assert [t.payee for t in txs] == ["new", "old", "mid"]


def test_list_transactions_sort_date_asc_orders_chronologically(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 15), "mid")
    transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    txs = transactions.list_transactions(session, sort="date", order="asc")
    assert [t.payee for t in txs] == ["old", "mid", "new"]


def test_list_transactions_sort_date_desc_orders_reverse_chronologically(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 15), "mid")
    transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    txs = transactions.list_transactions(session, sort="date", order="desc")
    assert [t.payee for t in txs] == ["new", "mid", "old"]
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `cd backend && uv run pytest tests/services/test_transactions.py -v -k "default_orders_by_created_at_desc or sort_date_asc or sort_date_desc"`
Expected: 3 failures — `test_list_transactions_default_orders_by_created_at_desc` fails because the current default is `date ASC`, returning `["old", "mid", "new"]`. The two sort/order tests fail with `TypeError: list_transactions() got an unexpected keyword argument 'sort'`.

- [ ] **Step 3: Update `list_transactions` in `services/transactions.py`**

At the top of `backend/src/quaestor/services/transactions.py`, add the import (next to the existing `from ..domain.rules import ...` block):

```python
from ..domain.sort import Order, SortField, SortSpec, SortableColumns
```

After the `_record` helpers (or anywhere at module scope before `list_transactions`), add the registry:

```python
# Per-service sortable columns. Open for extension: adding a new sortable
# field is one line here plus one Literal member in domain/sort.py.
_TRANSACTION_SORTABLE: SortableColumns = {
    "date":       Transaction.date,
    "created_at": Transaction.created_at,
}
```

Replace the body of `list_transactions` (keep the docstring, replace everything from `stmt = select(Transaction)` through the `return` statement) with:

```python
    stmt = select(Transaction)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if type is not None:
        stmt = stmt.where(Transaction.type == TxType(type))
    if status is not None:
        stmt = stmt.where(Transaction.status == TxStatus(status))
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if tag is not None:
        stmt = (
            stmt.join(TransactionTag, TransactionTag.transaction_id == Transaction.id)  # type: ignore[arg-type]
            .join(Tag, Tag.id == TransactionTag.tag_id)  # type: ignore[arg-type]
            .where(Tag.name == tag)
        )
    spec = SortSpec(field=sort, order=order)
    primary, secondary = spec.resolve(_TRANSACTION_SORTABLE, Transaction.id)
    return list(session.exec(stmt.order_by(primary, secondary)).all())
```

And replace the function signature + docstring. The new signature must declare `sort`/`order` as keyword-only. Final form of `list_transactions`:

```python
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
    """List transactions with optional filters, ordered by `created_at DESC, id DESC`.

    The default puts the most recently created transaction first regardless
    of its logical `date`, matching the user's mental model on
    `/transactions` ("what I just entered is on top"). Pass `sort="date",
    order="asc"` to fall back to chronological-by-date (used by
    `planned.to_pay`, where `date` is the due date).

    Args:
        session: Database session.
        account_id: Filter by account.
        category_id: Filter by category.
        tag: Filter by tag name (exact match).
        type: Filter by TxType (or a value coercible to TxType).
        status: Filter by TxStatus (or a value coercible to TxStatus).
        date_from: Include transactions on or after this date.
        date_to: Include transactions on or before this date.
        sort: Primary sort field. One of `SortField`.
        order: Sort direction. One of `Order`.

    Returns:
        List of Transaction rows in deterministic order
        (primary field, then `id` as tiebreaker in the same direction).
    """
    stmt = select(Transaction)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if type is not None:
        stmt = stmt.where(Transaction.type == TxType(type))
    if status is not None:
        stmt = stmt.where(Transaction.status == TxStatus(status))
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if tag is not None:
        stmt = (
            stmt.join(TransactionTag, TransactionTag.transaction_id == Transaction.id)  # type: ignore[arg-type]
            .join(Tag, Tag.id == TransactionTag.tag_id)  # type: ignore[arg-type]
            .where(Tag.name == tag)
        )
    spec = SortSpec(field=sort, order=order)
    primary, secondary = spec.resolve(_TRANSACTION_SORTABLE, Transaction.id)
    return list(session.exec(stmt.order_by(primary, secondary)).all())
```

- [ ] **Step 4: Run the new tests to confirm they pass**

Run: `cd backend && uv run pytest tests/services/test_transactions.py -v -k "default_orders_by_created_at_desc or sort_date_asc or sort_date_desc"`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Run the full service test file**

Run: `cd backend && uv run pytest tests/services/test_transactions.py -v`
Expected: all pre-existing tests still pass + 3 new tests green.

- [ ] **Step 6: Run the full suite to catch unintended fallout**

Run: `cd backend && uv run pytest -q`
Expected: all pass except `test_planned.py::test_to_pay_*` if any test there happened to assert order (none do — the file currently asserts shape, not order, but `test_planned.py` callers that go through `list_transactions` are unaffected because `to_pay` will be updated in Task 3).

If anything fails, fix or update the failing assertion — do not silence.

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/services/transactions.py backend/tests/services/test_transactions.py
git commit -m "feat(services): list_transactions defaults to created_at desc + sort/order kwargs"
```

---

## Task 3: `planned.to_pay` — explicit chronological order (candado)

**Files:**
- Modify: `backend/src/quaestor/services/planned.py:100-115` (`to_pay` function)
- Modify: `backend/tests/services/test_planned.py` (append new test)

**Interfaces:**
- Consumes (from Task 2): `transactions.list_transactions(..., sort=..., order=...)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_planned.py`:

```python
# --- ADR-0021 amended: to_pay must keep chronological-by-due-date order ---


def test_to_pay_orders_by_due_date_asc(session):
    """Lock the chronological-by-due-date contract. Creation order is set
    OPPOSITE to due-date order, so any non-chronological sort (e.g. the
    new created_at DESC default) returns the wrong sequence and this
    test fails. After to_pay passes sort='date', order='asc' explicitly,
    this test passes."""
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=1_000_000)
    # Creation order: Card first, Rent second.
    # Due-date order: Card (6-30) before Rent (7-15).
    planned.plan_payment(session, "Card", 200_000, a.id, "COP", due_date=date(2026, 6, 30))
    planned.plan_payment(session, "Rent", 500_000, a.id, "COP", due_date=date(2026, 7, 15))
    result = planned.to_pay(session, date(2026, 6, 1), date(2026, 7, 31))
    assert [t.payee for t in result["items"]] == ["Card", "Rent"]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/services/test_planned.py -v -k "orders_by_due_date_asc"`
Expected: FAIL — under the new `created_at DESC, id DESC` default, `to_pay` returns `["Rent", "Card"]` (newer id / later creation first). Expected `["Card", "Rent"]`.

- [ ] **Step 3: Update `to_pay` to pass explicit sort kwargs**

Open `backend/src/quaestor/services/planned.py`. In the `to_pay` function, replace the `_tx.list_transactions(...)` call (currently at line 111):

```python
        items = _tx.list_transactions(
            session, status="planned", date_from=since, date_to=until,
        )
```

with:

```python
        items = _tx.list_transactions(
            session, status="planned", date_from=since, date_to=until,
            sort="date", order="asc",   # chronological-by-due-date; ADR-0021 amended
        )
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/services/test_planned.py -v -k "orders_by_due_date_asc"`
Expected: PASS.

- [ ] **Step 5: Run the full planned test file**

Run: `cd backend && uv run pytest tests/services/test_planned.py -v`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/services/planned.py backend/tests/services/test_planned.py
git commit -m "fix(planned): lock to_pay to chronological-by-due-date order"
```

---

## Task 4: REST `GET /transactions` — expose `sort` / `order`

**Files:**
- Modify: `backend/src/quaestor/api/routers/transactions.py:24-44` (the `list_transactions` route handler)
- Modify: `backend/tests/api/test_transactions.py` (append new tests)

**Interfaces:**
- Consumes (from Task 2): `transactions.list_transactions(..., sort=..., order=...)`.
- Produces: `GET /transactions?sort=<field>&order=<dir>` accepts the same `SortField` / `Order` Literal types.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/api/test_transactions.py`:

```python
# --- ADR-0021 amended: sort/order query params on GET /transactions ---


def test_list_endpoint_default_orders_by_created_at_desc(client, auth, two_accounts):
    """Default endpoint order: newest-created first, regardless of date."""
    cash, _ = two_accounts
    # Insert in misleading order: oldest creation first.
    client.post("/api/transactions", headers=auth, json={
        "type": "expense", "account_id": cash["id"], "amount": 100,
        "currency": "COP", "date": "2026-06-15", "payee": "mid",
    })
    client.post("/api/transactions", headers=auth, json={
        "type": "expense", "account_id": cash["id"], "amount": 200,
        "currency": "COP", "date": "2026-06-01", "payee": "old",
    })
    client.post("/api/transactions", headers=auth, json={
        "type": "expense", "account_id": cash["id"], "amount": 300,
        "currency": "COP", "date": "2026-07-01", "payee": "new",
    })
    body = client.get("/api/transactions", headers=auth).json()
    assert [t["payee"] for t in body] == ["new", "old", "mid"]


def test_list_endpoint_sort_date_asc_orders_chronologically(client, auth, two_accounts):
    cash, _ = two_accounts
    for payee, date in [("mid", "2026-06-15"), ("old", "2026-06-01"), ("new", "2026-07-01")]:
        client.post("/api/transactions", headers=auth, json={
            "type": "expense", "account_id": cash["id"], "amount": 100,
            "currency": "COP", "date": date, "payee": payee,
        })
    body = client.get("/api/transactions", headers=auth, params={"sort": "date", "order": "asc"}).json()
    assert [t["payee"] for t in body] == ["old", "mid", "new"]


def test_list_endpoint_invalid_sort_returns_422(client, auth):
    resp = client.get("/api/transactions", headers=auth, params={"sort": "amount"})
    assert resp.status_code == 422
    assert "sort" in resp.text.lower()
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `cd backend && uv run pytest tests/api/test_transactions.py -v -k "default_orders_by_created_at_desc or sort_date_asc or invalid_sort"`
Expected: 3 failures — the default-ordering test fails because the endpoint currently passes through the old default (`date ASC`); the sort-date-asc test fails because `sort` is not a valid query param (`422 Unprocessable Entity` from FastAPI); the invalid-sort test fails because the endpoint doesn't validate, so it would pass `sort=amount` straight through (status 200, wrong order).

- [ ] **Step 3: Update the REST router**

Open `backend/src/quaestor/api/routers/transactions.py`. Add the import near the top (after the existing `from ...domain.models import TxType`):

```python
from ...domain.sort import Order, SortField
```

Replace the `list_transactions` route handler signature and body (lines 24-44):

```python
@router.get("", response_model=list[TransactionOut])
def list_transactions(
    date_from: Date | None = None,
    date_to: Date | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    tag: str | None = None,
    type: TxType | None = None,
    status: str | None = None,
    sort: SortField = "created_at",
    order: Order = "desc",
    session: Session = Depends(get_session),
):
    return transactions.list_transactions(
        session,
        account_id=account_id,
        category_id=category_id,
        tag=tag,
        type=type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        order=order,
    )
```

- [ ] **Step 4: Run the new tests to confirm they pass**

Run: `cd backend && uv run pytest tests/api/test_transactions.py -v -k "default_orders_by_created_at_desc or sort_date_asc or invalid_sort"`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Run the full API test file**

Run: `cd backend && uv run pytest tests/api/test_transactions.py -v`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/api/routers/transactions.py backend/tests/api/test_transactions.py
git commit -m "feat(api): GET /transactions accepts sort/order query params"
```

---

## Task 5: MCP `list_transactions` — expose `sort` / `order` on the tool input

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/core.py:69-80` (`ListTransactionsInput` class)
- Modify: `backend/src/quaestor/mcp/tools/core.py:242-257` (`list_transactions` function — pass kwargs through)
- Modify: `backend/tests/mcp/test_core_reads.py` (append new tests)

**Interfaces:**
- Consumes (from Task 2): `transactions.list_transactions(..., sort=..., order=...)`.
- Produces: `ListTransactionsInput` accepts optional `sort: Literal["date","created_at"]` and `order: Literal["asc","desc"]`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/mcp/test_core_reads.py`:

```python
# --- ADR-0021 amended: sort/order on MCP list_transactions ---


def _row_of(out: str, payee: str) -> int:
    """Return the line index of the markdown-table row whose Payee cell
    equals `payee`. Format is `| ... | <payee> | ...` per
    `mcp.format.transactions_table`."""
    needle = f"| {payee} |"
    for i, line in enumerate(out.splitlines()):
        if needle in line:
            return i
    raise AssertionError(
        f"payee {payee!r} not found in transactions_table output:\n{out}"
    )


def test_mcp_list_transactions_default_orders_by_created_at_desc(session, seeded):
    from quaestor.services import transactions as tx_service

    acc = seeded["account"]
    tx_service.record_expense(session, acc.id, 100, "COP", date(2026, 6, 15), "mid")
    tx_service.record_expense(session, acc.id, 200, "COP", date(2026, 6, 1), "old")
    tx_service.record_expense(session, acc.id, 300, "COP", date(2026, 7, 1), "new")
    out = core.list_transactions(session, ListTransactionsInput())
    # Default = created_at DESC. Newest creation ("new") above "old" above "mid".
    new_row = _row_of(out, "new")
    old_row = _row_of(out, "old")
    mid_row = _row_of(out, "mid")
    assert new_row < old_row < mid_row, (
        f"expected order new < old < mid; got rows new={new_row}, "
        f"old={old_row}, mid={mid_row}\n{out}"
    )


def test_mcp_list_transactions_explicit_sort_date_asc(session, seeded):
    from quaestor.services import transactions as tx_service

    acc = seeded["account"]
    tx_service.record_expense(session, acc.id, 100, "COP", date(2026, 6, 15), "mid")
    tx_service.record_expense(session, acc.id, 200, "COP", date(2026, 6, 1), "old")
    tx_service.record_expense(session, acc.id, 300, "COP", date(2026, 7, 1), "new")
    out = core.list_transactions(
        session, ListTransactionsInput(sort="date", order="asc")
    )
    old_row = _row_of(out, "old")
    mid_row = _row_of(out, "mid")
    new_row = _row_of(out, "new")
    assert old_row < mid_row < new_row, (
        f"expected order old < mid < new; got rows old={old_row}, "
        f"mid={mid_row}, new={new_row}\n{out}"
    )
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `cd backend && uv run pytest tests/mcp/test_core_reads.py -v -k "default_orders_by_created_at_desc or explicit_sort_date_asc"`
Expected: 2 failures — the default-ordering test fails because the MCP tool currently passes no sort/order, so the service returns `date ASC` (old before mid before new). The explicit-sort test fails with a Pydantic validation error: `sort` is not a field on `ListTransactionsInput`.

- [ ] **Step 3: Update `ListTransactionsInput` and the tool function**

Open `backend/src/quaestor/mcp/tools/core.py`.

Add the imports near the top (the existing imports already include `Literal` and `Field`; verify they're present):

```python
from typing import Literal  # add if not present
```

Append `sort` and `order` fields to `ListTransactionsInput` (currently lines 69-80). Final form:

```python
class ListTransactionsInput(BaseModel):
    date_from: Date | None = Field(default=None, description="Include from this date")
    date_to: Date | None = Field(default=None, description="Include up to this date")
    account: str | None = Field(default=None, description="Filter by account name")
    category: str | None = Field(default=None, description="Filter by category name")
    tag: str | None = Field(default=None, description="Filter by tag name")
    type: Literal["expense", "income", "transfer"] | None = Field(
        default=None, description="Transaction type"
    )
    status: Literal["posted", "planned"] | None = Field(
        default=None, description="Transaction status"
    )
    sort: Literal["date", "created_at"] = Field(
        default="created_at",
        description="Primary sort field (date = logical date; created_at = row creation).",
    )
    order: Literal["asc", "desc"] = Field(
        default="desc", description="Sort direction."
    )
```

Update the `list_transactions` tool function body (currently lines 242-257) to pass the kwargs through to the service:

```python
@_as_text
def list_transactions(session: Session, inp: ListTransactionsInput) -> str:
    account_id = _resolve_account(session, inp.account).id if inp.account else None
    category_id = (
        _resolve_category(session, inp.category).id if inp.category else None
    )
    txs = transactions.list_transactions(
        session,
        account_id=account_id,
        category_id=category_id,
        tag=inp.tag,
        type=inp.type,
        status=inp.status,
        date_from=inp.date_from,
        date_to=inp.date_to,
        sort=inp.sort,
        order=inp.order,
    )
    return format.transactions_table(txs)
```

- [ ] **Step 4: Run the new tests to confirm they pass**

Run: `cd backend && uv run pytest tests/mcp/test_core_reads.py -v -k "default_orders_by_created_at_desc or explicit_sort_date_asc"`
Expected: PASS — 2 tests green.

- [ ] **Step 5: Run the full MCP test file**

Run: `cd backend && uv run pytest tests/mcp/test_core_reads.py -v`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/mcp/tools/core.py backend/tests/mcp/test_core_reads.py
git commit -m "feat(mcp): list_transactions tool accepts sort/order on input"
```

---

## Task 6: Amend ADR-0021 to reflect the actual design

**Files:**
- Modify: `docs/adr/0021-default-transaction-listing-order-created-at-desc.md`
- Modify: `docs/adr/README.md` (no status change yet — keep `proposed` until merge)

- [ ] **Step 1: Update the `Decision outcome` section**

Open `docs/adr/0021-default-transaction-listing-order-created-at-desc.md`.

Find the section that begins `## Decision outcome` and the `Chosen option: **1**` line. Replace that line and the paragraph that follows up to (but not including) the next `### Pros and cons of the options` heading with:

```markdown
## Decision outcome

Chosen option: **1 + 2 combined** — the service default flips to
`created_at DESC, id DESC`, and a `sort` / `order` keyword-only kwargs pair
is added to `services.transactions.list_transactions` so callers whose
ordering semantics differ from the listing default can declare their intent
explicitly. Today only `planned.to_pay` opts out (it passes `sort="date",
order="asc"` so the due-date queue stays chronological — without that
opt-out, flipping the default would silently invert the `/to-pay` queue
from "next due" to "most recently planned").

Option 2 alone (keep the service default as `date ASC`, add the kwargs,
let REST/MCP pass them) was rejected because every new caller would have
to know to opt in, and the `/transactions` page — the primary motivation
— would remain chronological. Option 1 alone (flip the default with no
escape hatch) was rejected after discovering the `planned.to_pay` caller:
its ordering is functional, not accidental, so the default flip would
break the due-date contract.

The `sort` / `order` plumbing is implemented through a `SortSpec` value
object (`backend/src/quaestor/domain/sort.py`) backed by a per-service
column registry — adding a third sortable field later is one line in the
registry plus one Literal member in the domain module.

If a future caller needs a third ordering semantic (e.g. `amount` desc),
add it to `_TRANSACTION_SORTABLE` in `services/transactions.py` and to the
`SortField` Literal in `domain/sort.py`. Do not change the default.
```

- [ ] **Step 2: Update the `Consequences` section**

In the same file, find the section that begins `## Consequences`. Replace the four bullets (Good / Good / Bad or cost / Follow-up) with:

```markdown
## Consequences

- Good: `/transactions` and the MCP `list_transactions` tool both show
  newest-first by creation, matching how the user reasons about activity.
- Good: when two transactions share a `created_at` (same microsecond), the
  `id DESC` tiebreaker keeps the order deterministic across calls.
- Good: the `sort` / `order` escape hatch means each future caller can
  declare its ordering semantics explicitly instead of inheriting whatever
  the default happens to be.
- Bad / cost: any consumer that iterated results assuming chronological
  order without an explicit sort arg now sees a different sequence. The
  only in-tree caller in this category was `planned.to_pay`; it has been
  updated to pass `sort="date", order="asc"` and is locked by
  `test_to_pay_orders_by_due_date_asc`. REST consumers outside this
  codebase should be flagged in release notes.
- Neutral / not a regression: the chat persona does not narrate raw
  transaction lists — the LLM receives the MCP tool output as data and
  composes its own narrative, so the default-order flip has no visible
  effect on chat responses. (Earlier drafts overstated this risk.)
- Follow-up: when the ledger grows past a few thousand rows, add a
  composite index `(created_at DESC, id DESC)` via Alembic. At current
  sizes the unordered scan + in-memory sort is negligible.
- Follow-up: the `id` tiebreaker is reliable under SQLite autoincrement
  with a single writer. If the store migrates to Postgres or another DB
  with sequence gaps from rolled-back inserts, revalidate that `id`
  remains monotonic under load (almost certainly true, but worth a note).
```

- [ ] **Step 3: Verify the ADR header is unchanged**

Confirm the header block (`Status: proposed`, `Date: 2026-06-28`, `Deciders: Angelo`, `Supersedes: —`, `Superseded by: —`) is untouched. The status stays `proposed` until the implementation lands and a follow-up commit flips it to `accepted`.

- [ ] **Step 4: Verify the index in `docs/adr/README.md` is unchanged**

Open `docs/adr/README.md`. Confirm row 37 still reads:

```
| 0021 | Default transaction listing order: created_at desc | proposed | 2026-06-28 |
```

Status flips to `accepted` in a separate follow-up commit after this plan is merged (the spec says: "Status: se mantiene proposed durante la implementación. Pasa a accepted tras merge").

- [ ] **Step 5: Commit the ADR amendment**

```bash
git add docs/adr/0021-default-transaction-listing-order-created-at-desc.md
git commit -m "docs(adr): amend 0021 — combined sort-param + default-flip decision"
```

---

## Self-Review

**1. Spec coverage:**
- `domain/sort.py` with SortSpec, SortField, Order, SortableColumns → Task 1.
- Service signature with keyword-only `sort`/`order` → Task 2.
- Default flip to `created_at DESC, id DESC` → Task 2.
- `planned.to_pay` explicit chronological opt-out → Task 3.
- REST `sort`/`order` query params + 422 on invalid → Task 4.
- MCP `sort`/`order` fields on `ListTransactionsInput` → Task 5.
- ADR-0021 Decision outcome rewrite → Task 6.
- ADR-0021 Consequences rewrite → Task 6.
- All 12 tests in spec → distributed across Tasks 1-5.

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later".
- Every code block is complete (no `...` placeholders in code).
- Every command shows full args and expected output.
- Every signature/type referenced in a later task is defined in an earlier task (SortSpec, SortField, Order, SortableColumns).

**3. Type consistency:**
- `SortSpec(field, order)` defined in Task 1; consumed in Tasks 2-5 unchanged.
- `_TRANSACTION_SORTABLE` defined in Task 2; used only there.
- `sort`/`order` kwarg names identical across `list_transactions` (Task 2), `to_pay` call site (Task 3), REST router (Task 4), `ListTransactionsInput` (Task 5).
- `sort` / `order` field names on `ListTransactionsInput` (Task 5) match the kwargs the service expects (Task 2).
- Test names match between spec and plan (`test_sort_spec_resolve_desc_orders_newest_creation_first`, `test_list_transactions_default_orders_by_created_at_desc`, `test_to_pay_orders_by_due_date_asc`, etc.).

**4. Risks not addressed:**
- None within this plan. The two follow-ups (index on `created_at`, Postgres tiebreaker revisit) are documented in the amended ADR but explicitly deferred per spec.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-28-transaction-listing-order.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

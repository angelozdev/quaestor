# P6 Frontend CRUD (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the already-built goals/budgets domain services as HTTP + MCP write paths, add the few missing service functions (recurring edit/delete, master un-archive), and graduate `/goals`, `/budgets`, `/recurring`, and the masters to full management UI — completing ADR-025.

**Architecture:** Backend-first, TDD. Each area moves through three backend layers (service function → thin REST router → thin MCP tool) before the frontend consumes it. The hard logic already exists in `services/`; Phase 2 is mostly exposure + small lifecycle additions. Soft-delete is uniform and reversible (ADR-0005); writes ship on HTTP and MCP together (ADR-0006). The frontend stays a thin client (no business arithmetic).

**Tech Stack:** Backend — Python · FastAPI · SQLModel · FastMCP · pytest · uv. Frontend — Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind v4 · `@base-ui/react` · `@tanstack/react-query` v5 · `sonner` · `date-fns` · pnpm.

## Global Constraints

- **All identifiers in English (ADR-0001).** User-facing copy is Spanish (Colombia) with correct diacritics.
- **Money is always integer cents.** Display via `formatCents(cents, currency)`; `MoneyInput` text↔cents is the only numeric transform allowed in the client.
- **Soft-delete is uniform and reversible (ADR-0005).** "Delete" deactivates (`Goal.status=paused`, `RecurringItem.active=false`, master `archived=true`); never `session.delete(...)` for Goal/RecurringItem/Account/Category/CategoryGroup. `POST /{id}/restore` reverses it; restoring an already-active/non-archived resource is an idempotent `200` no-op.
- **Write API shape (ADR-0006).** State transitions and create-actions are `POST /{id}/<verb>` (`contribute`, `restore`) returning the affected Out; the idempotent envelope assign is `PUT /budgets`. Every new goals/budgets/recurring HTTP write lands with its MCP sibling in the same change.
- **Thin client.** `assigned/spent/available`, `status`, balances, progress all arrive resolved from the API; the client only fetches, renders, formats.
- **Recurring edit affects the future only.** `materialize_due` reads the item's current fields when generating un-materialized occurrences; already-materialized planned/posted transactions are untouched. `type` and `currency` are immutable.
- **Backend verification:** from `backend/`, `uv run pytest <path>` per task; lint `uv run ruff check`.
- **Frontend verification:** from `frontend/`, `pnpm exec tsc --noEmit && pnpm lint`, then manual smoke against a running backend + `pnpm dev` (no automated UI runner, ADR-008).
- **Error contract (unchanged from Phase 1).** Backend `{ error, detail }` → `ApiError { status, code, message }`. Mutations → toast; page loads → `<ErrorState>` with retry. 401 → cache clear + `/login`.

## File Structure

```
backend/src/quaestor/
  domain/dtos.py                 # + BudgetLine dataclass
  services/
    accounts.py                  # + unarchive_account
    categories.py                # + unarchive_category, unarchive_group
    recurring.py                 # + update_recurring, deactivate_recurring, restore_recurring
    budgets.py                   # + list_budgets(year_month)
    goals.py                     # + list_goals, update_goal, pause_goal, restore_goal
  api/schemas.py                 # + GoalOut/GoalCreate/GoalUpdate/GoalContributeIn/GoalContributionOut,
                                 #   BudgetLineOut/BudgetAssignIn, RecurringUpdate
  api/routers/
    accounts.py                  # + POST /{id}/restore
    categories.py                # + POST /{id}/restore
    category_groups.py           # + POST /{id}/restore
    recurring.py                 # + PATCH /{id}, DELETE /{id}, POST /{id}/restore
    budgets.py                   # + GET ?month (lines), PUT (assign)
    goals.py                     # + GET, POST, PATCH /{id}, DELETE /{id}, POST /{id}/contribute, POST /{id}/restore
  mcp/tools/
    temporal.py                  # + update_recurring, delete_recurring impls + input models
    planning.py                  # NEW — goals/budgets MCP tools (mirrors temporal.py for P4)
  mcp/registry.py                # + register update_recurring/delete_recurring; + register_planning_tools
  mcp/format.py                  # + goal_*, budget_line_* formatters
  mcp/server.py                  # + call register_planning_tools
backend/tests/{services,api}/    # tests alongside each change

frontend/
  lib/api.ts                     # + Goal/GoalContribution/BudgetLine types + ~12 methods
  lib/query.ts                   # + qk.goals, qk.budgets; INVALIDATION.goalWrite, budgetWrite
  components/status-badge.tsx    # + goal status (active/reached/paused)
  app/(app)/recurring/page.tsx   # + edit / delete / restore + "show inactive" filter; banner removed
  app/(app)/budgets/page.tsx     # + per-category assign + envelope status; banner removed
  app/(app)/goals/page.tsx       # read → management; banner removed
  app/(app)/accounts/page.tsx    # + "Restaurar" row action
  app/(app)/categories/page.tsx  # + "Restaurar" row action
  app/(app)/category-groups/page.tsx # + "Restaurar" row action
```

---

## Phase A — Backend: un-archive masters (warm-up)

### Task 1: `unarchive_account` service + restore route

**Files:**
- Modify: `backend/src/quaestor/services/accounts.py`
- Modify: `backend/src/quaestor/api/routers/accounts.py`
- Test: `backend/tests/services/test_accounts.py`, `backend/tests/api/test_accounts.py`

**Interfaces:**
- Consumes: `accounts.get_account(session, account_id) -> Account` (exists), `accounts.archive_account` (exists).
- Produces: `accounts.unarchive_account(session, account_id: int) -> Account`; `POST /accounts/{id}/restore` → `AccountOut` (200).

- [ ] **Step 1: Write the failing service test**

In `backend/tests/services/test_accounts.py`, append:

```python
def test_unarchive_account_clears_flag(session):
    from quaestor.services import accounts
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    accounts.archive_account(session, acc.id)
    restored = accounts.unarchive_account(session, acc.id)
    assert restored.archived is False


def test_unarchive_active_account_is_noop(session):
    from quaestor.services import accounts
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    restored = accounts.unarchive_account(session, acc.id)
    assert restored.archived is False
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd backend && uv run pytest tests/services/test_accounts.py -k unarchive -v`
Expected: FAIL — `AttributeError: module 'quaestor.services.accounts' has no attribute 'unarchive_account'`.

- [ ] **Step 3: Implement `unarchive_account`**

In `backend/src/quaestor/services/accounts.py`, add after `archive_account`:

```python
def unarchive_account(session: Session, account_id: int) -> Account:
    """Re-activate an archived account. Idempotent no-op if already active.

    Raises:
        NotFound: If the account does not exist.
    """
    acc = get_account(session, account_id)
    acc.archived = False
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc
```

- [ ] **Step 4: Run service test, verify pass**

Run: `cd backend && uv run pytest tests/services/test_accounts.py -k unarchive -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Write the failing API test**

In `backend/tests/api/test_accounts.py`, append:

```python
def test_restore_account_endpoint(client, engine, auth):
    from quaestor.services import accounts
    from sqlmodel import Session
    with Session(engine) as s:
        acc = accounts.create_account(s, "Bank", "debit", "COP", balance=0)
        accounts.archive_account(s, acc.id)
        acc_id = acc.id
    r = client.post(f"/api/accounts/{acc_id}/restore", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False
```

- [ ] **Step 6: Run it, verify it fails**

Run: `cd backend && uv run pytest tests/api/test_accounts.py -k restore -v`
Expected: FAIL with 404/405 (route not defined).

- [ ] **Step 7: Add the restore route**

In `backend/src/quaestor/api/routers/accounts.py`, add after `archive_account`:

```python
@router.post("/{account_id}/restore", response_model=AccountOut)
def restore_account(account_id: int, session: Session = Depends(get_session)):
    return accounts.unarchive_account(session, account_id)
```

- [ ] **Step 8: Run API test, verify pass**

Run: `cd backend && uv run pytest tests/api/test_accounts.py -k restore -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/quaestor/services/accounts.py backend/src/quaestor/api/routers/accounts.py backend/tests
git commit -m "feat(api): unarchive_account + POST /accounts/{id}/restore (ADR-0005)"
```

---

### Task 2: `unarchive_category` + `unarchive_group` services + restore routes

**Files:**
- Modify: `backend/src/quaestor/services/categories.py`
- Modify: `backend/src/quaestor/api/routers/categories.py`, `backend/src/quaestor/api/routers/category_groups.py`
- Test: `backend/tests/services/test_categories.py`, `backend/tests/api/test_categories.py`, `backend/tests/api/test_category_groups.py`

**Interfaces:**
- Consumes: `categories.get_category` (exists), `categories.archive_category`/`archive_group` (exist).
- Produces: `categories.unarchive_category(session, category_id) -> Category`; `categories.unarchive_group(session, group_id) -> CategoryGroup`; `POST /categories/{id}/restore` → `CategoryOut`; `POST /category-groups/{id}/restore` → `CategoryGroupOut`.

- [ ] **Step 1: Write the failing service tests**

In `backend/tests/services/test_categories.py`, append:

```python
def test_unarchive_category_clears_flag(session):
    from quaestor.services import categories
    cat = categories.create_category(session, name="Food")
    categories.archive_category(session, cat.id)
    assert categories.unarchive_category(session, cat.id).archived is False


def test_unarchive_group_clears_flag(session):
    from quaestor.services import categories
    g = categories.create_group(session, name="Bills")
    categories.archive_group(session, g.id)
    assert categories.unarchive_group(session, g.id).archived is False
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/services/test_categories.py -k unarchive -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Implement both functions**

In `backend/src/quaestor/services/categories.py`, add `unarchive_category` after `archive_category`:

```python
def unarchive_category(session: Session, category_id: int) -> Category:
    """Re-activate an archived category. Idempotent no-op if already active.

    Raises:
        NotFound: If the category does not exist.
    """
    cat = get_category(session, category_id)
    cat.archived = False
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
```

And add `unarchive_group` after `archive_group`:

```python
def unarchive_group(session: Session, group_id: int) -> CategoryGroup:
    """Re-activate an archived category group. Idempotent no-op if already active.

    Raises:
        NotFound: If the group does not exist.
    """
    group = session.get(CategoryGroup, group_id)
    if group is None:
        raise NotFound(f"group {group_id} not found")
    group.archived = False
    session.add(group)
    session.commit()
    session.refresh(group)
    return group
```

- [ ] **Step 4: Run service tests, verify pass**

Run: `cd backend && uv run pytest tests/services/test_categories.py -k unarchive -v`
Expected: PASS (2).

- [ ] **Step 5: Write failing API tests**

In `backend/tests/api/test_categories.py`, append:

```python
def test_restore_category_endpoint(client, engine, auth):
    from quaestor.services import categories
    from sqlmodel import Session
    with Session(engine) as s:
        cat = categories.create_category(s, name="Food")
        categories.archive_category(s, cat.id)
        cat_id = cat.id
    r = client.post(f"/api/categories/{cat_id}/restore", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False
```

In `backend/tests/api/test_category_groups.py`, append:

```python
def test_restore_group_endpoint(client, engine, auth):
    from quaestor.services import categories
    from sqlmodel import Session
    with Session(engine) as s:
        g = categories.create_group(s, name="Bills")
        categories.archive_group(s, g.id)
        gid = g.id
    r = client.post(f"/api/category-groups/{gid}/restore", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False
```

- [ ] **Step 6: Run, verify fail**

Run: `cd backend && uv run pytest tests/api/test_categories.py tests/api/test_category_groups.py -k restore -v`
Expected: FAIL (routes missing).

- [ ] **Step 7: Add restore routes**

In `backend/src/quaestor/api/routers/categories.py`, after `archive_category`:

```python
@router.post("/{category_id}/restore", response_model=CategoryOut)
def restore_category(category_id: int, session: Session = Depends(get_session)):
    return categories.unarchive_category(session, category_id)
```

In `backend/src/quaestor/api/routers/category_groups.py`, after `archive_group`:

```python
@router.post("/{group_id}/restore", response_model=CategoryGroupOut)
def restore_group(group_id: int, session: Session = Depends(get_session)):
    return categories.unarchive_group(session, group_id)
```

- [ ] **Step 8: Run API tests, verify pass**

Run: `cd backend && uv run pytest tests/api/test_categories.py tests/api/test_category_groups.py -k restore -v`
Expected: PASS (2).

- [ ] **Step 9: Commit**

```bash
git add backend/src/quaestor/services/categories.py backend/src/quaestor/api/routers/categories.py backend/src/quaestor/api/routers/category_groups.py backend/tests
git commit -m "feat(api): unarchive category + group restore routes (ADR-0005)"
```

---

## Phase B — Backend: recurring edit / delete / restore

### Task 3: `update_recurring` service

**Files:**
- Modify: `backend/src/quaestor/services/recurring.py`
- Test: `backend/tests/services/test_recurring.py`

**Interfaces:**
- Consumes: `_require_account(session, account_id) -> Account` (exists, raises NotFound/ValidationError); `RecurringItem`, `Category`, `IntervalUnit`, `RecurringMode` models.
- Produces: `recurring.update_recurring(session, recurring_id, *, name=None, payee=None, mode=None, amount=None, category_id=_UNSET, account_id=None, interval_unit=None, interval_count=None, start_date=None, end_date=_UNSET) -> RecurringItem`. `None`/`_UNSET` leave a field unchanged; `category_id=None`/`end_date=None` clear them. `type` and `currency` are NOT parameters (immutable).

- [ ] **Step 1: Write failing tests**

In `backend/tests/services/test_recurring.py`, append:

```python
def test_update_recurring_changes_amount_and_payee(session):
    from quaestor.services import accounts, recurring
    from datetime import date
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    item = recurring.create_recurring(
        session, name="Rent", payee="LL", type="expense", mode="auto",
        amount=2_000_000, currency="COP", category_id=None, account_id=acc.id,
        interval_unit="month", interval_count=1, start_date=date(2026, 1, 1),
    )
    updated = recurring.update_recurring(session, item.id, amount=2_500_000, payee="New LL")
    assert updated.amount == 2_500_000 and updated.payee == "New LL"
    assert updated.currency == "COP"  # unchanged


def test_update_recurring_rejects_bad_interval(session):
    from quaestor.domain.errors import ValidationError
    from quaestor.services import accounts, recurring
    from datetime import date
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    item = recurring.create_recurring(
        session, name="X", payee="", type="expense", mode="auto", amount=1000,
        currency="COP", category_id=None, account_id=acc.id, interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    )
    import pytest
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, interval_count=0)


def test_update_recurring_account_must_match_currency(session):
    from quaestor.domain.errors import ValidationError
    from quaestor.services import accounts, recurring
    from datetime import date
    cop = accounts.create_account(session, "COP acct", "debit", "COP", balance=0)
    usd = accounts.create_account(session, "USD acct", "debit", "USD", balance=0)
    item = recurring.create_recurring(
        session, name="X", payee="", type="expense", mode="auto", amount=1000,
        currency="COP", category_id=None, account_id=cop.id, interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    )
    import pytest
    with pytest.raises(ValidationError):
        recurring.update_recurring(session, item.id, account_id=usd.id)


def test_update_recurring_not_found(session):
    from quaestor.domain.errors import NotFound
    from quaestor.services import recurring
    import pytest
    with pytest.raises(NotFound):
        recurring.update_recurring(session, 999, amount=1)
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/services/test_recurring.py -k update -v`
Expected: FAIL — attribute missing.

- [ ] **Step 3: Implement `update_recurring`**

In `backend/src/quaestor/services/recurring.py`, add a module-level sentinel near the imports (after the `_tx` import line):

```python
_UNSET = object()
```

Then add the function after `list_recurring`:

```python
def update_recurring(
    session: Session,
    recurring_id: int,
    *,
    name: str | None = None,
    payee: str | None = None,
    mode: RecurringMode | None = None,
    amount: int | None = None,
    category_id=_UNSET,
    account_id: int | None = None,
    interval_unit: IntervalUnit | None = None,
    interval_count: int | None = None,
    start_date: Date | None = None,
    end_date=_UNSET,
) -> RecurringItem:
    """Edit a recurring item. type and currency are immutable. Changes affect only
    future un-materialized occurrences (materialize_due reads current fields).

    `category_id=_UNSET`/`end_date=_UNSET` leave unchanged; `=None` clears them.

    Raises:
        NotFound: the item or a new account does not exist.
        ValidationError: amount <= 0, interval_count < 1, end_date < start_date,
            account currency mismatch, unknown/archived category.
    """
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    if name is not None:
        item.name = name
    if payee is not None:
        item.payee = payee
    if mode is not None:
        item.mode = RecurringMode(mode)
    if amount is not None:
        if amount <= 0:
            raise ValidationError("amount must be > 0")
        item.amount = amount
    if interval_unit is not None:
        item.interval_unit = IntervalUnit(interval_unit)
    if interval_count is not None:
        if interval_count < 1:
            raise ValidationError("interval_count must be >= 1")
        item.interval_count = interval_count
    if start_date is not None:
        item.start_date = start_date
    if end_date is not _UNSET:
        item.end_date = end_date
    if item.end_date is not None and item.end_date < item.start_date:
        raise ValidationError("end_date must be on or after start_date")
    if account_id is not None:
        acc = _require_account(session, account_id)
        if item.currency != acc.currency:
            raise ValidationError(
                f"currency {item.currency} does not match account currency {acc.currency}"
            )
        item.account_id = account_id
    if category_id is not _UNSET:
        if category_id is not None:
            cat = session.get(Category, category_id)
            if cat is None:
                raise ValidationError(f"category {category_id} not found")
            if cat.archived:
                raise ValidationError(f"category {category_id} is archived")
        item.category_id = category_id
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && uv run pytest tests/services/test_recurring.py -k update -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/recurring.py backend/tests/services/test_recurring.py
git commit -m "feat(recurring): update_recurring service (future-only edits)"
```

---

### Task 4: `deactivate_recurring` + `restore_recurring` services

**Files:**
- Modify: `backend/src/quaestor/services/recurring.py`
- Test: `backend/tests/services/test_recurring.py`

**Interfaces:**
- Produces: `recurring.deactivate_recurring(session, recurring_id) -> RecurringItem` (sets `active=False`); `recurring.restore_recurring(session, recurring_id) -> RecurringItem` (sets `active=True`). Both raise `NotFound`.

- [ ] **Step 1: Write failing tests**

In `backend/tests/services/test_recurring.py`, append:

```python
def test_deactivate_then_restore_recurring(session):
    from quaestor.services import accounts, recurring
    from datetime import date
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    item = recurring.create_recurring(
        session, name="Rent", payee="", type="expense", mode="auto", amount=1000,
        currency="COP", category_id=None, account_id=acc.id, interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    )
    assert recurring.deactivate_recurring(session, item.id).active is False
    assert recurring.list_recurring(session, active=True) == []
    assert recurring.restore_recurring(session, item.id).active is True
    assert len(recurring.list_recurring(session, active=True)) == 1


def test_deactivate_recurring_not_found(session):
    from quaestor.domain.errors import NotFound
    from quaestor.services import recurring
    import pytest
    with pytest.raises(NotFound):
        recurring.deactivate_recurring(session, 999)
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/services/test_recurring.py -k "deactivate or restore" -v`
Expected: FAIL — attribute missing.

- [ ] **Step 3: Implement both**

In `backend/src/quaestor/services/recurring.py`, add after `update_recurring`:

```python
def _set_active(session: Session, recurring_id: int, active: bool) -> RecurringItem:
    item = session.get(RecurringItem, recurring_id)
    if item is None:
        raise NotFound(f"recurring item {recurring_id} not found")
    item.active = active
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def deactivate_recurring(session: Session, recurring_id: int) -> RecurringItem:
    """Soft-delete: stop materializing future occurrences (existing ones stay).

    Raises:
        NotFound: the item does not exist.
    """
    return _set_active(session, recurring_id, False)


def restore_recurring(session: Session, recurring_id: int) -> RecurringItem:
    """Re-activate a deactivated recurring item. Idempotent no-op if already active.

    Raises:
        NotFound: the item does not exist.
    """
    return _set_active(session, recurring_id, True)
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && uv run pytest tests/services/test_recurring.py -k "deactivate or restore" -v`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/recurring.py backend/tests/services/test_recurring.py
git commit -m "feat(recurring): deactivate/restore (soft-delete, ADR-0005)"
```

---

### Task 5: Recurring PATCH / DELETE / restore routes

**Files:**
- Modify: `backend/src/quaestor/api/schemas.py`, `backend/src/quaestor/api/routers/recurring.py`
- Test: `backend/tests/api/test_recurring.py`

**Interfaces:**
- Consumes: `recurring.update_recurring`, `deactivate_recurring`, `restore_recurring` (Tasks 3-4).
- Produces: schema `RecurringUpdate`; routes `PATCH /recurring/{id}` → `RecurringOut`, `DELETE /recurring/{id}` (204), `POST /recurring/{id}/restore` → `RecurringOut`.

- [ ] **Step 1: Write failing API tests**

In `backend/tests/api/test_recurring.py`, append (reuses the file's `_seed_account` helper):

```python
def _seed_recurring(client, engine, auth):
    acc_id = _seed_account(engine)
    body = {
        "name": "Rent", "payee": "LL", "type": "expense", "mode": "auto",
        "amount": 2_000_000, "account_id": acc_id, "interval_unit": "month",
        "interval_count": 1, "start_date": "2026-01-01",
    }
    return client.post("/api/recurring", json=body, headers=auth).json()["id"]


def test_patch_recurring(client, engine, auth):
    rid = _seed_recurring(client, engine, auth)
    r = client.patch(f"/api/recurring/{rid}", json={"amount": 2_500_000, "payee": "New"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 2_500_000 and r.json()["payee"] == "New"


def test_delete_recurring_is_soft(client, engine, auth):
    rid = _seed_recurring(client, engine, auth)
    assert client.delete(f"/api/recurring/{rid}", headers=auth).status_code == 204
    # gone from active list, present when listing inactive
    assert client.get("/api/recurring?active=true", headers=auth).json() == []
    inactive = client.get("/api/recurring?active=false", headers=auth).json()
    assert [i["id"] for i in inactive] == [rid]


def test_restore_recurring(client, engine, auth):
    rid = _seed_recurring(client, engine, auth)
    client.delete(f"/api/recurring/{rid}", headers=auth)
    r = client.post(f"/api/recurring/{rid}/restore", headers=auth)
    assert r.status_code == 200 and r.json()["active"] is True
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/api/test_recurring.py -k "patch or delete or restore" -v`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add `RecurringUpdate` schema**

In `backend/src/quaestor/api/schemas.py`, add after `RecurringCreate`:

```python
class RecurringUpdate(BaseModel):
    name: str | None = None
    payee: str | None = None
    mode: RecurringMode | None = None
    amount: int | None = None
    category_id: int | None = None
    account_id: int | None = None
    interval_unit: IntervalUnit | None = None
    interval_count: int | None = None
    start_date: Date | None = None
    end_date: Date | None = None
```

- [ ] **Step 4: Add the routes**

In `backend/src/quaestor/api/routers/recurring.py`, update the schemas import to include `RecurringUpdate`, then add after `create_recurring`:

```python
@router.patch("/{recurring_id}", response_model=RecurringOut)
def update_recurring(
    recurring_id: int, body: RecurringUpdate, session: Session = Depends(get_session)
):
    fields = body.model_dump(exclude_unset=True)
    return recurring.update_recurring(session, recurring_id, **fields)


@router.delete("/{recurring_id}", status_code=204)
def deactivate_recurring(recurring_id: int, session: Session = Depends(get_session)):
    recurring.deactivate_recurring(session, recurring_id)
    return None


@router.post("/{recurring_id}/restore", response_model=RecurringOut)
def restore_recurring(recurring_id: int, session: Session = Depends(get_session)):
    return recurring.restore_recurring(session, recurring_id)
```

Note: the existing `skip_recurring` route is `POST /{recurring_id}/skip`; `restore` does not collide.

- [ ] **Step 5: Run, verify pass**

Run: `cd backend && uv run pytest tests/api/test_recurring.py -v`
Expected: PASS (all, including the pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/api/schemas.py backend/src/quaestor/api/routers/recurring.py backend/tests/api/test_recurring.py
git commit -m "feat(api): recurring PATCH/DELETE(soft)/restore routes"
```

---

### Task 6: Recurring MCP tools — `update_recurring`, `delete_recurring`

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/temporal.py`, `backend/src/quaestor/mcp/registry.py`, `backend/src/quaestor/mcp/format.py`
- Test: `backend/tests/mcp/test_temporal.py` (create if absent; otherwise append)

**Interfaces:**
- Consumes: `recurring.update_recurring`, `deactivate_recurring` (Tasks 3-4); `format.recurring_created` (exists, reused for the updated item).
- Produces: MCP tools `update_recurring`, `delete_recurring`; input models `UpdateRecurringInput`, `DeleteRecurringInput`; formatter `format.recurring_updated`, `format.recurring_deleted`.

- [ ] **Step 1: Write failing MCP test**

Create or append `backend/tests/mcp/test_temporal.py`:

```python
from datetime import date

from sqlmodel import Session

from quaestor.mcp.tools import temporal
from quaestor.mcp.tools.temporal import UpdateRecurringInput, DeleteRecurringInput
from quaestor.services import accounts, recurring


def _item(session):
    acc = accounts.create_account(session, "Bank", "debit", "COP", balance=0)
    return recurring.create_recurring(
        session, name="Rent", payee="", type="expense", mode="auto", amount=1000,
        currency="COP", category_id=None, account_id=acc.id, interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    )


def test_mcp_update_recurring(engine):
    with Session(engine) as s:
        item = _item(s)
        out = temporal.update_recurring(s, UpdateRecurringInput(recurring_id=item.id, amount=5000))
        assert "5" in out  # formatted amount appears
        assert recurring.list_recurring(s)[0].amount == 5000


def test_mcp_delete_recurring(engine):
    with Session(engine) as s:
        item = _item(s)
        temporal.delete_recurring(s, DeleteRecurringInput(recurring_id=item.id))
        assert recurring.list_recurring(s, active=True) == []
```

If `backend/tests/mcp/` has no `conftest.py` providing `engine`, reuse the services conftest pattern: add `backend/tests/mcp/conftest.py`:

```python
import pytest

from quaestor.db import init_db, make_engine


@pytest.fixture
def engine():
    eng = make_engine(memory=True)
    init_db(eng)
    return eng
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/mcp/test_temporal.py -v`
Expected: FAIL — `ImportError` for `UpdateRecurringInput`.

- [ ] **Step 3: Add formatters**

In `backend/src/quaestor/mcp/format.py`, add near `recurring_created`:

```python
def recurring_updated(item: RecurringItem) -> str:
    return "Updated " + recurring_created(item)


def recurring_deleted(item: RecurringItem) -> str:
    return f"Deactivated recurring '{item.name}' (id {item.id}). Existing occurrences stay."
```

(`RecurringItem` is already imported in `format.py` for `recurring_created`; if not, add it to the imports.)

- [ ] **Step 4: Add input models + impls**

In `backend/src/quaestor/mcp/tools/temporal.py`, add to the input-models section:

```python
class UpdateRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id")
    name: str | None = Field(default=None, description="New display name")
    payee: str | None = Field(default=None, description="New payee")
    mode: Literal["auto", "manual"] | None = Field(default=None, description="New mode")
    amount: int | None = Field(default=None, gt=0, description="New amount in cents")
    interval_unit: Literal["day", "week", "month", "year"] | None = Field(
        default=None, description="New interval unit"
    )
    interval_count: int | None = Field(default=None, ge=1, description="New interval count")
    start_date: Date | None = Field(default=None, description="New anchor date YYYY-MM-DD")
    end_date: Date | None = Field(default=None, description="New last date YYYY-MM-DD")


class DeleteRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id to deactivate")
```

And to the impls section:

```python
@_as_text
def update_recurring(session: Session, inp: UpdateRecurringInput) -> str:
    fields = inp.model_dump(exclude_unset=True, exclude={"recurring_id"})
    item = recurring.update_recurring(session, inp.recurring_id, **fields)
    return format.recurring_updated(item)


@_as_text
def delete_recurring(session: Session, inp: DeleteRecurringInput) -> str:
    item = recurring.deactivate_recurring(session, inp.recurring_id)
    return format.recurring_deleted(item)
```

- [ ] **Step 5: Wire into the registry**

In `backend/src/quaestor/mcp/registry.py`: add `UpdateRecurringInput, DeleteRecurringInput` to the `from .tools.temporal import (...)` block; add `"update_recurring", "delete_recurring"` to `TEMPORAL_TOOL_NAMES`; and register inside `register_temporal_tools`:

```python
    @mcp.tool(name="update_recurring", description="Edit a recurring item (future occurrences only).")
    def update_recurring(item: UpdateRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.update_recurring(session, item)

    @mcp.tool(name="delete_recurring", description="Deactivate a recurring item (soft, reversible).")
    def delete_recurring(item: DeleteRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.delete_recurring(session, item)
```

- [ ] **Step 6: Run, verify pass**

Run: `cd backend && uv run pytest tests/mcp/test_temporal.py -v`
Expected: PASS (2).

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/mcp backend/tests/mcp
git commit -m "feat(mcp): update_recurring + delete_recurring tools"
```

---

## Phase C — Backend: budgets assign / status

### Task 7: `BudgetLine` DTO + `list_budgets` service

**Files:**
- Modify: `backend/src/quaestor/domain/dtos.py`, `backend/src/quaestor/services/budgets.py`
- Test: `backend/tests/services/test_budgets.py`

**Interfaces:**
- Consumes: `budgets.budget_status(session, category_id, year_month) -> BudgetStatus` (exists, fields `assigned, rollover_in, spent, available, pct_used, status`); `categories.list_categories(session)`.
- Produces: `BudgetLine` dataclass (`category_id, category_name, assigned, rollover_in, spent, available, pct_used, status`); `budgets.list_budgets(session, year_month: str) -> list[BudgetLine]` — one line per budget-eligible (non-archived, `exclude_from_budget=False`) category, ordered by category id.

- [ ] **Step 1: Write failing test**

In `backend/tests/services/test_budgets.py`, append:

```python
def test_list_budgets_one_line_per_eligible_category(session):
    from quaestor.services import budgets, categories
    food = categories.create_category(session, name="Food")
    categories.create_category(session, name="Hidden", exclude_from_budget=True)
    budgets.set_budget(session, food.id, "2026-06", 500_000)
    lines = budgets.list_budgets(session, "2026-06")
    names = [l.category_name for l in lines]
    assert "Food" in names and "Hidden" not in names
    food_line = next(l for l in lines if l.category_name == "Food")
    assert food_line.assigned == 500_000
    assert food_line.category_id == food.id


def test_list_budgets_includes_unassigned_eligible_category(session):
    from quaestor.services import budgets, categories
    categories.create_category(session, name="Transport")
    lines = budgets.list_budgets(session, "2026-06")
    line = next(l for l in lines if l.category_name == "Transport")
    assert line.assigned == 0
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/services/test_budgets.py -k list_budgets -v`
Expected: FAIL — attribute missing.

- [ ] **Step 3: Add the `BudgetLine` DTO**

In `backend/src/quaestor/domain/dtos.py`, add after `BudgetStatus`:

```python
@dataclass(frozen=True)
class BudgetLine:
    category_id: int
    category_name: str
    assigned: int
    rollover_in: int
    spent: int
    available: int
    pct_used: int
    status: str  # "over" | "under"
```

- [ ] **Step 4: Implement `list_budgets`**

In `backend/src/quaestor/services/budgets.py`: add `BudgetLine` to the `from ..domain.dtos import (...)` block, add `Category` to the models import if not present, then add at the end of the file:

```python
def list_budgets(session: Session, year_month: str) -> list[BudgetLine]:
    """One envelope line per budget-eligible category for the month.

    Eligible = not archived and not excluded from budget. Unassigned categories
    appear with assigned=0 so the UI can assign to them.

    Raises:
        ValidationError: malformed year_month.
    """
    _validate_year_month(year_month)
    cats = session.exec(
        select(Category).where(
            Category.archived == False,  # noqa: E712
            Category.exclude_from_budget == False,  # noqa: E712
        ).order_by(Category.id)
    ).all()
    lines: list[BudgetLine] = []
    for cat in cats:
        st = budget_status(session, cat.id, year_month)
        lines.append(
            BudgetLine(
                category_id=cat.id,
                category_name=cat.name,
                assigned=st.assigned,
                rollover_in=st.rollover_in,
                spent=st.spent,
                available=st.available,
                pct_used=st.pct_used,
                status=st.status,
            )
        )
    return lines
```

- [ ] **Step 5: Run, verify pass**

Run: `cd backend && uv run pytest tests/services/test_budgets.py -k list_budgets -v`
Expected: PASS (2).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/domain/dtos.py backend/src/quaestor/services/budgets.py backend/tests/services/test_budgets.py
git commit -m "feat(budgets): BudgetLine DTO + list_budgets(month)"
```

---

### Task 8: Budgets routes — `GET ?month` + `PUT` assign

**Files:**
- Modify: `backend/src/quaestor/api/schemas.py`, `backend/src/quaestor/api/routers/budgets.py`
- Test: `backend/tests/api/test_budgets.py`

**Interfaces:**
- Consumes: `budgets.list_budgets`, `budgets.set_budget`, `budgets.budget_status` (services).
- Produces: schemas `BudgetLineOut`, `BudgetAssignIn`; routes `GET /budgets?month=` → `list[BudgetLineOut]`, `PUT /budgets` → `BudgetLineOut` (recomputed line).

- [ ] **Step 1: Write failing API tests**

In `backend/tests/api/test_budgets.py`, append:

```python
def _seed_category(engine, name="Food"):
    from quaestor.services import categories
    from sqlmodel import Session
    with Session(engine) as s:
        return categories.create_category(s, name=name).id


def test_list_budgets_endpoint(client, engine, auth):
    cat_id = _seed_category(engine)
    r = client.get("/api/budgets?month=2026-06", headers=auth)
    assert r.status_code == 200, r.text
    assert any(line["category_id"] == cat_id for line in r.json())


def test_put_budget_assign_is_idempotent(client, engine, auth):
    cat_id = _seed_category(engine)
    body = {"category_id": cat_id, "year_month": "2026-06", "amount_assigned": 500_000}
    r1 = client.put("/api/budgets", json=body, headers=auth)
    assert r1.status_code == 200, r1.text
    assert r1.json()["assigned"] == 500_000
    body["amount_assigned"] = 700_000
    r2 = client.put("/api/budgets", json=body, headers=auth)
    assert r2.json()["assigned"] == 700_000  # overwrite, not add
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/api/test_budgets.py -k "list_budgets_endpoint or assign" -v`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add schemas**

In `backend/src/quaestor/api/schemas.py`, add near `SafeToSpendOut`:

```python
class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str
    assigned: int
    rollover_in: int
    spent: int
    available: int
    pct_used: int
    status: str


class BudgetAssignIn(BaseModel):
    category_id: int
    year_month: str
    amount_assigned: int
```

- [ ] **Step 4: Add the routes**

In `backend/src/quaestor/api/routers/budgets.py`, update the schemas import to add `BudgetLineOut, BudgetAssignIn`, then add:

```python
@router.get("", response_model=list[BudgetLineOut])
def list_budgets(month: str, session: Session = Depends(get_session)):
    return budgets.list_budgets(session, month)


@router.put("", response_model=BudgetLineOut)
def assign_budget(body: BudgetAssignIn, session: Session = Depends(get_session)):
    budgets.set_budget(session, body.category_id, body.year_month, body.amount_assigned)
    st = budgets.budget_status(session, body.category_id, body.year_month)
    cat = session.get(Category, body.category_id)
    return BudgetLine(
        category_id=st.category_id, category_name=cat.name, assigned=st.assigned,
        rollover_in=st.rollover_in, spent=st.spent, available=st.available,
        pct_used=st.pct_used, status=st.status,
    )
```

Add the imports this route needs at the top of the router: `from ...domain.dtos import BudgetLine` and `from ...domain.models import Category`.

- [ ] **Step 5: Run, verify pass**

Run: `cd backend && uv run pytest tests/api/test_budgets.py -v`
Expected: PASS (including the pre-existing safe-to-spend test).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/api/schemas.py backend/src/quaestor/api/routers/budgets.py backend/tests/api/test_budgets.py
git commit -m "feat(api): GET /budgets?month + PUT /budgets assign (ADR-0006)"
```

---

### Task 9: Budgets MCP tool — `assign_budget` (new `planning.py`)

**Files:**
- Create: `backend/src/quaestor/mcp/tools/planning.py`
- Modify: `backend/src/quaestor/mcp/registry.py`, `backend/src/quaestor/mcp/server.py`, `backend/src/quaestor/mcp/format.py`
- Test: `backend/tests/mcp/test_planning.py`

**Interfaces:**
- Consumes: `budgets.set_budget`, `budgets.budget_status`; `core._as_text`, `core._resolve_category` (exist in `mcp/tools/core.py`).
- Produces: `mcp/tools/planning.py` with `assign_budget` impl + `AssignBudgetInput`; `format.budget_assigned(BudgetStatus, category_name)`; `register_planning_tools(mcp)` in registry; `server.py` calls it. This module also hosts the goals tools in Task 13.

- [ ] **Step 1: Write failing MCP test**

Create `backend/tests/mcp/test_planning.py`:

```python
from sqlmodel import Session

from quaestor.mcp.tools import planning
from quaestor.mcp.tools.planning import AssignBudgetInput
from quaestor.services import budgets, categories


def test_mcp_assign_budget(engine):
    with Session(engine) as s:
        cat = categories.create_category(s, name="Food")
        out = planning.assign_budget(
            s, AssignBudgetInput(category="Food", year_month="2026-06", amount=500_000)
        )
        assert "Food" in out
        assert budgets.budget_status(s, cat.id, "2026-06").assigned == 500_000
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/mcp/test_planning.py -v`
Expected: FAIL — module `planning` does not exist.

- [ ] **Step 3: Add the formatter**

In `backend/src/quaestor/mcp/format.py`, add:

```python
def budget_assigned(status, category_name: str) -> str:
    return (
        f"Assigned {category_name} envelope for {status.year_month}: "
        f"{status.assigned} (available {status.available})."
    )
```

- [ ] **Step 4: Create `planning.py`**

Create `backend/src/quaestor/mcp/tools/planning.py`:

```python
"""MCP planning tools (P4): budgets envelope assign and goals management.

Mirrors temporal.py: parse input, resolve names, call ONE service, format output.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import budgets
from .. import format
from .core import _as_text, _resolve_category


class AssignBudgetInput(BaseModel):
    category: str = Field(description="Category name to assign an envelope to")
    year_month: str = Field(description="Target month, YYYY-MM")
    amount: int = Field(ge=0, description="Amount to assign in cents (0 unassigns)")


@_as_text
def assign_budget(session: Session, inp: AssignBudgetInput) -> str:
    category = _resolve_category(session, inp.category)
    budgets.set_budget(session, category.id, inp.year_month, inp.amount)
    status = budgets.budget_status(session, category.id, inp.year_month)
    return format.budget_assigned(status, category.name)
```

- [ ] **Step 5: Wire `register_planning_tools`**

In `backend/src/quaestor/mcp/registry.py`, add `from .tools import ... planning` (extend the existing `from .tools import core, temporal` to `core, planning, temporal`), import `AssignBudgetInput` from `.tools.planning`, add a `PLANNING_TOOL_NAMES = ("assign_budget",)` tuple, and append:

```python
def register_planning_tools(mcp) -> None:
    """Register the P4 planning tools (budgets + goals) on the FastMCP instance."""

    @mcp.tool(name="assign_budget", description="Assign (set) a category envelope for a month.")
    def assign_budget(item: AssignBudgetInput) -> str:
        with Session(db.engine) as session:
            return planning.assign_budget(session, item)
```

- [ ] **Step 6: Call it from `server.py`**

In `backend/src/quaestor/mcp/server.py`, find where `register_temporal_tools(mcp)` is called and add a sibling line `register_planning_tools(mcp)` (import it alongside the existing `register_*` imports).

- [ ] **Step 7: Run, verify pass**

Run: `cd backend && uv run pytest tests/mcp/test_planning.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src/quaestor/mcp backend/tests/mcp/test_planning.py
git commit -m "feat(mcp): planning tools module + assign_budget"
```

---

## Phase D — Backend: goals CRUD + contribute + lifecycle

### Task 10: `list_goals` + `update_goal` services

**Files:**
- Modify: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py`

**Interfaces:**
- Consumes: `Goal`, `GoalStatus`, `Account`, `AccountType` models; `create_goal` validation patterns.
- Produces: `goals.list_goals(session) -> list[Goal]` (all goals, any status, ordered by id); `goals.update_goal(session, goal_id, *, name=None, monthly_amount=None, target_amount=_UNSET, deadline=_UNSET, savings_account_id=None) -> Goal`. `None`/`_UNSET` leave fields unchanged; the resulting goal must keep the both-or-neither target/deadline invariant.

- [ ] **Step 1: Write failing tests**

In `backend/tests/services/test_goals.py`, append (`_savings` helper exists in this file):

```python
def test_list_goals_returns_all_statuses(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    goals.pause_goal(session, g.id)
    goals.create_goal(session, name="B", monthly_amount=100_000, savings_account_id=sav.id)
    names = [x.name for x in goals.list_goals(session)]
    assert names == ["A", "B"]


def test_update_goal_name_and_monthly(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    out = goals.update_goal(session, g.id, name="A2", monthly_amount=150_000)
    assert out.name == "A2" and out.monthly_amount == 150_000


def test_update_goal_to_defined_requires_both(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.update_goal(session, g.id, target_amount=1_000_000)  # deadline missing


def test_update_goal_to_open_ended_clears_both(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000,
                          savings_account_id=sav.id, target_amount=1_000_000,
                          deadline=date(2026, 12, 1))
    out = goals.update_goal(session, g.id, target_amount=None, deadline=None)
    assert out.target_amount is None and out.deadline is None
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/services/test_goals.py -k "list_goals or update_goal" -v`
Expected: FAIL — attributes missing (note `pause_goal` from Task 11 is referenced; this task adds `list_goals`/`update_goal`, Task 11 adds `pause_goal`. Implement `pause_goal` stub-free by ordering: do Step 3 here, then Task 11; the `test_list_goals_returns_all_statuses` test will pass once Task 11 lands. To keep this task green on its own, temporarily skip that one test or implement `pause_goal` now — see Step 3 note).

- [ ] **Step 3: Implement `list_goals` + `update_goal` (and `pause_goal` to keep tests green)**

In `backend/src/quaestor/services/goals.py`, add a sentinel near the imports:

```python
_UNSET = object()
```

Add the functions:

```python
def list_goals(session: Session) -> list[Goal]:
    """All goals (any status), ordered by id, for management UIs."""
    return list(session.exec(select(Goal).order_by(Goal.id)).all())


def update_goal(
    session: Session,
    goal_id: int,
    *,
    name: str | None = None,
    monthly_amount: int | None = None,
    target_amount=_UNSET,
    deadline=_UNSET,
    savings_account_id: int | None = None,
) -> Goal:
    """Edit a goal, preserving the defined/open-ended invariant (target+deadline
    both set or both null).

    Raises:
        NotFound: the goal does not exist.
        ValidationError: monthly_amount <= 0; resulting target/deadline not both-or-
            neither; target_amount <= 0; savings account missing/not-savings/archived.
    """
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise NotFound(f"goal {goal_id} not found")
    if name is not None:
        goal.name = name
    if monthly_amount is not None:
        if monthly_amount <= 0:
            raise ValidationError("monthly_amount must be > 0")
        goal.monthly_amount = monthly_amount
    new_target = goal.target_amount if target_amount is _UNSET else target_amount
    new_deadline = goal.deadline if deadline is _UNSET else deadline
    if (new_target is None) != (new_deadline is None):
        raise ValidationError(
            "a defined goal needs both target_amount and deadline; "
            "an open-ended goal needs neither"
        )
    if new_target is not None and new_target <= 0:
        raise ValidationError("target_amount must be > 0")
    goal.target_amount = new_target
    goal.deadline = new_deadline
    if savings_account_id is not None:
        acc = session.get(Account, savings_account_id)
        if acc is None:
            raise ValidationError(f"savings account {savings_account_id} does not exist")
        if acc.type != AccountType.savings:
            raise ValidationError(f"account {savings_account_id} is not a savings account")
        if acc.archived:
            raise ValidationError(f"savings account {savings_account_id} is archived")
        goal.savings_account_id = savings_account_id
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal
```

Note: `pause_goal`/`restore_goal` land in Task 11. If executing strictly task-by-task and you want this task fully green, implement Task 11's `pause_goal`/`restore_goal` now (they are 6 lines) or mark `test_list_goals_returns_all_statuses` with `@pytest.mark.skip(reason="pause_goal lands in Task 11")` and remove the skip in Task 11.

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && uv run pytest tests/services/test_goals.py -k "update_goal" -v`
Expected: PASS (3 update tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(goals): list_goals + update_goal (invariant-preserving)"
```

---

### Task 11: `pause_goal` + `restore_goal` services

**Files:**
- Modify: `backend/src/quaestor/services/goals.py`
- Test: `backend/tests/services/test_goals.py`

**Interfaces:**
- Consumes: `Goal`, `GoalStatus`; `_maybe_mark_reached(session, goal)` (exists).
- Produces: `goals.pause_goal(session, goal_id) -> Goal` (`status=paused`); `goals.restore_goal(session, goal_id) -> Goal` (`status=active`, then re-evaluates reached). Both raise `NotFound`.

- [ ] **Step 1: Write failing tests**

In `backend/tests/services/test_goals.py`, append:

```python
def test_pause_then_restore_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    assert goals.pause_goal(session, g.id).status == GoalStatus.paused
    # paused goal drops out of active progress
    assert goals.goals_progress(session) == []
    assert goals.restore_goal(session, g.id).status == GoalStatus.active


def test_pause_goal_not_found(session):
    from quaestor.domain.errors import NotFound
    with pytest.raises(NotFound):
        goals.pause_goal(session, 999)
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/services/test_goals.py -k "pause or restore_goal" -v`
Expected: FAIL — attribute missing.

- [ ] **Step 3: Implement both**

In `backend/src/quaestor/services/goals.py`, add:

```python
def pause_goal(session: Session, goal_id: int) -> Goal:
    """Soft-delete: pause a goal (drops out of active progress; contributions stay).

    Raises:
        NotFound: the goal does not exist.
    """
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise NotFound(f"goal {goal_id} not found")
    goal.status = GoalStatus.paused
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def restore_goal(session: Session, goal_id: int) -> Goal:
    """Re-activate a paused goal. Re-evaluates reached. No-op if already active.

    Raises:
        NotFound: the goal does not exist.
    """
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise NotFound(f"goal {goal_id} not found")
    goal.status = GoalStatus.active
    _maybe_mark_reached(session, goal)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal
```

If you added a skip marker in Task 10, remove it now and re-run `test_list_goals_returns_all_statuses`.

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && uv run pytest tests/services/test_goals.py -v`
Expected: PASS (all goals service tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/goals.py backend/tests/services/test_goals.py
git commit -m "feat(goals): pause/restore (soft-delete, ADR-0005)"
```

---

### Task 12: Goals routes — list / create / patch / delete / contribute / restore

**Files:**
- Modify: `backend/src/quaestor/api/schemas.py`, `backend/src/quaestor/api/routers/goals.py`
- Test: `backend/tests/api/test_goals.py`

**Interfaces:**
- Consumes: `goals.list_goals`, `create_goal`, `update_goal`, `pause_goal`, `restore_goal`, `goal_contribution` (services); `settings.update_settings` for seeding default source in tests.
- Produces: schemas `GoalOut`, `GoalCreate`, `GoalUpdate`, `GoalContributeIn`, `GoalContributionOut`; routes `GET /goals`, `POST /goals` (201), `PATCH /goals/{id}`, `DELETE /goals/{id}` (204), `POST /goals/{id}/contribute` (201), `POST /goals/{id}/restore`.

- [ ] **Step 1: Write failing API tests**

In `backend/tests/api/test_goals.py`, append:

```python
def _seed_savings(engine):
    from quaestor.services import accounts
    from quaestor.domain.models import AccountType
    from sqlmodel import Session
    with Session(engine) as s:
        return accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0).id


def test_create_list_goal(client, engine, auth):
    sid = _seed_savings(engine)
    body = {"name": "Trip", "monthly_amount": 200_000, "savings_account_id": sid}
    r = client.post("/api/goals", json=body, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"
    assert any(g["name"] == "Trip" for g in client.get("/api/goals", headers=auth).json())


def test_patch_goal(client, engine, auth):
    sid = _seed_savings(engine)
    gid = client.post("/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid}, headers=auth).json()["id"]
    r = client.patch(f"/api/goals/{gid}", json={"monthly_amount": 150_000}, headers=auth)
    assert r.status_code == 200 and r.json()["monthly_amount"] == 150_000


def test_delete_then_restore_goal(client, engine, auth):
    sid = _seed_savings(engine)
    gid = client.post("/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid}, headers=auth).json()["id"]
    assert client.delete(f"/api/goals/{gid}", headers=auth).status_code == 204
    assert client.post(f"/api/goals/{gid}/restore", headers=auth).json()["status"] == "active"


def test_contribute_requires_default_source_is_422(client, engine, auth):
    sid = _seed_savings(engine)
    gid = client.post("/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sid}, headers=auth).json()["id"]
    # no default source account configured -> 422
    r = client.post(f"/api/goals/{gid}/contribute", json={"amount": 50_000, "date": "2026-06-01"}, headers=auth)
    assert r.status_code == 422


def test_contribute_succeeds_with_default_source(client, engine, auth):
    from quaestor.services import accounts, settings
    from quaestor.domain.models import AccountType
    from sqlmodel import Session
    with Session(engine) as s:
        src = accounts.create_account(s, "Checking", AccountType.savings, "COP", balance=1_000_000)
        sav = accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0)
        settings.update_settings(s, default_source_account_id=src.id)
        sav_id = sav.id
    gid = client.post("/api/goals", json={"name": "A", "monthly_amount": 100_000, "savings_account_id": sav_id}, headers=auth).json()["id"]
    r = client.post(f"/api/goals/{gid}/contribute", json={"amount": 50_000, "date": "2026-06-01"}, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["goal_id"] == gid
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/api/test_goals.py -k "create_list_goal or patch_goal or restore_goal or contribute" -v`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add schemas**

In `backend/src/quaestor/api/schemas.py`, add near `GoalProgressOut`:

```python
class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    target_amount: int | None
    deadline: Date | None
    monthly_amount: int
    savings_account_id: int
    status: str


class GoalCreate(BaseModel):
    name: str
    monthly_amount: int
    savings_account_id: int
    target_amount: int | None = None
    deadline: Date | None = None


class GoalUpdate(BaseModel):
    name: str | None = None
    monthly_amount: int | None = None
    target_amount: int | None = None
    deadline: Date | None = None
    savings_account_id: int | None = None


class GoalContributeIn(BaseModel):
    amount: int
    date: Date


class GoalContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    date: Date
    amount: int
    source: str
    transaction_id: int | None
```

- [ ] **Step 4: Rewrite the goals router**

Replace `backend/src/quaestor/api/routers/goals.py` with:

```python
"""Goals REST router — thin adapter over services.goals."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...services import goals
from ..deps import get_session
from ..schemas import (
    GoalContributeIn,
    GoalContributionOut,
    GoalCreate,
    GoalOut,
    GoalProgressOut,
    GoalUpdate,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/progress", response_model=list[GoalProgressOut])
def goals_progress(session: Session = Depends(get_session)):
    return goals.goals_progress(session)


@router.get("", response_model=list[GoalOut])
def list_goals(session: Session = Depends(get_session)):
    return goals.list_goals(session)


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(body: GoalCreate, session: Session = Depends(get_session)):
    return goals.create_goal(
        session,
        name=body.name,
        monthly_amount=body.monthly_amount,
        savings_account_id=body.savings_account_id,
        target_amount=body.target_amount,
        deadline=body.deadline,
    )


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, body: GoalUpdate, session: Session = Depends(get_session)):
    fields = body.model_dump(exclude_unset=True)
    return goals.update_goal(session, goal_id, **fields)


@router.delete("/{goal_id}", status_code=204)
def pause_goal(goal_id: int, session: Session = Depends(get_session)):
    goals.pause_goal(session, goal_id)
    return None


@router.post("/{goal_id}/contribute", response_model=GoalContributionOut, status_code=201)
def contribute(goal_id: int, body: GoalContributeIn, session: Session = Depends(get_session)):
    return goals.goal_contribution(session, goal_id, body.amount, body.date)


@router.post("/{goal_id}/restore", response_model=GoalOut)
def restore_goal(goal_id: int, session: Session = Depends(get_session)):
    return goals.restore_goal(session, goal_id)
```

Note: `GET /progress` is declared before `GET ""` so the static segment wins; `POST ""` (create) and `POST /{goal_id}/contribute` do not collide.

- [ ] **Step 5: Run, verify pass**

Run: `cd backend && uv run pytest tests/api/test_goals.py -v`
Expected: PASS (including the pre-existing `/progress` test).

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/api/schemas.py backend/src/quaestor/api/routers/goals.py backend/tests/api/test_goals.py
git commit -m "feat(api): goals CRUD + contribute + restore routes (ADR-0006)"
```

---

### Task 13: Goals MCP tools — create / update / contribute / pause / restore

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/planning.py`, `backend/src/quaestor/mcp/registry.py`, `backend/src/quaestor/mcp/format.py`
- Test: `backend/tests/mcp/test_planning.py`

**Interfaces:**
- Consumes: `goals.create_goal`, `update_goal`, `goal_contribution`, `pause_goal`, `restore_goal`; `core._resolve_account` (exists).
- Produces: tools `create_goal`, `update_goal`, `contribute_goal`, `pause_goal`, `restore_goal`; input models in `planning.py`; formatters `format.goal_saved`, `format.goal_contribution_recorded`.

- [ ] **Step 1: Write failing MCP tests**

In `backend/tests/mcp/test_planning.py`, append:

```python
def test_mcp_create_goal(engine):
    from quaestor.mcp.tools.planning import CreateGoalInput
    from quaestor.services import accounts
    from quaestor.domain.models import AccountType
    with Session(engine) as s:
        accounts.create_account(s, "Savings", AccountType.savings, "COP", balance=0)
        out = planning.create_goal(s, CreateGoalInput(name="Trip", monthly_amount=200_000, savings_account="Savings"))
        assert "Trip" in out
        from quaestor.services import goals
        assert [g.name for g in goals.list_goals(s)] == ["Trip"]
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && uv run pytest tests/mcp/test_planning.py -k create_goal -v`
Expected: FAIL — `ImportError: CreateGoalInput`.

- [ ] **Step 3: Add formatters**

In `backend/src/quaestor/mcp/format.py`, add:

```python
def goal_saved(goal) -> str:
    kind = "defined" if goal.target_amount is not None else "open-ended"
    return f"Goal '{goal.name}' (id {goal.id}, {kind}, {goal.status.value}), monthly {goal.monthly_amount}."


def goal_contribution_recorded(contribution) -> str:
    return f"Recorded {contribution.amount} contribution to goal {contribution.goal_id}."
```

- [ ] **Step 4: Add input models + impls to `planning.py`**

In `backend/src/quaestor/mcp/tools/planning.py`, extend the imports (`from ...services import budgets, goals`, and `from .core import _as_text, _resolve_account, _resolve_category`), and add:

```python
class CreateGoalInput(BaseModel):
    name: str = Field(description="Goal name, e.g. 'Trip'")
    monthly_amount: int = Field(gt=0, description="Fixed monthly amount in cents")
    savings_account: str = Field(description="Savings account name to hold the goal")
    target_amount: int | None = Field(default=None, description="Target in cents (defined goal)")
    deadline: str | None = Field(default=None, description="Deadline YYYY-MM-DD (defined goal)")


class UpdateGoalInput(BaseModel):
    goal_id: int = Field(description="The goal id")
    name: str | None = Field(default=None, description="New name")
    monthly_amount: int | None = Field(default=None, gt=0, description="New monthly amount in cents")


class ContributeGoalInput(BaseModel):
    goal_id: int = Field(description="The goal id")
    amount: int = Field(gt=0, description="Contribution amount in cents")
    date: str = Field(description="Contribution date YYYY-MM-DD")


class GoalIdInput(BaseModel):
    goal_id: int = Field(description="The goal id")


@_as_text
def create_goal(session: Session, inp: CreateGoalInput) -> str:
    from datetime import date as _date
    account = _resolve_account(session, inp.savings_account)
    deadline = _date.fromisoformat(inp.deadline) if inp.deadline else None
    goal = goals.create_goal(
        session, name=inp.name, monthly_amount=inp.monthly_amount,
        savings_account_id=account.id, target_amount=inp.target_amount, deadline=deadline,
    )
    return format.goal_saved(goal)


@_as_text
def update_goal(session: Session, inp: UpdateGoalInput) -> str:
    fields = inp.model_dump(exclude_unset=True, exclude={"goal_id"})
    goal = goals.update_goal(session, inp.goal_id, **fields)
    return format.goal_saved(goal)


@_as_text
def contribute_goal(session: Session, inp: ContributeGoalInput) -> str:
    from datetime import date as _date
    contribution = goals.goal_contribution(session, inp.goal_id, inp.amount, _date.fromisoformat(inp.date))
    return format.goal_contribution_recorded(contribution)


@_as_text
def pause_goal(session: Session, inp: GoalIdInput) -> str:
    return format.goal_saved(goals.pause_goal(session, inp.goal_id))


@_as_text
def restore_goal(session: Session, inp: GoalIdInput) -> str:
    return format.goal_saved(goals.restore_goal(session, inp.goal_id))
```

- [ ] **Step 5: Register the tools**

In `backend/src/quaestor/mcp/registry.py`, import the new input models from `.tools.planning`, extend `PLANNING_TOOL_NAMES` to `("assign_budget", "create_goal", "update_goal", "contribute_goal", "pause_goal", "restore_goal")`, and inside `register_planning_tools` add:

```python
    @mcp.tool(name="create_goal", description="Create a savings goal (defined or open-ended).")
    def create_goal(item: CreateGoalInput) -> str:
        with Session(db.engine) as session:
            return planning.create_goal(session, item)

    @mcp.tool(name="update_goal", description="Edit a goal's name or monthly amount.")
    def update_goal(item: UpdateGoalInput) -> str:
        with Session(db.engine) as session:
            return planning.update_goal(session, item)

    @mcp.tool(name="contribute_goal", description="Record a manual contribution to a goal.")
    def contribute_goal(item: ContributeGoalInput) -> str:
        with Session(db.engine) as session:
            return planning.contribute_goal(session, item)

    @mcp.tool(name="pause_goal", description="Pause a goal (soft-delete, reversible).")
    def pause_goal(item: GoalIdInput) -> str:
        with Session(db.engine) as session:
            return planning.pause_goal(session, item)

    @mcp.tool(name="restore_goal", description="Restore a paused goal.")
    def restore_goal(item: GoalIdInput) -> str:
        with Session(db.engine) as session:
            return planning.restore_goal(session, item)
```

- [ ] **Step 6: Run, verify pass; run the full backend suite**

Run: `cd backend && uv run pytest tests/mcp/test_planning.py -v && uv run pytest`
Expected: PASS (planning tests + whole suite green).

- [ ] **Step 7: Commit**

```bash
git add backend/src/quaestor/mcp backend/tests/mcp/test_planning.py
git commit -m "feat(mcp): goals tools (create/update/contribute/pause/restore)"
```

---

## Phase E — Frontend: API client + query keys

### Task 14: Extend `lib/api.ts` with Phase 2 types + methods

**Files:**
- Modify: `frontend/lib/api.ts`
- Verify: `frontend/` `pnpm exec tsc --noEmit && pnpm lint`

**Interfaces:**
- Consumes: existing `request`, `qs`, `Recurring`, `GoalProgress`, `SafeToSpend` (in this file).
- Produces: interfaces `Goal`, `GoalContribution`, `BudgetLine`; payload types `GoalCreate`, `GoalUpdate`, `GoalContributeBody`, `RecurringUpdate`, `BudgetAssign`; `api` methods `listGoals`, `createGoal`, `updateGoal`, `pauseGoal`, `restoreGoal`, `contributeGoal`, `listBudgets`, `assignBudget`, `updateRecurring`, `deleteRecurring`, `restoreRecurring`, `restoreAccount`, `restoreCategory`, `restoreCategoryGroup`.

- [ ] **Step 1: Add the types**

In `frontend/lib/api.ts`, add near the other interfaces:

```typescript
export type GoalStatus = "active" | "reached" | "paused";

export interface Goal {
  id: number;
  name: string;
  target_amount: number | null;
  deadline: string | null;
  monthly_amount: number;
  savings_account_id: number;
  status: GoalStatus;
}

export interface GoalContribution {
  id: number;
  goal_id: number;
  date: string;
  amount: number;
  source: string;
  transaction_id: number | null;
}

export interface BudgetLine {
  category_id: number;
  category_name: string;
  assigned: number;
  rollover_in: number;
  spent: number;
  available: number;
  pct_used: number;
  status: string;
}

export interface GoalCreate {
  name: string;
  monthly_amount: number;
  savings_account_id: number;
  target_amount?: number | null;
  deadline?: string | null;
}
export interface GoalUpdate {
  name?: string;
  monthly_amount?: number;
  target_amount?: number | null;
  deadline?: string | null;
  savings_account_id?: number;
}
export interface GoalContributeBody {
  amount: number;
  date: string;
}
export interface RecurringUpdate {
  name?: string;
  payee?: string;
  mode?: RecurringMode;
  amount?: number;
  category_id?: number | null;
  account_id?: number;
  interval_unit?: IntervalUnit;
  interval_count?: number;
  start_date?: string;
  end_date?: string | null;
}
export interface BudgetAssign {
  category_id: number;
  year_month: string;
  amount_assigned: number;
}
```

- [ ] **Step 2: Add the methods**

In the `api` object in `frontend/lib/api.ts`, add to the relevant sections:

```typescript
  // recurring (Phase 2)
  updateRecurring: (id: number, body: RecurringUpdate) =>
    request<Recurring>(`/recurring/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRecurring: (id: number) => request<void>(`/recurring/${id}`, { method: "DELETE" }),
  restoreRecurring: (id: number) =>
    request<Recurring>(`/recurring/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),

  // goals (Phase 2)
  listGoals: () => request<Goal[]>("/goals"),
  createGoal: (body: GoalCreate) =>
    request<Goal>("/goals", { method: "POST", body: JSON.stringify(body) }),
  updateGoal: (id: number, body: GoalUpdate) =>
    request<Goal>(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  pauseGoal: (id: number) => request<void>(`/goals/${id}`, { method: "DELETE" }),
  restoreGoal: (id: number) =>
    request<Goal>(`/goals/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
  contributeGoal: (id: number, body: GoalContributeBody) =>
    request<GoalContribution>(`/goals/${id}/contribute`, { method: "POST", body: JSON.stringify(body) }),

  // budgets (Phase 2)
  listBudgets: (month: string) => request<BudgetLine[]>(`/budgets${qs({ month })}`),
  assignBudget: (body: BudgetAssign) =>
    request<BudgetLine>("/budgets", { method: "PUT", body: JSON.stringify(body) }),

  // masters restore (Phase 2)
  restoreAccount: (id: number) =>
    request<Account>(`/accounts/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
  restoreCategory: (id: number) =>
    request<Category>(`/categories/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
  restoreCategoryGroup: (id: number) =>
    request<CategoryGroup>(`/category-groups/${id}/restore`, { method: "POST", body: JSON.stringify({}) }),
```

- [ ] **Step 3: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat(frontend): api client Phase 2 methods (goals/budgets/recurring/restore)"
```

---

### Task 15: Query keys + invalidation for Phase 2

**Files:**
- Modify: `frontend/lib/query.ts`
- Verify: `frontend/` typecheck + lint

**Interfaces:**
- Produces: `qk.goals()`, `qk.budgets(month)`; `INVALIDATION.goalWrite`, `INVALIDATION.budgetWrite`. Recurring/master writes reuse existing groups (`recurringWrite`, `accountWrite`, `categoryWrite`, `categoryGroupWrite`).

- [ ] **Step 1: Add query keys**

In `frontend/lib/query.ts`, inside the `qk` object add:

```typescript
  goals: () => ["goals", "list"] as const,
  budgets: (month: string) => ["budgets", "lines", month] as const,
```

- [ ] **Step 2: Add invalidation groups**

In the `INVALIDATION` object add:

```typescript
  goalWrite: [["goals"], ["accounts"], ["transactions"], ["reports"]],
  budgetWrite: [["budgets"], ["reports"]],
```

- [ ] **Step 3: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/query.ts
git commit -m "feat(frontend): goalWrite/budgetWrite invalidation + goals/budgets query keys"
```

---

## Phase F — Frontend: pages

### Task 16: `StatusBadge` goal status variant

**Files:**
- Modify: `frontend/components/status-badge.tsx`
- Verify: typecheck + lint

**Interfaces:**
- Produces: `StatusBadge` accepts `kind="goal"` mapping `active`→"Activa"(secondary), `reached`→"Cumplida"(secondary), `paused`→"Pausada"(ghost).

- [ ] **Step 1: Extend the component**

In `frontend/components/status-badge.tsx`, add a `GOAL` map after `MODE`:

```typescript
const GOAL: Record<string, { label: string; variant: Variant }> = {
  active: { label: "Activa", variant: "secondary" },
  reached: { label: "Cumplida", variant: "secondary" },
  paused: { label: "Pausada", variant: "ghost" },
};
```

Widen the `kind` union to include `"goal"` and add a branch in the body:

```typescript
  } else if (kind === "goal") {
    const m = GOAL[String(value)];
    if (m) ({ label, variant } = m);
  }
```

(The `kind` prop type becomes `"tx" | "mode" | "archived" | "onTrack" | "goal"`.)

- [ ] **Step 2: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/status-badge.tsx
git commit -m "feat(frontend): StatusBadge goal status variant"
```

---

### Task 17: `/recurring` — edit / delete / restore + show-inactive filter

**Files:**
- Modify: `frontend/app/(app)/recurring/page.tsx`
- Verify: typecheck + lint + manual smoke

**Interfaces:**
- Consumes: `api.updateRecurring`, `deleteRecurring`, `restoreRecurring`, `listRecurring(active?)`; `ConfirmDialog`; `invalidate(qc, "recurringWrite")`.

- [ ] **Step 1: Add edit/delete/restore + filter to the page**

Apply these changes to `frontend/app/(app)/recurring/page.tsx`:

1. Add `ConfirmDialog` to the imports: `import { ConfirmDialog } from "@/components/confirm-dialog";`.
2. Add state: `const [showInactive, setShowInactive] = useState(false);`, `const [editing, setEditing] = useState<Recurring | null>(null);`, `const [deleting, setDeleting] = useState<Recurring | null>(null);`.
3. Change the list query to honor the filter:

```typescript
  const list = useQuery({
    queryKey: qk.recurring(showInactive ? undefined : true),
    queryFn: () => api.listRecurring(showInactive ? undefined : true),
  });
```

4. Add an "Mostrar inactivos" checkbox under the `PageHeader` (mirror the accounts page checkbox):

```tsx
      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
        <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
        Mostrar inactivos
      </label>
```

5. Add the mutations:

```typescript
  const update = useMutation({
    mutationFn: () =>
      api.updateRecurring(editing!.id, {
        name, amount: amount ?? undefined, payee: payee || undefined,
        category_id: categoryId, account_id: accountId ?? undefined,
        mode: mode as RecurringMode, interval_unit: unit as IntervalUnit,
        interval_count: count ?? 1, start_date: startDate || undefined,
        end_date: endDate || null,
      }),
    onSuccess: () => { done("Recurrente actualizado"); setEditing(null); },
    onError: onErr,
  });
  const remove = useMutation({
    mutationFn: () => api.deleteRecurring(deleting!.id),
    onSuccess: () => { done("Recurrente desactivado"); setDeleting(null); },
    onError: onErr,
  });
  const restore = useMutation({
    mutationFn: (r: Recurring) => api.restoreRecurring(r.id),
    onSuccess: () => done("Recurrente restaurado"),
    onError: onErr,
  });
```

6. In the row actions cell, replace the single "Omitir" button with conditional actions:

```tsx
                  <td className="px-3 py-2.5 text-right">
                    {r.active ? (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => {
                          setEditing(r); setName(r.name); setPayee(r.payee); setType(r.type);
                          setMode(r.mode); setAccountId(r.account_id); setCategoryId(r.category_id);
                          setAmount(r.amount); setUnit(r.interval_unit); setCount(r.interval_count);
                          setStartDate(r.start_date); setEndDate(r.end_date ?? "");
                        }}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setSkipping(r)}>Omitir</Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleting(r)}>Eliminar</Button>
                      </div>
                    ) : (
                      <Button variant="ghost" size="sm" onClick={() => restore.mutate(r)} disabled={restore.isPending}>Restaurar</Button>
                    )}
                  </td>
```

7. Add an inactive indicator next to the name cell: in the name `<td>`, append `{!r.active && <StatusBadge kind="archived" value={true} />}` (shows "Archivado" as the inactive marker).

8. Reuse the existing create `<Dialog>` form for editing. Add a parallel edit dialog after the create dialog that submits `update.mutate()` instead of `create.mutate()`:

```tsx
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Editar recurrente</DialogTitle>
          <form onSubmit={(e) => { e.preventDefault(); if (!invalid) update.mutate(); }} className="space-y-4">
            <div className="space-y-1.5"><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Tipo (no editable)</Label><Select value={type} onValueChange={() => {}} items={TYPE_ITEMS} disabled /></div>
              <div className="space-y-1.5"><Label>Modo *</Label><Select value={mode} onValueChange={setMode} items={MODE_ITEMS} /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta *</Label>
              <EntitySelect value={accountId} onChange={setAccountId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
            </div>
            <div className="space-y-1.5"><Label>Monto * ({currency})</Label><MoneyInput currency={currency} value={amount} onChange={setAmount} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Cada (cantidad) *</Label>
                <Input type="number" min={1} value={count === null ? "" : String(count)} onChange={(e) => setCount(e.target.value === "" ? null : Number(e.target.value))} />
              </div>
              <div className="space-y-1.5"><Label>Unidad *</Label><Select value={unit} onValueChange={setUnit} items={UNIT_ITEMS} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Inicio *</Label><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Fin (opcional)</Label><Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect value={categoryId} onChange={setCategoryId} queryKey={qk.categories(false)} queryFn={() => api.listCategories(false)} allowNullLabel="Sin categoría" />
            </div>
            <div className="space-y-1.5"><Label>Beneficiario</Label><Input value={payee} onChange={(e) => setPayee(e.target.value)} /></div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setEditing(null)}>Cancelar</Button>
              <Button type="submit" disabled={invalid || update.isPending}>{update.isPending ? "…" : "Guardar"}</Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Eliminar recurrente"
        description={`Se desactivará "${deleting?.name}". Las ocurrencias ya registradas se mantienen. Puedes restaurarlo luego.`}
        confirmLabel="Eliminar"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate()}
      />
```

9. Remove the `Phase2Banner` import and its `<Phase2Banner>…</Phase2Banner>` usage.

- [ ] **Step 2: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 3: Manual smoke**

With the backend running and `pnpm dev`: create a recurring item, edit its amount (verify persisted), delete it (toggle "Mostrar inactivos" to see it with the inactive badge), restore it. Confirm the Phase-2 banner is gone.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(app\)/recurring/page.tsx
git commit -m "feat(frontend): /recurring edit/delete/restore + show-inactive"
```

---

### Task 18: `/budgets` — per-category assign + envelope status

**Files:**
- Modify: `frontend/app/(app)/budgets/page.tsx`
- Verify: typecheck + lint + manual smoke

**Interfaces:**
- Consumes: `api.listBudgets(month)`, `api.assignBudget`, `qk.budgets(month)`, `invalidate(qc, "budgetWrite")`, `MoneyInput`, `formatCents`.

- [ ] **Step 1: Replace the read-only envelope table with an assignable one**

Edit `frontend/app/(app)/budgets/page.tsx`:

1. Add imports: `useMutation, useQueryClient` from react-query; `invalidate` from `@/lib/query`; `toast` from `sonner`; `ApiError` from `@/lib/api`; `MoneyInput` from `@/components/money-input`; `Button` from `@/ui`. Remove `Phase2Banner`.
2. Add `const qc = useQueryClient();` and a budgets query:

```typescript
  const lines = useQuery({ queryKey: qk.budgets(month), queryFn: () => api.listBudgets(month) });
```

3. Add inline assign state + mutation:

```typescript
  const [editingCat, setEditingCat] = useState<number | null>(null);
  const [draft, setDraft] = useState<number | null>(null);
  const assign = useMutation({
    mutationFn: (categoryId: number) =>
      api.assignBudget({ category_id: categoryId, year_month: month, amount_assigned: draft ?? 0 }),
    onSuccess: () => {
      toast.success("Sobre asignado");
      invalidate(qc, "budgetWrite");
      setEditingCat(null); setDraft(null);
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  });
```

4. Replace the `report.data` envelopes block with a `lines.data` table that renders, per line, the assigned amount with an inline "Asignar" affordance (a `MoneyInput` + save button when `editingCat === line.category_id`, else the formatted value + an "Asignar" button):

```tsx
      {lines.data && lines.data.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>Sobres</h2>
          <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--muted-foreground)" }}>
                  <th className="px-3 py-2.5 text-left text-xs font-medium">Categoría</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Asignado</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Gastado</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium">Disponible</th>
                  <th className="w-32 px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {lines.data.map((l) => (
                  <tr key={l.category_id} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <td className="px-3 py-2.5">{l.category_name}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--muted-foreground)" }}>
                      {editingCat === l.category_id
                        ? <MoneyInput currency="COP" value={draft} onChange={setDraft} />
                        : formatCents(l.assigned, "COP")}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: "var(--muted-foreground)" }}>{formatCents(l.spent, "COP")}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-medium" style={{ color: l.status === "over" ? "var(--expense)" : "var(--income)" }}>
                      {formatCents(l.available, "COP")}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {editingCat === l.category_id ? (
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => { setEditingCat(null); setDraft(null); }}>Cancelar</Button>
                          <Button size="sm" disabled={assign.isPending} onClick={() => assign.mutate(l.category_id)}>Guardar</Button>
                        </div>
                      ) : (
                        <Button variant="ghost" size="sm" onClick={() => { setEditingCat(l.category_id); setDraft(l.assigned); }}>Asignar</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
```

5. Remove the old `report` query and its envelope table (the new `lines` table supersedes it). Keep the safe-to-spend card as is.
6. Remove the `Phase2Banner` usage.

- [ ] **Step 2: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 3: Manual smoke**

Backend running + `pnpm dev`: pick a month, click "Asignar" on a category, enter an amount, save → the assigned/available columns and the safe-to-spend card update. Re-assign a different amount → it overwrites (not adds). Banner gone.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(app\)/budgets/page.tsx
git commit -m "feat(frontend): /budgets per-category envelope assign"
```

---

### Task 19: `/goals` — management (create / edit / pause / restore / contribute)

**Files:**
- Modify: `frontend/app/(app)/goals/page.tsx`
- Verify: typecheck + lint + manual smoke

**Interfaces:**
- Consumes: `api.listGoals`, `createGoal`, `updateGoal`, `pauseGoal`, `restoreGoal`, `contributeGoal`, `goalsProgress`; `EntitySelect` (savings account), `MoneyInput`, `ConfirmDialog`, `StatusBadge` (`kind="goal"`), `invalidate(qc, "goalWrite")`.

- [ ] **Step 1: Rewrite the goals page as a management view**

Replace `frontend/app/(app)/goals/page.tsx` with:

```tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Goal } from "@/lib/api";
import { qk, invalidate } from "@/lib/query";
import { formatCents } from "@/lib/money";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { MoneyInput } from "@/components/money-input";
import { EntitySelect } from "@/components/entity-select";
import { Dialog, DialogPopup, DialogTitle, Input, Label, Button } from "@/ui";

export default function GoalsPage() {
  const qc = useQueryClient();
  const goals = useQuery({ queryKey: qk.goals(), queryFn: () => api.listGoals() });
  const progress = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => api.goalsProgress() });

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [pausing, setPausing] = useState<Goal | null>(null);
  const [contributing, setContributing] = useState<Goal | null>(null);

  const [name, setName] = useState("");
  const [monthly, setMonthly] = useState<number | null>(null);
  const [savingsId, setSavingsId] = useState<number | null>(null);
  const [target, setTarget] = useState<number | null>(null);
  const [deadline, setDeadline] = useState("");
  const [amount, setAmount] = useState<number | null>(null);
  const [date, setDate] = useState("");

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error");
  const done = (msg: string) => { toast.success(msg); invalidate(qc, "goalWrite"); };
  const resetForm = () => { setName(""); setMonthly(null); setSavingsId(null); setTarget(null); setDeadline(""); };

  const create = useMutation({
    mutationFn: () => api.createGoal({
      name, monthly_amount: monthly!, savings_account_id: savingsId!,
      target_amount: target, deadline: deadline || null,
    }),
    onSuccess: () => { done("Meta creada"); setCreating(false); resetForm(); },
    onError: onErr,
  });
  const update = useMutation({
    mutationFn: () => api.updateGoal(editing!.id, {
      name, monthly_amount: monthly ?? undefined,
      target_amount: target, deadline: deadline || null, savings_account_id: savingsId ?? undefined,
    }),
    onSuccess: () => { done("Meta actualizada"); setEditing(null); resetForm(); },
    onError: onErr,
  });
  const pause = useMutation({
    mutationFn: () => api.pauseGoal(pausing!.id),
    onSuccess: () => { done("Meta pausada"); setPausing(null); },
    onError: onErr,
  });
  const restore = useMutation({
    mutationFn: (g: Goal) => api.restoreGoal(g.id),
    onSuccess: () => done("Meta restaurada"),
    onError: onErr,
  });
  const contribute = useMutation({
    mutationFn: () => api.contributeGoal(contributing!.id, { amount: amount!, date }),
    onSuccess: () => { done("Aporte registrado"); setContributing(null); setAmount(null); setDate(""); },
    onError: onErr,
  });

  const createInvalid = !name || monthly === null || savingsId === null || (!!target !== !!deadline);
  const editInvalid = !name || (!!target !== !!deadline);

  const savedFor = (id: number) => progress.data?.find((p) => p.goal_id === id);

  return (
    <div className="space-y-6">
      <PageHeader title="Metas" action={<Button onClick={() => { resetForm(); setCreating(true); }}>Nueva</Button>} />

      {goals.isError && <ErrorState message="No se pudieron cargar las metas" onRetry={() => goals.refetch()} />}
      {goals.data && goals.data.length === 0 && <EmptyState message="Sin metas" />}

      {goals.data && goals.data.length > 0 && (
        <div className="space-y-3">
          {goals.data.map((g) => {
            const p = savedFor(g.id);
            const pct = g.target_amount && p ? Math.min(100, Math.round((p.saved / g.target_amount) * 100)) : null;
            return (
              <div key={g.id} className="space-y-3 rounded-lg border p-5" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 font-medium">{g.name} <StatusBadge kind="goal" value={g.status} /></span>
                  <div className="flex gap-1">
                    {g.status === "paused" ? (
                      <Button variant="ghost" size="sm" disabled={restore.isPending} onClick={() => restore.mutate(g)}>Restaurar</Button>
                    ) : (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => { setContributing(g); setAmount(null); setDate(""); }}>Aportar</Button>
                        <Button variant="ghost" size="sm" onClick={() => {
                          setEditing(g); setName(g.name); setMonthly(g.monthly_amount);
                          setSavingsId(g.savings_account_id); setTarget(g.target_amount); setDeadline(g.deadline ?? "");
                        }}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setPausing(g)}>Pausar</Button>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(p?.saved ?? 0, "COP")}{g.target_amount !== null && ` / ${formatCents(g.target_amount, "COP")}`}
                  </span>
                  {pct !== null && <span className="tabular-nums">{pct}%</span>}
                </div>
                {pct !== null && (
                  <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--muted)" }}>
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "var(--foreground)" }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Create / edit dialog (shared fields) */}
      <Dialog open={creating || editing !== null} onOpenChange={(o) => { if (!o) { setCreating(false); setEditing(null); } }}>
        <DialogPopup className="max-w-md">
          <DialogTitle>{editing ? "Editar meta" : "Nueva meta"}</DialogTitle>
          <form
            onSubmit={(e) => { e.preventDefault(); if (editing ? !editInvalid : !createInvalid) (editing ? update : create).mutate(); }}
            className="space-y-4"
          >
            <div className="space-y-1.5"><Label>Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div className="space-y-1.5"><Label>Aporte mensual * (COP)</Label><MoneyInput currency="COP" value={monthly} onChange={setMonthly} /></div>
            <div className="space-y-1.5">
              <Label>Cuenta de ahorro *</Label>
              <EntitySelect value={savingsId} onChange={setSavingsId} queryKey={qk.accounts(false)} queryFn={() => api.listAccounts(false)} />
            </div>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>Meta definida: completa objetivo y fecha. Abierta: deja ambos vacíos.</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Objetivo (COP)</Label><MoneyInput currency="COP" value={target} onChange={setTarget} /></div>
              <div className="space-y-1.5"><Label>Fecha límite</Label><Input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => { setCreating(false); setEditing(null); }}>Cancelar</Button>
              <Button type="submit" disabled={(editing ? editInvalid : createInvalid) || create.isPending || update.isPending}>
                {create.isPending || update.isPending ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Contribute dialog */}
      <Dialog open={contributing !== null} onOpenChange={(o) => !o && setContributing(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Aportar a {contributing?.name}</DialogTitle>
          <form onSubmit={(e) => { e.preventDefault(); if (amount !== null && date) contribute.mutate(); }} className="space-y-4">
            <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>Transfiere desde tu cuenta origen predeterminada (configúrala en Ajustes).</p>
            <div className="space-y-1.5"><Label>Monto * (COP)</Label><MoneyInput currency="COP" value={amount} onChange={setAmount} /></div>
            <div className="space-y-1.5"><Label>Fecha *</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setContributing(null)}>Cancelar</Button>
              <Button type="submit" disabled={amount === null || !date || contribute.isPending}>{contribute.isPending ? "…" : "Aportar"}</Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      <ConfirmDialog
        open={pausing !== null}
        onOpenChange={(o) => !o && setPausing(null)}
        title="Pausar meta"
        description={`Se pausará "${pausing?.name}". Tus aportes se mantienen. Puedes restaurarla luego.`}
        confirmLabel="Pausar"
        pending={pause.isPending}
        onConfirm={() => pausing && pause.mutate()}
      />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 3: Manual smoke**

Backend running + `pnpm dev`, and a default source account set in `/settings`: create an open-ended goal and a defined goal (objetivo+fecha); edit one; record a contribution (verify the savings balance and dashboard update); pause then restore a goal. A contribution without a default source shows the 422 message.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(app\)/goals/page.tsx
git commit -m "feat(frontend): /goals management (create/edit/pause/restore/contribute)"
```

---

### Task 20: Masters — "Restaurar" row action on `/accounts`, `/categories`, `/category-groups`

**Files:**
- Modify: `frontend/app/(app)/accounts/page.tsx`, `frontend/app/(app)/categories/page.tsx`, `frontend/app/(app)/category-groups/page.tsx`
- Verify: typecheck + lint + manual smoke

**Interfaces:**
- Consumes: `api.restoreAccount`, `api.restoreCategory`, `api.restoreCategoryGroup`; existing `invalidate(qc, "accountWrite"|"categoryWrite"|"categoryGroupWrite")`.

- [ ] **Step 1: Accounts — add a restore mutation + row action**

In `frontend/app/(app)/accounts/page.tsx`, add the mutation next to `archive`:

```typescript
  const restore = useMutation({
    mutationFn: (id: number) => api.restoreAccount(id),
    onSuccess: () => done("Cuenta restaurada"),
    onError: onErr,
  });
```

In the row actions cell, render a restore button for archived rows (the current cell only renders actions when `!a.archived`):

```tsx
                  <td className="px-3 py-2.5 text-right">
                    {a.archived ? (
                      <Button variant="ghost" size="sm" disabled={restore.isPending} onClick={() => restore.mutate(a.id)}>Restaurar</Button>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(a)}>Editar</Button>
                        <Button variant="ghost" size="sm" onClick={() => setArchiving(a)}>Archivar</Button>
                      </div>
                    )}
                  </td>
```

Also update the archive `ConfirmDialog` description to drop the "no podrás reactivarla" caveat, since restore now exists: change it to `Se archivará "${archiving?.name}". Puedes restaurarla luego con "Mostrar archivadas".`

- [ ] **Step 2: Categories — same pattern**

In `frontend/app/(app)/categories/page.tsx`, add a `restore` mutation calling `api.restoreCategory(id)` with `done("Categoría restaurada")` and an equivalent archived-row "Restaurar" button mirroring the accounts change. Update the archive confirm copy the same way.

- [ ] **Step 3: Category-groups — same pattern**

In `frontend/app/(app)/category-groups/page.tsx`, add a `restore` mutation calling `api.restoreCategoryGroup(id)` with `done("Grupo restaurado")` and the archived-row "Restaurar" button. Update the archive confirm copy.

- [ ] **Step 4: Typecheck + lint**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
Expected: PASS.

- [ ] **Step 5: Manual smoke**

For each master: enable "Mostrar archivadas/archivados", archive a row, then restore it — it returns to the active list. Confirm copy no longer claims archiving is irreversible.

- [ ] **Step 6: Commit**

```bash
git add "frontend/app/(app)/accounts/page.tsx" "frontend/app/(app)/categories/page.tsx" "frontend/app/(app)/category-groups/page.tsx"
git commit -m "feat(frontend): restore action for archived masters"
```

---

## Final verification

- [ ] **Backend suite green:** `cd backend && uv run pytest && uv run ruff check` → all pass.
- [ ] **Frontend clean:** `cd frontend && pnpm exec tsc --noEmit && pnpm lint` → pass.
- [ ] **End-to-end smoke (backend + `pnpm dev`):** goals create/edit/pause/restore/contribute; budgets assign reflected in safe-to-spend; recurring edit/delete/restore; masters restore. Dashboard/reports/balances reflect each write.
- [ ] **Banners gone:** no `Phase2Banner` remains on `/goals`, `/budgets`, `/recurring` (`grep -rn Phase2Banner frontend/app` returns nothing for these three).
- [ ] **Agent parity:** the new goals/budgets/recurring writes are MCP tools (`grep -rn "mcp.tool" backend/src/quaestor/mcp/registry.py` shows `assign_budget`, `create_goal`, `update_goal`, `contribute_goal`, `pause_goal`, `restore_goal`, `update_recurring`, `delete_recurring`).
- [ ] **Thin-client purity:** no business arithmetic added in `frontend/lib` or pages (only `MoneyInput` text↔cents and progress `pct` display rounding, which renders a value the API resolved).

## Self-Review (author's checklist — verified while writing)

- **Spec coverage:** goals CRUD+contribute (Tasks 10-13, 19) · budgets assign/status (Tasks 7-9, 18) · recurring edit/delete (Tasks 3-6, 17) · un-archive masters (Tasks 1-2, 20) · MCP parity (Tasks 6, 9, 13) · ADR-0005 soft-delete (Tasks 1-2, 4, 11) · ADR-0006 verbs `POST /{id}/restore`, `POST /{id}/contribute`, `PUT /budgets` (Tasks 5, 8, 12).
- **No new tables/migrations:** every soft-delete reuses `status`/`active`/`archived`; assign upserts via existing `set_budget`.
- **Type consistency:** service `_UNSET` sentinels (`recurring`, `goals`) match their router `model_dump(exclude_unset=True)` callers; `BudgetLine` fields identical across DTO (Task 7), schema `BudgetLineOut` (Task 8), and TS `BudgetLine` (Task 14); `GoalOut`/`Goal` fields match across schema (Task 12) and TS (Task 14).
- **Immutability:** recurring `type`/`currency` never appear in `RecurringUpdate` (schema Task 5) nor the edit form (Task 17, disabled type select).

## Execution Handoff

(Filled in by the writing-plans skill after saving.)

# MCP Parity Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the parity gap between the FastAPI backend and the MCP server by adding 28 missing MCP tools (plus 1 rename) so every backend capability is reachable via MCP, per ADR-0006.

**Architecture:** Hand-written batch. Seven new tool modules under `mcp/tools/` plus formatters in `mcp/format.py`. Each tool is a thin Pydantic-input wrapper that delegates to the existing service layer (golden rule from the general design). All new tools share the existing `_as_text` error-mapping wrapper; one new per-entity render function per tool. Wiring lives in `mcp/registry.py` (where `register_core_tools`, `register_temporal_tools`, `register_planning_tools` already live).

**Tech Stack:** FastMCP (MCP SDK), Pydantic, SQLModel, pytest, in-memory SQLite for tests. No new dependencies.

## Global Constraints

- Backend root for commands: `/Users/angelozdev/me/quaestor/backend` (set via `cd` in every command).
- All amounts are integer cents; sign by `type`, never by sign (general-design §6).
- All amounts in markdown go through `format.money` / `format.cents_to_major` (already imported from `domain.money.cents_to_major`).
- Tool names follow `<verb>_<noun>` snake_case; verbs `create`, `update`, `archive`, `restore`, `get`, `list`, `delete`.
- One tool wraps ONE service call. No business logic in the tool layer.
- Every tool uses `@_as_text` from `mcp/tools/core.py` so typed domain errors become agent text.
- Inputs accept readable names (e.g. `account="Bancolombia"`); `_resolve_account` / `_resolve_category` from `tools/core.py` already exist — reuse them.
- For masters updates/deletes/gets that need entity lookup by name, add ONE new helper `_resolve_account_by_name`, `_resolve_category_by_name`, `_resolve_category_group_by_name`, `_resolve_tag_by_name` next to the existing helpers in `tools/core.py`.
- ADR-0005 lifecycle: `archive_*` soft-deletes; `restore_*` is idempotent; `delete_tag` is hard (no archive).
- ADR-0006 parity: every new HTTP write ships a sibling MCP tool. We are closing pre-existing gaps.
- All commits use conventional commits prefix (`feat(backend): …`, `test(backend): …`, `chore(backend): …`, `docs(adr): …`).
- Tests use in-memory SQLite via `make_engine(memory=True)` + `init_db`. Pattern matches `tests/mcp/conftest.py`.
- Spec is at `docs/superpowers/specs/2026-06-21-mcp-parity-gap-closure-design.md`.

---

### Task 1: Write ADR-0009

**Files:**
- Create: `docs/adr/0009-closing-mcp-parity-gap.md`

**Interfaces:**
- Consumes: nothing.
- Produces: ADR file in the same shape as `docs/adr/0006-goals-and-budgets-write-api-with-mcp-parity.md`.

- [ ] **Step 1: Create the ADR file**

Write to `/Users/angelozdev/me/quaestor/docs/adr/0009-closing-mcp-parity-gap.md` with this exact content:

```markdown
# 0009 — Closing the MCP Parity Gap

- **Status:** accepted
- **Date:** 2026-06-21

## Context

ADR-0006 mandates that every new HTTP write ships a sibling MCP tool. The P2
MCP server was launched before ADR-0006 was in force, so the existing tools
(24) cover only part of the backend's HTTP surface (~52 endpoints). 28
backend capabilities — masters CRUD, transaction updates/deletes/get, settings
read/write, budgets reads, recurring restore, goals reads, and the monthly
report — are reachable from the web UI but not from MCP agents.

## Decision

Ship the missing 28 MCP tools in one batch, plus a `delete_recurring` →
`archive_recurring` rename for consistency with ADR-0005's archive vocabulary.

The batch uses a hand-written parallel structure (one tool module per domain
area) instead of codegen-from-OpenAPI, because:

1. We are closing a one-time gap, not building a long-term parity mechanism.
2. Codegen introduces a second adapter layer that can drift from the existing
   service layer it is supposed to mirror.
3. ADR-0006 already covers future additions — a manual `<verb>_<noun>` tool
   per HTTP write keeps the invariant easy to enforce in code review.

Excluded from MCP (by design, not by omission):

- `POST /api/rollover` — scheduler-only trigger per ADR-017.
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` — MCP
  authenticates via bearer token; password login lives behind the frontend
  cookie session.

## Consequences

- Tool count grows from 24 to 52. Each tool has a stable, named verb and a
  precise input model, so discoverability improves, not degrades.
- The implementation plan (`docs/superpowers/plans/2026-06-21-mcp-parity-gap-closure.md`)
  ships the gap closure as 13 reviewable tasks with TDD throughout.
- ADR-0006's invariant becomes enforceable at code review: any new HTTP write
  merged without a sibling MCP tool can be flagged against this ADR plus
  ADR-0006.
- Follow-up ADR may codegen MCP tools from FastAPI's OpenAPI schema; that work
  is explicitly out of scope here.

## Related

- ADR-0005 — soft-delete + restore as the uniform lifecycle for masters,
  recurring, and goals.
- ADR-0006 — every new HTTP write ships a sibling MCP tool.
- Spec: `docs/superpowers/specs/2026-06-21-mcp-parity-gap-closure-design.md`.
```

- [ ] **Step 2: Append to the ADR index**

Open `/Users/angelozdev/me/quaestor/docs/adr/README.md`. The current index lists ADRs 0001–0008. Append a row for ADR-0009 in the same table format. (Read the file first to mirror its exact row shape.)

- [ ] **Step 3: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add docs/adr/0009-closing-mcp-parity-gap.md docs/adr/README.md
git commit -m "docs(adr): 0009 close the MCP parity gap in one batch"
```

---

### Task 2: Add formatters for the new tools

**Files:**
- Modify: `backend/src/quaestor/mcp/format.py:32-244`
- Modify: `backend/tests/mcp/test_format.py:1-126`

**Interfaces:**
- Consumes: existing `money`, `cents_to_major`, `domain_error_text`, all existing entity models imported at the top of `format.py`.
- Produces: new render functions consumed by Tasks 3–12.

- [ ] **Step 1: Add failing tests for the new renderers**

Append these tests to `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_format.py`:

```python
from datetime import date
from decimal import Decimal

from quaestor.domain.models import (
    Account, AccountType, Budget, Category, CategoryGroup, Goal,
    GoalStatus, RecurringItem, RecurringMode, Settings, Tag,
    Transaction, TxStatus, TxType, IntervalUnit,
)
from quaestor.domain.dtos import (
    BudgetLine, BudgetStatus, GoalProgress, SafeToSpend,
)


def test_account_card_basic():
    a = Account(id=7, name="Bancolombia", type=AccountType.debit, currency="COP", balance=4_500_000)
    text = format.account_card(a)
    assert "Bancolombia" in text and "debit" in text
    assert "45000.00 COP" in text
    assert "id=7" in text


def test_category_card_with_group():
    g = CategoryGroup(id=3, name="Essentials")
    c = Category(id=4, name="Groceries", group_id=3, is_income=False)
    text = format.category_card(c, group=g)
    assert "Groceries" in text and "Essentials" in text
    assert "id=4" in text


def test_category_card_without_group():
    c = Category(id=4, name="Groceries", group_id=None, is_income=True)
    text = format.category_card(c, group=None)
    assert "Groceries" in text and "(no group)" in text
    assert "income" in text


def test_category_group_card():
    g = CategoryGroup(id=2, name="Essentials", sort_order=1)
    text = format.category_group_card(g)
    assert "Essentials" in text and "id=2" in text


def test_tag_card():
    t = Tag(id=9, name="travel")
    assert format.tag_card(t) == "Tag 'travel' (id 9)."


def test_transaction_card():
    tx = Transaction(
        id=42, date=date(2026, 6, 18), payee="Lunch", type=TxType.expense,
        status=TxStatus.posted, amount=5_000_000, currency="COP",
        fx_rate=Decimal("1"), to_base=5_000_000, account_id=1,
    )
    text = format.transaction_card(tx)
    assert "Lunch" in text and "50000.00 COP" in text
    assert "2026-06-18" in text and "id=42" in text


def test_settings_card():
    s = Settings(id=1, base_currency="COP", default_source_account_id=3)
    text = format.settings_card(s)
    assert "Base currency: COP" in text
    assert "default source account: 3" in text


def test_budgets_table_empty():
    assert format.budgets_table([]) == "No budgets for that month."


def test_budgets_table_renders_lines():
    lines = [
        BudgetLine(
            category_id=1, category_name="Groceries",
            assigned=200_000, rollover_in=0, spent=80_000,
            available=120_000, pct_used=40.0, status="under",
        )
    ]
    text = format.budgets_table(lines)
    assert "Groceries" in text and "| Category |" in text
    assert "2000.00" in text and "800.00" in text
    assert "1200.00" in text


def test_safe_to_spend_card():
    sts = SafeToSpend(
        year_month="2026-06", income_forecast=2_000_000,
        committed=600_000, assigned_envelopes=400_000, free=1_000_000,
        committed_breakdown=[],
    )
    text = format.safe_to_spend_card(sts)
    assert "2026-06" in text
    assert "10000.00 COP" in text  # free
    assert "20000.00 COP" in text  # income
    assert "free to spend" in text.lower()


def test_goals_table():
    goals = [
        Goal(id=1, name="Trip", monthly_amount=500_000, savings_account_id=2,
             target_amount=2_000_000, deadline=date(2026, 12, 31), status=GoalStatus.active),
    ]
    text = format.goals_table(goals)
    assert "Trip" in text and "5000.00 COP" in text
    assert "id=1" in text and "defined" in text


def test_goals_table_empty():
    assert format.goals_table([]) == "No goals."


def test_goals_progress_table():
    progress = [
        GoalProgress(
            goal_id=1, name="Trip", monthly_amount=500_000, saved=600_000,
            target_amount=2_000_000, deadline=date(2026, 12, 31),
            eta=None, on_track=True,
        )
    ]
    text = format.goals_progress_table(progress)
    assert "Trip" in text and "6000.00" in text and "20000.00" in text
    assert "on-track" in text


def test_monthly_report_card_headline():
    # Minimal MonthlyReport-like object: only fields the renderer reads.
    class _R:
        month = "2026-06"
        income = 5_000_000
        expense = 3_000_000
        net = 2_000_000
        markdown = "# sample"
    text = format.monthly_report_card(_R())
    assert "2026-06" in text
    assert "50000.00 COP" in text  # income
    assert "30000.00 COP" in text  # expense
    assert "20000.00 COP" in text  # net


def test_recurring_restored():
    item = RecurringItem(
        id=5, name="Rent", payee="Landlord", type=TxType.expense,
        mode=RecurringMode.auto, amount=2_000_000, currency="COP",
        category_id=None, account_id=1,
        interval_unit=IntervalUnit.month, interval_count=1,
        start_date=date(2026, 1, 1), end_date=None, active=True,
    )
    text = format.recurring_restored(item)
    assert "Rent" in text and "restored" in text
    assert "id=5" in text
```

Also add the missing imports at the top of the test file (merge with existing):

```python
from quaestor.domain.models import (
    Goal, GoalStatus, IntervalUnit, Settings,
)
from quaestor.domain.dtos import BudgetLine, GoalProgress, SafeToSpend
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_format.py -v`
Expected: FAIL on every new test, with `AttributeError: module 'quaestor.mcp.format' has no attribute 'account_card'`.

- [ ] **Step 3: Add the renderers to `format.py`**

Append to `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/format.py` (after `to_pay_table`, before nothing — file ends there):

```python
# ----- new renderers (ADR-0009: MCP parity gap closure) -----


def account_card(account: Account) -> str:
    return (
        f"Account **{account.name}** (id={account.id}, "
        f"{account.type.value}, {account.currency}) — "
        f"balance {money(account.balance, account.currency)}"
    )


def category_card(category: Category, group: CategoryGroup | None) -> str:
    group_name = group.name if group is not None else "(no group)"
    kind = "income" if category.is_income else "expense"
    return (
        f"Category **{category.name}** (id={category.id}, {kind}, "
        f"group: {group_name})"
    )


def category_group_card(group: CategoryGroup) -> str:
    return f"Category group **{group.name}** (id={group.id}, order={group.sort_order})"


def tag_card(tag: Tag) -> str:
    return f"Tag '{tag.name}' (id {tag.id})."


def transaction_card(tx: Transaction) -> str:
    return (
        f"Transaction **{tx.payee}** (id={tx.id}, {tx.type.value}, {tx.status.value}, "
        f"{tx.date.isoformat()}) — {money(tx.amount, tx.currency)} "
        f"({money(tx.to_base, 'COP')})"
    )


def settings_card(settings) -> str:
    src = (
        f"{settings.default_source_account_id}"
        if settings.default_source_account_id is not None
        else "(none)"
    )
    return (
        f"Settings — Base currency: {settings.base_currency}; "
        f"default source account: {src}"
    )


def budgets_table(lines: list) -> str:
    if not lines:
        return "No budgets for that month."
    rows = [
        "| Category | Assigned | Rollover in | Spent | Available | Used |",
        "|---|---|---|---|---|---|",
    ]
    for ln in lines:
        rows.append(
            f"| {ln.category_name} | {cents_to_major(ln.assigned)} | "
            f"{cents_to_major(ln.rollover_in)} | {cents_to_major(ln.spent)} | "
            f"{cents_to_major(ln.available)} | {ln.pct_used:.0f}% |"
        )
    return "\n".join(rows)


def safe_to_spend_card(sts: SafeToSpend) -> str:
    return "\n".join([
        f"Safe to spend for **{sts.year_month}**: {money(sts.free, 'COP')} free to spend.",
        f"- Income forecast: {money(sts.income_forecast, 'COP')}",
        f"- Committed: {money(sts.committed, 'COP')}",
        f"- Assigned to envelopes: {money(sts.assigned_envelopes, 'COP')}",
    ])


def goals_table(goals) -> str:
    if not goals:
        return "No goals."
    rows = [
        "| id | Name | Status | Monthly | Target | Deadline |",
        "|---|---|---|---|---|---|",
    ]
    for g in goals:
        kind = "defined" if g.target_amount is not None else "open-ended"
        target = cents_to_major(g.target_amount) if g.target_amount is not None else "—"
        deadline = g.deadline.isoformat() if g.deadline is not None else "—"
        rows.append(
            f"| {g.id} | {g.name} | {g.status.value} | "
            f"{cents_to_major(g.monthly_amount)} COP | {target} | {deadline} |"
        )
    return "\n".join(rows)


def goals_progress_table(progress: list) -> str:
    if not progress:
        return "No goal progress."
    rows = [
        "| id | Name | Saved | Target | On track |",
        "|---|---|---|---|---|",
    ]
    for p in progress:
        target = cents_to_major(p.target_amount) if p.target_amount is not None else "—"
        track = "on-track" if p.on_track else "behind"
        rows.append(
            f"| {p.goal_id} | {p.name} | {cents_to_major(p.saved)} COP | "
            f"{target} | {track} |"
        )
    return "\n".join(rows)


def monthly_report_card(report) -> str:
    return "\n".join([
        f"# Monthly report — {report.month}",
        f"- Income: {money(report.income, 'COP')}",
        f"- Expense: {money(report.expense, 'COP')}",
        f"- Net: {money(report.net, 'COP')}",
        "",
        report.markdown,
    ])


def recurring_restored(item: RecurringItem) -> str:
    return f"✅ Restored recurring '{item.name}' (id {item.id})."
```

Also add to the top imports in `format.py` (next to existing model imports):

```python
from ..domain.models import Settings  # noqa: F401  (used by settings_card)
from ..domain.dtos import GoalProgress, SafeToSpend  # noqa: F401
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_format.py -v`
Expected: PASS on all 16 new tests (and the existing 14).

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/format.py backend/tests/mcp/test_format.py
git commit -m "feat(backend): add mcp formatters for parity gap (ADR-0009)"
```

---

### Task 3: Accounts MCP tools

**Files:**
- Create: `backend/src/quaestor/mcp/tools/masters.py`
- Modify: `backend/src/quaestor/mcp/registry.py:1-209`
- Create: `backend/tests/mcp/test_masters_accounts.py`

**Interfaces:**
- Consumes: `_as_text`, `_resolve_account` from `mcp/tools/core.py`; `services.accounts.{create_account, update_account, archive_account, unarchive_account, get_account}`.
- Produces: `MASTERS_TOOL_NAMES` (initially containing only the 5 accounts tools); `register_accounts_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_masters_accounts.py`:

```python
from datetime import date

from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    CreateAccountInput, UpdateAccountInput, ArchiveAccountInput,
    RestoreAccountInput, GetAccountInput,
)
from quaestor.services import accounts


def test_create_account_returns_card(session):
    out = masters.create_account(
        session, CreateAccountInput(name="Nequi", type="debit", currency="COP")
    )
    assert "Nequi" in out and "debit" in out
    assert "id=" in out


def test_create_account_rejects_empty_name(session):
    out = masters.create_account(
        session, CreateAccountInput(name="   ", type="debit")
    )
    assert "Invalid input" in out


def test_create_account_rejects_unsupported_currency(session):
    out = masters.create_account(
        session, CreateAccountInput(name="X", type="debit", currency="XYZ")
    )
    assert "Invalid input" in out


def test_update_account_renames_and_changes_type(session):
    acc = accounts.create_account(session, "Old", "debit", "COP", balance=0)
    out = masters.update_account(
        session, UpdateAccountInput(account="Old", name="New", type="savings")
    )
    assert "New" in out
    refreshed = accounts.get_account(session, acc.id)
    assert refreshed.name == "New"
    assert refreshed.type.value == "savings"


def test_update_account_unknown_name_returns_text(session):
    out = masters.update_account(
        session, UpdateAccountInput(account="Ghost", name="Whatever")
    )
    assert "not found" in out


def test_archive_account_soft_deletes(session, seeded):
    out = masters.archive_account(
        session, ArchiveAccountInput(account=seeded["account"].name)
    )
    assert "Bancolombia" in out and "archived" in out
    listed = accounts.list_accounts(session)  # default excludes archived
    assert listed == []


def test_archive_account_already_archived_is_idempotent(session, seeded):
    masters.archive_account(session, ArchiveAccountInput(account="Bancolombia"))
    out = masters.archive_account(session, ArchiveAccountInput(account="Bancolombia"))
    assert "Bancolombia" in out and "archived" in out


def test_restore_account(session, seeded):
    masters.archive_account(session, ArchiveAccountInput(account="Bancolombia"))
    out = masters.restore_account(session, RestoreAccountInput(account="Bancolombia"))
    assert "Bancolombia" in out and "restored" in out
    assert len(accounts.list_accounts(session)) == 1


def test_get_account_returns_card(session, seeded):
    out = masters.get_account(session, GetAccountInput(account="Bancolombia"))
    assert "Bancolombia" in out and "100000.00 COP" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_accounts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.mcp.tools.masters'`.

- [ ] **Step 3: Create `masters.py` with input models and a stub `register_accounts_tools`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/masters.py`:

```python
"""MCP masters tools (ADR-0009): accounts, categories, category-groups, tags.

One module hosts the input models + the per-entity impls for all four master
entities so each task (accounts / categories / groups / tags) can land
independently while sharing helpers (resolve-by-name, register functions).

Tasks 3-6 each add input models, impls, and a `register_<entity>_tools(mcp)`
function. Task 13 wires them all into the FastMCP instance via the registry.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import NotFound
from ...domain.models import Account
from ...services import accounts, categories, tags
from .. import format
from .core import _as_text, _resolve_account


# ===== accounts =====


class CreateAccountInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Account name")
    type: Literal["debit", "credit", "cash", "savings"] = Field(description="Account type")
    currency: str = Field(default="COP", description="ISO currency code; defaults to COP")
    initial_balance_cents: int = Field(default=0, ge=0, description="Initial balance in cents")


class UpdateAccountInput(BaseModel):
    account: str = Field(description="Account name")
    name: str | None = Field(default=None, description="New name")
    type: Literal["debit", "credit", "cash", "savings"] | None = Field(
        default=None, description="New type"
    )


class ArchiveAccountInput(BaseModel):
    account: str = Field(description="Account name")


class RestoreAccountInput(BaseModel):
    account: str = Field(description="Account name")


class GetAccountInput(BaseModel):
    account: str = Field(description="Account name")


@_as_text
def create_account(session: Session, inp: CreateAccountInput) -> str:
    acc = accounts.create_account(
        session,
        name=inp.name,
        type=inp.type,
        currency=inp.currency,
        balance=inp.initial_balance_cents,
    )
    return format.account_card(acc)


@_as_text
def update_account(session: Session, inp: UpdateAccountInput) -> str:
    acc = _resolve_account(session, inp.account)
    updated = accounts.update_account(
        session, acc.id, name=inp.name, type=inp.type
    )
    return format.account_card(updated)


@_as_text
def archive_account(session: Session, inp: ArchiveAccountInput) -> str:
    acc = _resolve_account(session, inp.account)
    archived = accounts.archive_account(session, acc.id)
    return f"✅ Archived **{archived.name}** (id={archived.id})."


@_as_text
def restore_account(session: Session, inp: RestoreAccountInput) -> str:
    acc = _resolve_account(session, inp.account)
    restored = accounts.unarchive_account(session, acc.id)
    return format.account_card(restored)


@_as_text
def get_account(session: Session, inp: GetAccountInput) -> str:
    acc = _resolve_account(session, inp.account)
    return format.account_card(acc)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_accounts.py -v`
Expected: PASS on all 9 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/masters.py backend/tests/mcp/test_masters_accounts.py
git commit -m "feat(backend): mcp accounts tools (ADR-0009)"
```

---

### Task 4: Categories MCP tools

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/masters.py` (append)
- Create: `backend/tests/mcp/test_masters_categories.py`

**Interfaces:**
- Consumes: `_as_text`, `_resolve_category` from `mcp/tools/core.py`; `services.categories.{create_category, update_category, archive_category, unarchive_category, get_category}`.
- Produces: `register_categories_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_masters_categories.py`:

```python
from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    CreateCategoryInput, UpdateCategoryInput, ArchiveCategoryInput,
    RestoreCategoryInput, GetCategoryInput,
)
from quaestor.services import categories


def _seed_group(session):
    return categories.create_group(session, "Essentials")


def test_create_category_with_group_returns_card(session):
    g = _seed_group(session)
    out = masters.create_category(
        session, CreateCategoryInput(name="Groceries", group="Essentials")
    )
    assert "Groceries" in out and "Essentials" in out


def test_create_category_income_flag(session):
    out = masters.create_category(
        session, CreateCategoryInput(name="Salary", is_income=True)
    )
    assert "Salary" in out and "income" in out


def test_create_category_unknown_group_returns_text(session):
    _seed_group(session)
    out = masters.create_category(
        session, CreateCategoryInput(name="X", group="Nonexistent")
    )
    assert "Invalid input" in out


def test_update_category_renames_and_regroups(session):
    _seed_group(session)
    g2 = categories.create_group(session, "Discretionary")
    categories.create_category(session, "Fun")
    out = masters.update_category(
        session, UpdateCategoryInput(category="Fun", name="Entertainment", group="Discretionary")
    )
    assert "Entertainment" in out and "Discretionary" in out


def test_update_category_unknown_returns_text(session):
    out = masters.update_category(session, UpdateCategoryInput(category="Ghost"))
    assert "not found" in out


def test_archive_and_restore_category_roundtrip(session):
    _seed_group(session)
    categories.create_category(session, "Groceries")
    out = masters.archive_category(session, ArchiveCategoryInput(category="Groceries"))
    assert "archived" in out
    out = masters.restore_category(session, RestoreCategoryInput(category="Groceries"))
    assert "Groceries" in out


def test_get_category_returns_card(session):
    _seed_group(session)
    categories.create_category(session, "Groceries")
    out = masters.get_category(session, GetCategoryInput(category="Groceries"))
    assert "Groceries" in out and "Essentials" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_categories.py -v`
Expected: FAIL with `ImportError: cannot import name 'CreateCategoryInput'`.

- [ ] **Step 3: Append category impls to `masters.py`**

Append to `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/masters.py`:

```python
# ===== categories =====


class CreateCategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Category name")
    group: str | None = Field(default=None, description="Category group name (optional)")
    is_income: bool = Field(default=False, description="Income category flag")
    exclude_from_budget: bool = Field(default=False, description="Exclude from budget")
    exclude_from_totals: bool = Field(default=False, description="Exclude from totals")


class UpdateCategoryInput(BaseModel):
    category: str = Field(description="Category name")
    name: str | None = Field(default=None, description="New name")
    group: str | None = Field(default=None, description="New group name (None to clear)")
    is_income: bool | None = Field(default=None, description="New income flag")
    exclude_from_budget: bool | None = Field(default=None, description="New exclude_from_budget")
    exclude_from_totals: bool | None = Field(default=None, description="New exclude_from_totals")


class ArchiveCategoryInput(BaseModel):
    category: str = Field(description="Category name")


class RestoreCategoryInput(BaseModel):
    category: str = Field(description="Category name")


class GetCategoryInput(BaseModel):
    category: str = Field(description="Category name")


def _resolve_category_group(session: Session, name: str):
    """Resolve a category group by name (case-insensitive). Raise NotFound with hints."""
    all_groups = categories.list_groups(session, include_archived=False)
    target = name.strip().lower()
    for g in all_groups:
        if g.name.lower() == target:
            return g
    available = ", ".join(g.name for g in all_groups) or "(none)"
    raise NotFound(f"Category group '{name}' not found. Available: {available}.")


def _category_group_by_id(session: Session, group_id: int):
    """Look up a category group by id; returns None if missing."""
    for g in categories.list_groups(session, include_archived=True):
        if g.id == group_id:
            return g
    return None


@_as_text
def create_category(session: Session, inp: CreateCategoryInput) -> str:
    group = _resolve_category_group(session, inp.group) if inp.group else None
    cat = categories.create_category(
        session,
        name=inp.name,
        group_id=group.id if group else None,
        is_income=inp.is_income,
        exclude_from_budget=inp.exclude_from_budget,
        exclude_from_totals=inp.exclude_from_totals,
    )
    return format.category_card(cat, group)


@_as_text
def update_category(session: Session, inp: UpdateCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    group_id = categories._UNSET  # unchanged by default
    group_for_card = None
    if inp.group is not None:
        if inp.group == "":
            group_id = None  # explicitly clear
            group_for_card = None
        else:
            g = _resolve_category_group(session, inp.group)
            group_id = g.id
            group_for_card = g
    updated = categories.update_category(
        session,
        cat.id,
        name=inp.name,
        group_id=group_id,
        is_income=inp.is_income,
        exclude_from_budget=inp.exclude_from_budget,
        exclude_from_totals=inp.exclude_from_totals,
    )
    return format.category_card(updated, group_for_card)


@_as_text
def archive_category(session: Session, inp: ArchiveCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    archived = categories.archive_category(session, cat.id)
    return f"✅ Archived **{archived.name}** (id={archived.id})."


@_as_text
def restore_category(session: Session, inp: RestoreCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    restored = categories.unarchive_category(session, cat.id)
    group = _category_group_by_id(session, restored.group_id)
    return format.category_card(restored, group)


@_as_text
def get_category(session: Session, inp: GetCategoryInput) -> str:
    cat = _resolve_category(session, inp.category)
    group = _category_group_by_id(session, cat.group_id)
    return format.category_card(cat, group)
```

Note: `_resolve_category` already exists in `mcp/tools/core.py:111-118`. Reuse it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_categories.py -v`
Expected: PASS on all 7 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/masters.py backend/tests/mcp/test_masters_categories.py
git commit -m "feat(backend): mcp categories tools (ADR-0009)"
```

---

### Task 5: Category-groups MCP tools

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/masters.py` (append)
- Create: `backend/tests/mcp/test_masters_category_groups.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `_resolve_category_group` from Task 4; `services.categories.{create_group, update_group, archive_group, unarchive_group}`.
- Produces: `register_category_groups_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_masters_category_groups.py`:

```python
from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    CreateCategoryGroupInput, UpdateCategoryGroupInput,
    ArchiveCategoryGroupInput, RestoreCategoryGroupInput,
)
from quaestor.services import categories


def test_create_group(session):
    out = masters.create_category_group(
        session, CreateCategoryGroupInput(name="Essentials", sort_order=2)
    )
    assert "Essentials" in out and "id=" in out


def test_create_group_empty_name_rejected(session):
    out = masters.create_category_group(
        session, CreateCategoryGroupInput(name="   ")
    )
    assert "Invalid input" in out


def test_update_group_renames(session):
    categories.create_group(session, "Old")
    out = masters.update_category_group(
        session, UpdateCategoryGroupInput(group="Old", name="New")
    )
    assert "New" in out


def test_update_group_unknown_returns_text(session):
    out = masters.update_category_group(
        session, UpdateCategoryGroupInput(group="Ghost")
    )
    assert "not found" in out


def test_archive_group(session):
    categories.create_group(session, "Essentials")
    out = masters.archive_category_group(
        session, ArchiveCategoryGroupInput(group="Essentials")
    )
    assert "archived" in out


def test_restore_group(session):
    categories.create_group(session, "Essentials")
    masters.archive_category_group(
        session, ArchiveCategoryGroupInput(group="Essentials")
    )
    out = masters.restore_category_group(
        session, RestoreCategoryGroupInput(group="Essentials")
    )
    assert "Essentials" in out and "restored" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_category_groups.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Append category-group impls to `masters.py`**

Append to `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/masters.py`:

```python
# ===== category groups =====


class CreateCategoryGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Group name")
    sort_order: int = Field(default=0, description="Display order")


class UpdateCategoryGroupInput(BaseModel):
    group: str = Field(description="Category group name")
    name: str | None = Field(default=None, description="New name")
    sort_order: int | None = Field(default=None, description="New display order")


class ArchiveCategoryGroupInput(BaseModel):
    group: str = Field(description="Category group name")


class RestoreCategoryGroupInput(BaseModel):
    group: str = Field(description="Category group name")


@_as_text
def create_category_group(session: Session, inp: CreateCategoryGroupInput) -> str:
    g = categories.create_group(session, name=inp.name, sort_order=inp.sort_order)
    return format.category_group_card(g)


@_as_text
def update_category_group(session: Session, inp: UpdateCategoryGroupInput) -> str:
    g = _resolve_category_group(session, inp.group)
    updated = categories.update_group(
        session, g.id, name=inp.name, sort_order=inp.sort_order
    )
    return format.category_group_card(updated)


@_as_text
def archive_category_group(session: Session, inp: ArchiveCategoryGroupInput) -> str:
    g = _resolve_category_group(session, inp.group)
    archived = categories.archive_group(session, g.id)
    return f"✅ Archived **{archived.name}** (id={archived.id})."


@_as_text
def restore_category_group(session: Session, inp: RestoreCategoryGroupInput) -> str:
    g = _resolve_category_group(session, inp.group)
    restored = categories.unarchive_group(session, g.id)
    return format.category_group_card(restored)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_category_groups.py -v`
Expected: PASS on all 6 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/masters.py backend/tests/mcp/test_masters_category_groups.py
git commit -m "feat(backend): mcp category-groups tools (ADR-0009)"
```

---

### Task 6: Tags MCP tools

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/masters.py` (append)
- Create: `backend/tests/mcp/test_masters_tags.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.tags.{create_tag, update_tag, delete_tag, list_tags}`.
- Produces: `register_tags_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_masters_tags.py`:

```python
from quaestor.mcp.tools import masters
from quaestor.mcp.tools.masters import (
    CreateTagInput, UpdateTagInput, DeleteTagInput,
)


def test_create_tag(session):
    out = masters.create_tag(session, CreateTagInput(name="travel"))
    assert out == "Tag 'travel' (id 1)."


def test_create_tag_idempotent_by_name(session):
    masters.create_tag(session, CreateTagInput(name="trip"))
    out = masters.create_tag(session, CreateTagInput(name="trip"))
    assert out == "Tag 'trip' (id 1)."  # same id, no duplicate


def test_create_tag_empty_name_rejected(session):
    out = masters.create_tag(session, CreateTagInput(name="   "))
    assert "Invalid input" in out


def test_update_tag_renames(session):
    masters.create_tag(session, CreateTagInput(name="old"))
    out = masters.update_tag(session, UpdateTagInput(tag="old", name="new"))
    assert out == "Tag 'new' (id 1)."


def test_update_tag_unknown_returns_text(session):
    out = masters.update_tag(session, UpdateTagInput(tag="ghost", name="x"))
    assert "not found" in out


def test_update_tag_duplicate_name_rejected(session):
    masters.create_tag(session, CreateTagInput(name="a"))
    masters.create_tag(session, CreateTagInput(name="b"))
    out = masters.update_tag(session, UpdateTagInput(tag="a", name="b"))
    assert "Invalid input" in out


def test_delete_tag_removes_it(session):
    masters.create_tag(session, CreateTagInput(name="trip"))
    out = masters.delete_tag(session, DeleteTagInput(tag="trip"))
    assert out == "Deleted tag 'trip'."
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_tags.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Append tag impls + a new `tag_card`-like deletion message to `masters.py`**

Append to `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/masters.py`:

```python
# ===== tags =====


class CreateTagInput(BaseModel):
    name: str = Field(min_length=1, max_length=40, description="Tag name")


class UpdateTagInput(BaseModel):
    tag: str = Field(description="Existing tag name")
    name: str = Field(min_length=1, max_length=40, description="New name")


class DeleteTagInput(BaseModel):
    tag: str = Field(description="Tag name to delete")


def _resolve_tag(session: Session, name: str):
    target = name.strip().lower()
    for t in tags.list_tags(session):
        if t.name.lower() == target:
            return t
    available = ", ".join(t.name for t in tags.list_tags(session)) or "(none)"
    raise NotFound(f"Tag '{name}' not found. Available: {available}.")


@_as_text
def create_tag(session: Session, inp: CreateTagInput) -> str:
    tag = tags.create_tag(session, inp.name)
    return format.tag_card(tag)


@_as_text
def update_tag(session: Session, inp: UpdateTagInput) -> str:
    tag = _resolve_tag(session, inp.tag)
    updated = tags.update_tag(session, tag.id, inp.name)
    return format.tag_card(updated)


@_as_text
def delete_tag(session: Session, inp: DeleteTagInput) -> str:
    tag = _resolve_tag(session, inp.tag)
    tags.delete_tag(session, tag.id)
    return f"Deleted tag '{tag.name}'."
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_masters_tags.py -v`
Expected: PASS on all 7 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/masters.py backend/tests/mcp/test_masters_tags.py
git commit -m "feat(backend): mcp tags tools (ADR-0009)"
```

---

### Task 7: Transactions writes (get/update/delete)

**Files:**
- Create: `backend/src/quaestor/mcp/tools/transactions.py`
- Create: `backend/tests/mcp/test_transactions_writes.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.transactions.{get_transaction, update_transaction, delete_transaction}`.
- Produces: `register_transactions_writes_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_transactions_writes.py`:

```python
from datetime import date

from quaestor.mcp.tools import transactions as tx_tools
from quaestor.mcp.tools.transactions import (
    GetTransactionInput, UpdateTransactionInput, DeleteTransactionInput,
)
from quaestor.services import accounts, transactions as tx_service


def _seed(session):
    return accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)


def test_get_transaction_returns_card(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.get_transaction(session, GetTransactionInput(tx_id=tx.id))
    assert "Lunch" in out and "50000.00 COP" in out
    assert f"id={tx.id}" in out


def test_get_transaction_unknown_returns_text(session):
    out = tx_tools.get_transaction(session, GetTransactionInput(tx_id=999))
    assert "not found" in out


def test_update_transaction_changes_payee_and_notes(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.update_transaction(
        session, UpdateTransactionInput(
            tx_id=tx.id, payee="Brunch", notes="with friends"
        )
    )
    assert "Brunch" in out
    refreshed = tx_service.get_transaction(session, tx.id)
    assert refreshed.payee == "Brunch"
    assert refreshed.notes == "with friends"


def test_update_transaction_can_clear_notes_with_empty_string(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch", notes="note",
    )
    tx_tools.update_transaction(
        session, UpdateTransactionInput(tx_id=tx.id, clear_notes=True)
    )
    assert tx_service.get_transaction(session, tx.id).notes is None


def test_delete_transaction_reverses_balance(session):
    _seed(session)
    tx = tx_service.record_expense(
        session, account_id=1, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch",
    )
    out = tx_tools.delete_transaction(session, DeleteTransactionInput(tx_id=tx.id))
    assert "Deleted" in out
    # account balance back to original
    assert accounts.get_account(session, 1).balance == 10_000_000
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_transactions_writes.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `transactions.py`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/transactions.py`:

```python
"""MCP transaction write tools (ADR-0009): get/update/delete by id.

Reads (list_transactions, list_transactions-filtered) live in `core.py`.
Writes to fields beyond payee/notes/category_id/date are not allowed — those
are immutable in the service layer (P0 invariant: balances only move via
record_expense / record_income / transfer).
"""
from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import transactions
from .. import format
from .core import _as_text, _resolve_category


class GetTransactionInput(BaseModel):
    tx_id: int = Field(description="Transaction id")


class UpdateTransactionInput(BaseModel):
    tx_id: int = Field(description="Transaction id")
    payee: str | None = Field(default=None, description="New payee")
    notes: str | None = Field(default=None, description="New notes")
    clear_notes: bool = Field(default=False, description="Set notes to None")
    category: str | None = Field(default=None, description="New category name (empty string clears)")
    date: Date | None = Field(default=None, description="New date")


class DeleteTransactionInput(BaseModel):
    tx_id: int = Field(description="Transaction id")


@_as_text
def get_transaction(session: Session, inp: GetTransactionInput) -> str:
    tx = transactions.get_transaction(session, inp.tx_id)
    return format.transaction_card(tx)


@_as_text
def update_transaction(session: Session, inp: UpdateTransactionInput) -> str:
    notes = None if inp.clear_notes else inp.notes
    category_id = transactions._UNSET
    if inp.category is not None:
        category_id = (
            None if inp.category == "" else _resolve_category(session, inp.category).id
        )
    updated = transactions.update_transaction(
        session,
        inp.tx_id,
        payee=inp.payee,
        notes=notes,
        category_id=category_id,
        date=inp.date,
    )
    return format.transaction_card(updated)


@_as_text
def delete_transaction(session: Session, inp: DeleteTransactionInput) -> str:
    tx = transactions.get_transaction(session, inp.tx_id)
    payee = tx.payee
    transactions.delete_transaction(session, inp.tx_id)
    return f"Deleted transaction '{payee}' (id {inp.tx_id})."
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_transactions_writes.py -v`
Expected: PASS on all 5 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/transactions.py backend/tests/mcp/test_transactions_writes.py
git commit -m "feat(backend): mcp transaction get/update/delete (ADR-0009)"
```

---

### Task 8: Settings MCP tools

**Files:**
- Create: `backend/src/quaestor/mcp/tools/settings.py`
- Create: `backend/tests/mcp/test_settings_writes.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.settings.{get_settings, update_settings}`.
- Produces: `register_settings_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_settings_writes.py`:

```python
from quaestor.mcp.tools import settings as settings_tools
from quaestor.mcp.tools.settings import GetSettingsInput, UpdateSettingsInput
from quaestor.services import accounts


def test_get_settings_default_card(session):
    out = settings_tools.get_settings(session, GetSettingsInput())
    assert "Base currency: COP" in out
    assert "(none)" in out  # default_source_account_id is None initially


def test_update_settings_base_currency(session):
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(base_currency="USD")
    )
    assert "Base currency: USD" in out


def test_update_settings_rejects_unsupported_currency(session):
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(base_currency="XYZ")
    )
    assert "Invalid input" in out


def test_update_settings_default_source_account(session):
    acc = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=0)
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(default_source_account="Bancolombia")
    )
    assert "default source account: 1" in out  # the new account's id


def test_update_settings_unknown_account_returns_text(session):
    out = settings_tools.update_settings(
        session, UpdateSettingsInput(default_source_account="Ghost")
    )
    assert "not found" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_settings_writes.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `settings.py`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/settings.py`:

```python
"""MCP settings tools (ADR-0009): get/update the singleton Settings row.

Lets the agent set `default_source_account_id`, which is required by
`contribute_goal` (services/goals.py).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import settings
from .. import format
from .core import _as_text, _resolve_account


class GetSettingsInput(BaseModel):
    pass


class UpdateSettingsInput(BaseModel):
    base_currency: Literal["COP", "USD"] | None = Field(
        default=None, description="New base currency"
    )
    default_source_account: str | None = Field(
        default=None, description="New default source account name (None to clear)"
    )


@_as_text
def get_settings(session: Session, inp: GetSettingsInput) -> str:
    s = settings.get_settings(session)
    return format.settings_card(s)


@_as_text
def update_settings(session: Session, inp: UpdateSettingsInput) -> str:
    default_source_id = settings._UNSET  # unchanged by default
    if inp.default_source_account is not None:
        if inp.default_source_account == "":
            default_source_id = None
        else:
            default_source_id = _resolve_account(
                session, inp.default_source_account
            ).id
    updated = settings.update_settings(
        session,
        base_currency=inp.base_currency,
        default_source_account_id=default_source_id,
    )
    return format.settings_card(updated)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_settings_writes.py -v`
Expected: PASS on all 5 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/settings.py backend/tests/mcp/test_settings_writes.py
git commit -m "feat(backend): mcp settings get/update (ADR-0009)"
```

---

### Task 9: Budgets reads MCP tools

**Files:**
- Create: `backend/src/quaestor/mcp/tools/budgets_reads.py`
- Create: `backend/tests/mcp/test_budgets_reads.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.budgets.{list_budgets, safe_to_spend}`.
- Produces: `register_budgets_reads_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_budgets_reads.py`:

```python
from datetime import date

import pytest

from quaestor.mcp.tools import budgets_reads
from quaestor.mcp.tools.budgets_reads import (
    ListBudgetsInput, SafeToSpendInput,
)
from quaestor.services import accounts, budgets, categories


@pytest.fixture
def seeded_month(session):
    acc = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    categories.create_category(session, "Groceries")
    budgets.set_budget(session, category_id=1, year_month="2026-06", amount_assigned=200_000)
    return acc


def test_list_budgets_table_with_one_line(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    categories.create_category(session, "Groceries")
    budgets.set_budget(session, category_id=1, year_month="2026-06", amount_assigned=200_000)
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-06"))
    assert "Groceries" in out and "| Category |" in out
    assert "2000.00" in out


def test_list_budgets_empty_month(session):
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-06"))
    assert out == "No budgets for that month."


def test_list_budgets_rejects_malformed_month(session):
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-6"))
    assert "Invalid input" in out


def test_safe_to_spend_card(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    out = budgets_reads.safe_to_spend(session, SafeToSpendInput(month="2026-06"))
    assert "2026-06" in out and "free to spend" in out.lower()
    assert "Income forecast" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_budgets_reads.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `budgets_reads.py`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/budgets_reads.py`:

```python
"""MCP budget read tools (ADR-0009): list_budgets, safe_to_spend.

Writes (`assign_budget`) live in `planning.py`.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from ...services import budgets
from .. import format
from .core import _as_text


_YEAR_MONTH_RE = __import__("re").compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class _MonthField(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")


class ListBudgetsInput(_MonthField):
    pass


class SafeToSpendInput(_MonthField):
    pass


@_as_text
def list_budgets(session: Session, inp: ListBudgetsInput) -> str:
    lines = budgets.list_budgets(session, inp.month)
    return format.budgets_table(lines)


@_as_text
def safe_to_spend(session: Session, inp: SafeToSpendInput) -> str:
    sts = budgets.safe_to_spend(session, inp.month)
    return format.safe_to_spend_card(sts)
```

If Pydantic complains that the pattern argument is not supported on `Field` for the version in use, replace the validator approach:

```python
class _MonthField(BaseModel):
    month: str = Field(description="YYYY-MM")

    @field_validator("month")
    @classmethod
    def _check(cls, v: str) -> str:
        if not _YEAR_MONTH_RE.match(v):
            from ...domain.errors import ValidationError
            raise ValidationError(f"malformed year_month (expected YYYY-MM): {v!r}")
        return v
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_budgets_reads.py -v`
Expected: PASS on all 4 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/budgets_reads.py backend/tests/mcp/test_budgets_reads.py
git commit -m "feat(backend): mcp budgets reads (ADR-0009)"
```

---

### Task 10: Goals reads MCP tools

**Files:**
- Create: `backend/src/quaestor/mcp/tools/goals_reads.py`
- Create: `backend/tests/mcp/test_goals_reads.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.goals.{list_goals, goals_progress}`.
- Produces: `register_goals_reads_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_goals_reads.py`:

```python
from datetime import date

from quaestor.mcp.tools import goals_reads
from quaestor.services import accounts, goals


def _bank(session):
    return accounts.create_account(session, "Savings", "savings", "COP", balance=0)


def test_list_goals_empty(session):
    out = goals_reads.list_goals(goals_reads.ListGoalsInput())
    assert out == "No goals."


def test_list_goals_table_with_one(session):
    _bank(session)
    goals.create_goal(
        session, name="Trip", monthly_amount=500_000,
        savings_account_id=1, target_amount=2_000_000,
        deadline=date(2026, 12, 31),
    )
    out = goals_reads.list_goals(goals_reads.ListGoalsInput())
    assert "Trip" in out and "| id |" in out


def test_goals_progress_empty(session):
    out = goals_reads.goals_progress(goals_reads.GoalsProgressInput())
    assert out == "No goal progress."


def test_goals_progress_active_goal(session):
    _bank(session)
    goals.create_goal(
        session, name="Trip", monthly_amount=500_000,
        savings_account_id=1, target_amount=2_000_000,
        deadline=date(2026, 12, 31),
    )
    out = goals_reads.goals_progress(goals_reads.GoalsProgressInput())
    assert "Trip" in out and "on-track" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_goals_reads.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `goals_reads.py`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/goals_reads.py`:

```python
"""MCP goal read tools (ADR-0009): list_goals, goals_progress.

Writes (`create_goal`, `update_goal`, `contribute_goal`, `pause_goal`,
`restore_goal`) live in `planning.py`.
"""
from __future__ import annotations

from pydantic import BaseModel
from sqlmodel import Session

from ...services import goals
from .. import format
from .core import _as_text


class ListGoalsInput(BaseModel):
    pass


class GoalsProgressInput(BaseModel):
    pass


@_as_text
def list_goals(session: Session, inp: ListGoalsInput) -> str:
    return format.goals_table(goals.list_goals(session))


@_as_text
def goals_progress(session: Session, inp: GoalsProgressInput) -> str:
    return format.goals_progress_table(goals.goals_progress(session))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_goals_reads.py -v`
Expected: PASS on all 4 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/goals_reads.py backend/tests/mcp/test_goals_reads.py
git commit -m "feat(backend): mcp goals reads (ADR-0009)"
```

---

### Task 11: Monthly report MCP tool

**Files:**
- Create: `backend/src/quaestor/mcp/tools/reports.py`
- Create: `backend/tests/mcp/test_reports.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.reports.monthly_report`.
- Produces: `register_reports_tools(mcp)`.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_reports.py`:

```python
from datetime import date

from quaestor.mcp.tools import reports
from quaestor.services import accounts, categories, transactions


def test_monthly_report_card_returns_headline(session):
    acc = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    categories.create_category(session, "Groceries")
    transactions.record_expense(
        session, account_id=acc.id, amount=5_000_000, currency="COP",
        date=date(2026, 6, 18), payee="Lunch", category_id=1,
    )
    out = reports.monthly_report(reports.MonthlyReportInput(month="2026-06"))
    assert "# Monthly report — 2026-06" in out
    assert "Income:" in out and "Expense:" in out and "Net:" in out


def test_monthly_report_rejects_malformed_month(session):
    out = reports.monthly_report(reports.MonthlyReportInput(month="2026-6"))
    assert "Invalid input" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_reports.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `reports.py`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/reports.py`:

```python
"""MCP report tools (ADR-0009): monthly_report.

The full markdown body comes from `services.reports.render_markdown`; the
tool wrapper adds a compact headline (income/expense/net) so the agent gets
the summary without parsing the long-form body.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

import re

from ...domain.errors import ValidationError
from ...services import reports
from .. import format
from .core import _as_text


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class MonthlyReportInput(BaseModel):
    month: str = Field(description="YYYY-MM")

    @field_validator("month")
    @classmethod
    def _check(cls, v: str) -> str:
        if not _MONTH_RE.match(v):
            raise ValidationError(f"malformed month (expected YYYY-MM): {v!r}")
        return v


@_as_text
def monthly_report(session: Session, inp: MonthlyReportInput) -> str:
    report = reports.monthly_report(session, inp.month)
    return format.monthly_report_card(report)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_reports.py -v`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/reports.py backend/tests/mcp/test_reports.py
git commit -m "feat(backend): mcp monthly_report tool (ADR-0009)"
```

---

### Task 12: Recurring restore + rename `delete_recurring` → `archive_recurring`

**Files:**
- Create: `backend/src/quaestor/mcp/tools/recurring_restore.py`
- Modify: `backend/src/quaestor/mcp/tools/temporal.py:90-174`
- Modify: `backend/tests/mcp/test_temporal.py:131-142`
- Create: `backend/tests/mcp/test_recurring_restore.py`

**Interfaces:**
- Consumes: `_as_text` from `mcp/tools/core.py`; `services.recurring.{restore_recurring, deactivate_recurring}`.
- Produces: `register_recurring_restore_tools(mcp)`; renames `delete_recurring` → `archive_recurring` in temporal.py.

- [ ] **Step 1: Write the failing tests**

Create `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_recurring_restore.py`:

```python
from datetime import date

from quaestor.mcp.tools import recurring_restore
from quaestor.mcp.tools.temporal import (
    CreateRecurringInput, ArchiveRecurringInput,
)
from quaestor.services import accounts, recurring


def _seed(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    from quaestor.mcp.tools.temporal import create_recurring
    create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    return recurring.list_recurring(session)[0].id


def test_archive_recurring_renamed(session):
    """The `delete_recurring` name is gone; `archive_recurring` exists and works."""
    from quaestor.mcp.tools import temporal
    item_id = _seed(session)
    out = temporal.archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    assert "Deactivated" in out
    assert recurring.list_recurring(session, active=True) == []


def test_restore_recurring_roundtrip(session):
    item_id = _seed(session)
    from quaestor.mcp.tools.temporal import archive_recurring
    archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    out = recurring_restore.restore_recurring(
        session, recurring_restore.RestoreRecurringInput(recurring_id=item_id)
    )
    assert "Restored" in out
    assert len(recurring.list_recurring(session, active=True)) == 1
```

Also append to `backend/tests/mcp/test_temporal.py` (replace the existing `test_mcp_delete_recurring`):

```python
def test_mcp_archive_recurring(session):
    _bank(session)
    temporal.create_recurring(session, CreateRecurringInput(
        name="Rent", payee="Landlord", type="expense", mode="auto",
        amount=2_000_000, account="Bancolombia", interval_unit="month",
        interval_count=1, start_date=date(2026, 1, 1),
    ))
    from quaestor.services import recurring as _rec_svc
    item_id = _rec_svc.list_recurring(session)[0].id
    temporal.archive_recurring(session, ArchiveRecurringInput(recurring_id=item_id))
    assert _rec_svc.list_recurring(session, active=True) == []
```

And update the imports at the top of `test_temporal.py`:

```python
from quaestor.mcp.tools.temporal import (
    ArchiveRecurringInput,
    ConfirmPaymentInput,
    CreateRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
    UpdateRecurringInput,
)
```

(Removed `DeleteRecurringInput` import; added `ArchiveRecurringInput`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_recurring_restore.py tests/mcp/test_temporal.py -v`
Expected: FAIL on `test_archive_recurring_renamed` (no `archive_recurring`), on `test_restore_recurring_roundtrip` (no module), and on `test_mcp_archive_recurring` (same).

- [ ] **Step 3: Rename in `temporal.py`**

In `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/temporal.py`:

1. Replace `class DeleteRecurringInput(BaseModel):` with:

```python
class ArchiveRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id to archive")
```

2. Replace `def delete_recurring(...)` with:

```python
@_as_text
def archive_recurring(session: Session, inp: ArchiveRecurringInput) -> str:
    item = recurring.deactivate_recurring(session, inp.recurring_id)
    return format.recurring_deleted(item)
```

- [ ] **Step 4: Create `recurring_restore.py`**

Create `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/tools/recurring_restore.py`:

```python
"""MCP recurring restore tool (ADR-0009): undo an archive_recurring call."""
from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...services import recurring
from .. import format
from .core import _as_text


class RestoreRecurringInput(BaseModel):
    recurring_id: int = Field(description="The recurring item id to restore")


@_as_text
def restore_recurring(session: Session, inp: RestoreRecurringInput) -> str:
    item = recurring.restore_recurring(session, inp.recurring_id)
    return format.recurring_restored(item)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/test_recurring_restore.py tests/mcp/test_temporal.py -v`
Expected: PASS on all tests in both files. The earlier `test_register_temporal_tools_exposes_all_nine` test will FAIL because `TEMPORAL_TOOL_NAMES` still includes `"delete_recurring"`. That is fixed in Task 13.

- [ ] **Step 6: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/tools/recurring_restore.py backend/src/quaestor/mcp/tools/temporal.py backend/tests/mcp/test_recurring_restore.py backend/tests/mcp/test_temporal.py
git commit -m "feat(backend): mcp recurring restore + rename delete_recurring (ADR-0009)"
```

---

### Task 13: Wire all new tools into the registry + smoke test

**Files:**
- Modify: `backend/src/quaestor/mcp/registry.py:1-209`
- Modify: `backend/tests/mcp/test_registry.py:1-50`
- Modify: `backend/tests/mcp/test_server.py:43-86`

**Interfaces:**
- Consumes: every new module from Tasks 2-12; existing `register_core_tools`, `register_temporal_tools`, `register_planning_tools`.
- Produces: seven new tool-name tuples + seven new `register_*_tools(mcp)` functions, all wired into the FastMCP instance.

- [ ] **Step 1: Add new tool-name tuples and register functions to `registry.py`**

Edit `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/registry.py`.

After the existing `TEMPORAL_TOOL_NAMES` tuple (line 42-52), update it: rename `"delete_recurring"` to `"archive_recurring"`:

```python
TEMPORAL_TOOL_NAMES = (
    "create_recurring",
    "list_recurring",
    "plan_payment",
    "confirm_payment",
    "skip_payment",
    "skip_recurring",
    "to_pay",
    "update_recurring",
    "archive_recurring",
)
```

Also update the corresponding decorator inside `register_temporal_tools`:

Replace the existing `@mcp.tool(name="delete_recurring", ...)` block (the last tool in that function) with:

```python
    @mcp.tool(name="archive_recurring", description="Deactivate a recurring item (soft, reversible).")
    def archive_recurring(item: ArchiveRecurringInput) -> str:
        with Session(db.engine) as session:
            return temporal.archive_recurring(session, item)
```

Update the import block at the top of `registry.py` to swap `DeleteRecurringInput` for `ArchiveRecurringInput`:

```python
from .tools.temporal import (
    ArchiveRecurringInput,
    ConfirmPaymentInput,
    CreateRecurringInput,
    ListRecurringInput,
    PlanPaymentInput,
    SkipPaymentInput,
    SkipRecurringInput,
    ToPayInput,
    UpdateRecurringInput,
)
```

Now add new imports and tuples + register functions. Append below the existing import block (after the imports section):

```python
from .tools.masters import (
    ArchiveAccountInput,
    ArchiveCategoryGroupInput,
    ArchiveCategoryInput,
    CreateAccountInput,
    CreateCategoryGroupInput,
    CreateCategoryInput,
    CreateTagInput,
    DeleteTagInput,
    GetAccountInput,
    GetCategoryInput,
    RestoreAccountInput,
    RestoreCategoryGroupInput,
    RestoreCategoryInput,
    UpdateAccountInput,
    UpdateCategoryGroupInput,
    UpdateCategoryInput,
    UpdateTagInput,
)
from .tools.transactions import (
    DeleteTransactionInput,
    GetTransactionInput,
    UpdateTransactionInput,
)
from .tools.settings import GetSettingsInput, UpdateSettingsInput
from .tools.budgets_reads import ListBudgetsInput, SafeToSpendInput
from .tools.goals_reads import GoalsProgressInput, ListGoalsInput
from .tools.reports import MonthlyReportInput
from .tools.recurring_restore import RestoreRecurringInput
```

Add the new tool-name tuples after `PLANNING_TOOL_NAMES`:

```python
ACCOUNTS_TOOL_NAMES = (
    "create_account",
    "update_account",
    "archive_account",
    "restore_account",
    "get_account",
)

CATEGORIES_TOOL_NAMES = (
    "create_category",
    "update_category",
    "archive_category",
    "restore_category",
    "get_category",
)

CATEGORY_GROUPS_TOOL_NAMES = (
    "create_category_group",
    "update_category_group",
    "archive_category_group",
    "restore_category_group",
)

TAGS_TOOL_NAMES = (
    "create_tag",
    "update_tag",
    "delete_tag",
)

TRANSACTIONS_WRITES_TOOL_NAMES = (
    "get_transaction",
    "update_transaction",
    "delete_transaction",
)

SETTINGS_TOOL_NAMES = (
    "get_settings",
    "update_settings",
)

BUDGETS_READS_TOOL_NAMES = (
    "list_budgets",
    "safe_to_spend",
)

GOALS_READS_TOOL_NAMES = (
    "list_goals",
    "goals_progress",
)

REPORTS_TOOL_NAMES = (
    "monthly_report",
)

RECURRING_RESTORE_TOOL_NAMES = (
    "restore_recurring",
)
```

Append the seven new `register_*_tools` functions at the end of `registry.py` (after `register_planning_tools`):

```python
def register_accounts_tools(mcp) -> None:
    @mcp.tool(name="create_account", description="Create a new account.")
    def create_account(inp: CreateAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.create_account(session, inp)

    @mcp.tool(name="update_account", description="Update an account's name or type.")
    def update_account(inp: UpdateAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.update_account(session, inp)

    @mcp.tool(name="archive_account", description="Archive an account (soft, reversible).")
    def archive_account(inp: ArchiveAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.archive_account(session, inp)

    @mcp.tool(name="restore_account", description="Restore an archived account.")
    def restore_account(inp: RestoreAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.restore_account(session, inp)

    @mcp.tool(name="get_account", description="Fetch one account by name.")
    def get_account(inp: GetAccountInput) -> str:
        with Session(db.engine) as session:
            return masters.get_account(session, inp)


def register_categories_tools(mcp) -> None:
    @mcp.tool(name="create_category", description="Create a new category.")
    def create_category(inp: CreateCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.create_category(session, inp)

    @mcp.tool(name="update_category", description="Update a category's fields.")
    def update_category(inp: UpdateCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.update_category(session, inp)

    @mcp.tool(name="archive_category", description="Archive a category (soft, reversible).")
    def archive_category(inp: ArchiveCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.archive_category(session, inp)

    @mcp.tool(name="restore_category", description="Restore an archived category.")
    def restore_category(inp: RestoreCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.restore_category(session, inp)

    @mcp.tool(name="get_category", description="Fetch one category by name.")
    def get_category(inp: GetCategoryInput) -> str:
        with Session(db.engine) as session:
            return masters.get_category(session, inp)


def register_category_groups_tools(mcp) -> None:
    @mcp.tool(name="create_category_group", description="Create a new category group.")
    def create_category_group(inp: CreateCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.create_category_group(session, inp)

    @mcp.tool(name="update_category_group", description="Update a category group's fields.")
    def update_category_group(inp: UpdateCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.update_category_group(session, inp)

    @mcp.tool(name="archive_category_group", description="Archive a category group (soft, reversible).")
    def archive_category_group(inp: ArchiveCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.archive_category_group(session, inp)

    @mcp.tool(name="restore_category_group", description="Restore an archived category group.")
    def restore_category_group(inp: RestoreCategoryGroupInput) -> str:
        with Session(db.engine) as session:
            return masters.restore_category_group(session, inp)


def register_tags_tools(mcp) -> None:
    @mcp.tool(name="create_tag", description="Create a tag (idempotent by name).")
    def create_tag(inp: CreateTagInput) -> str:
        with Session(db.engine) as session:
            return masters.create_tag(session, inp)

    @mcp.tool(name="update_tag", description="Rename a tag.")
    def update_tag(inp: UpdateTagInput) -> str:
        with Session(db.engine) as session:
            return masters.update_tag(session, inp)

    @mcp.tool(name="delete_tag", description="Hard-delete a tag and its transaction links.")
    def delete_tag(inp: DeleteTagInput) -> str:
        with Session(db.engine) as session:
            return masters.delete_tag(session, inp)


def register_transactions_writes_tools(mcp) -> None:
    @mcp.tool(name="get_transaction", description="Fetch one transaction by id.")
    def get_transaction(inp: GetTransactionInput) -> str:
        with Session(db.engine) as session:
            return tx_tools.get_transaction(session, inp)

    @mcp.tool(name="update_transaction", description="Edit a transaction's payee/notes/category/date.")
    def update_transaction(inp: UpdateTransactionInput) -> str:
        with Session(db.engine) as session:
            return tx_tools.update_transaction(session, inp)

    @mcp.tool(name="delete_transaction", description="Delete a transaction and reverse its balance effect.")
    def delete_transaction(inp: DeleteTransactionInput) -> str:
        with Session(db.engine) as session:
            return tx_tools.delete_transaction(session, inp)


def register_settings_tools(mcp) -> None:
    @mcp.tool(name="get_settings", description="Fetch app settings.")
    def get_settings(inp: GetSettingsInput) -> str:
        with Session(db.engine) as session:
            return settings_tools.get_settings(session, inp)

    @mcp.tool(name="update_settings", description="Update app settings.")
    def update_settings(inp: UpdateSettingsInput) -> str:
        with Session(db.engine) as session:
            return settings_tools.update_settings(session, inp)


def register_budgets_reads_tools(mcp) -> None:
    @mcp.tool(name="list_budgets", description="List budget envelopes for a month.")
    def list_budgets(inp: ListBudgetsInput) -> str:
        with Session(db.engine) as session:
            return budgets_reads.list_budgets(session, inp)

    @mcp.tool(name="safe_to_spend", description="Get the safe-to-spend headline for a month.")
    def safe_to_spend(inp: SafeToSpendInput) -> str:
        with Session(db.engine) as session:
            return budgets_reads.safe_to_spend(session, inp)


def register_goals_reads_tools(mcp) -> None:
    @mcp.tool(name="list_goals", description="List all savings goals.")
    def list_goals(inp: ListGoalsInput) -> str:
        with Session(db.engine) as session:
            return goals_reads.list_goals(session, inp)

    @mcp.tool(name="goals_progress", description="Show progress for active goals.")
    def goals_progress(inp: GoalsProgressInput) -> str:
        with Session(db.engine) as session:
            return goals_reads.goals_progress(session, inp)


def register_reports_tools(mcp) -> None:
    @mcp.tool(name="monthly_report", description="Build the retrospective monthly report.")
    def monthly_report(inp: MonthlyReportInput) -> str:
        with Session(db.engine) as session:
            return reports.monthly_report(session, inp)


def register_recurring_restore_tools(mcp) -> None:
    @mcp.tool(name="restore_recurring", description="Re-activate a deactivated recurring item.")
    def restore_recurring(inp: RestoreRecurringInput) -> str:
        with Session(db.engine) as session:
            return recurring_restore.restore_recurring(session, inp)
```

Add to the imports at the top of `registry.py` (alongside the other module imports):

```python
from .tools import (
    budgets_reads, goals_reads, masters, recurring_restore, reports,
    settings as settings_tools, transactions as tx_tools,
)
```

Update `register_temporal_tools`'s `delete_recurring` block (already done in step 1 of this task).

- [ ] **Step 2: Wire the new register functions into `build_mcp()`**

Edit `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/server.py:16-25`. Update the import:

```python
from .registry import (
    register_accounts_tools,
    register_budgets_reads_tools,
    register_category_groups_tools,
    register_categories_tools,
    register_core_tools,
    register_goals_reads_tools,
    register_planning_tools,
    register_recurring_restore_tools,
    register_reports_tools,
    register_settings_tools,
    register_tags_tools,
    register_temporal_tools,
    register_transactions_writes_tools,
)
```

Update `build_mcp`:

```python
def build_mcp() -> FastMCP:
    """A FastMCP instance with every P2/P3/P4/P5/ADR-0009 tool registered."""
    mcp = FastMCP("Quaestor", json_response=True)
    register_core_tools(mcp)
    register_temporal_tools(mcp)
    register_planning_tools(mcp)
    register_accounts_tools(mcp)
    register_categories_tools(mcp)
    register_category_groups_tools(mcp)
    register_tags_tools(mcp)
    register_transactions_writes_tools(mcp)
    register_settings_tools(mcp)
    register_budgets_reads_tools(mcp)
    register_goals_reads_tools(mcp)
    register_reports_tools(mcp)
    register_recurring_restore_tools(mcp)
    return mcp
```

- [ ] **Step 3: Extend `test_registry.py` to assert each new tuple ⊂ registered**

Append to `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_registry.py`:

```python
from quaestor.mcp.registry import (
    ACCOUNTS_TOOL_NAMES, CATEGORIES_TOOL_NAMES, CATEGORY_GROUPS_TOOL_NAMES,
    TAGS_TOOL_NAMES, TRANSACTIONS_WRITES_TOOL_NAMES, SETTINGS_TOOL_NAMES,
    BUDGETS_READS_TOOL_NAMES, GOALS_READS_TOOL_NAMES, REPORTS_TOOL_NAMES,
    RECURRING_RESTORE_TOOL_NAMES,
)
from quaestor.mcp.registry import (
    register_accounts_tools, register_categories_tools,
    register_category_groups_tools, register_tags_tools,
    register_transactions_writes_tools, register_settings_tools,
    register_budgets_reads_tools, register_goals_reads_tools,
    register_reports_tools, register_recurring_restore_tools,
)


def test_register_accounts_tools_exposes_all_five():
    mcp = FastMCP("test")
    register_accounts_tools(mcp)
    names = _tool_names(mcp)
    assert set(ACCOUNTS_TOOL_NAMES) <= names
    assert len(ACCOUNTS_TOOL_NAMES) == 5


def test_register_categories_tools_exposes_all_five():
    mcp = FastMCP("test")
    register_categories_tools(mcp)
    assert set(CATEGORIES_TOOL_NAMES) <= _tool_names(mcp)
    assert len(CATEGORIES_TOOL_NAMES) == 5


def test_register_category_groups_tools_exposes_all_four():
    mcp = FastMCP("test")
    register_category_groups_tools(mcp)
    assert set(CATEGORY_GROUPS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(CATEGORY_GROUPS_TOOL_NAMES) == 4


def test_register_tags_tools_exposes_all_three():
    mcp = FastMCP("test")
    register_tags_tools(mcp)
    assert set(TAGS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(TAGS_TOOL_NAMES) == 3


def test_register_transactions_writes_tools_exposes_all_three():
    mcp = FastMCP("test")
    register_transactions_writes_tools(mcp)
    assert set(TRANSACTIONS_WRITES_TOOL_NAMES) <= _tool_names(mcp)
    assert len(TRANSACTIONS_WRITES_TOOL_NAMES) == 3


def test_register_settings_tools_exposes_both():
    mcp = FastMCP("test")
    register_settings_tools(mcp)
    assert set(SETTINGS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(SETTINGS_TOOL_NAMES) == 2


def test_register_budgets_reads_tools_exposes_both():
    mcp = FastMCP("test")
    register_budgets_reads_tools(mcp)
    assert set(BUDGETS_READS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(BUDGETS_READS_TOOL_NAMES) == 2


def test_register_goals_reads_tools_exposes_both():
    mcp = FastMCP("test")
    register_goals_reads_tools(mcp)
    assert set(GOALS_READS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(GOALS_READS_TOOL_NAMES) == 2


def test_register_reports_tools_exposes_one():
    mcp = FastMCP("test")
    register_reports_tools(mcp)
    assert set(REPORTS_TOOL_NAMES) <= _tool_names(mcp)
    assert len(REPORTS_TOOL_NAMES) == 1


def test_register_recurring_restore_tools_exposes_one():
    mcp = FastMCP("test")
    register_recurring_restore_tools(mcp)
    assert set(RECURRING_RESTORE_TOOL_NAMES) <= _tool_names(mcp)
    assert len(RECURRING_RESTORE_TOOL_NAMES) == 1


def test_build_mcp_registers_every_new_group():
    import asyncio
    mcp = server.build_mcp()
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    for grp in (
        ACCOUNTS_TOOL_NAMES, CATEGORIES_TOOL_NAMES, CATEGORY_GROUPS_TOOL_NAMES,
        TAGS_TOOL_NAMES, TRANSACTIONS_WRITES_TOOL_NAMES, SETTINGS_TOOL_NAMES,
        BUDGETS_READS_TOOL_NAMES, GOALS_READS_TOOL_NAMES, REPORTS_TOOL_NAMES,
        RECURRING_RESTORE_TOOL_NAMES,
    ):
        assert set(grp) <= names, f"missing tools: {set(grp) - names}"
    # And the renamed one is present, not the old name.
    assert "archive_recurring" in names
    assert "delete_recurring" not in names
```

Note: this requires `server` to be importable in the test. Add at the top of `test_registry.py`:

```python
from quaestor.mcp import server
```

- [ ] **Step 4: Update `test_server.py` for the renamed tool**

In `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_server.py`, the existing `test_build_mcp_registers_core_tools` checks `CORE_TOOL_NAMES <= names`. That still works. No change needed.

But the file `test_temporal.py` has `assert names == set(TEMPORAL_TOOL_NAMES)` (line 111). Since `TEMPORAL_TOOL_NAMES` now contains `archive_recurring` instead of `delete_recurring`, that test passes against the new tuple. No change.

- [ ] **Step 5: Run the full MCP test suite**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest tests/mcp/ -v`
Expected: all green. Total ≈ existing 35 + new ~50 = ~85 tests.

- [ ] **Step 6: End-to-end smoke test through the ASGI app**

Append to `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_server.py`:

```python
def test_build_mcp_exposes_all_fifty_two_tools(monkeypatch, engine):
    """ADR-0009: total tool count after the gap closure is 52."""
    import asyncio
    monkeypatch.setattr(db, "engine", engine)
    mcp = server.build_mcp()
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert len(names) == 52
```

- [ ] **Step 7: Run the full backend test suite to confirm nothing else regressed**

Run: `cd /Users/angelozdev/me/quaestor/backend && python -m pytest -v`
Expected: all green (API tests + domain tests + MCP tests).

- [ ] **Step 8: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add backend/src/quaestor/mcp/registry.py backend/src/quaestor/mcp/server.py backend/tests/mcp/test_registry.py backend/tests/mcp/test_server.py
git commit -m "feat(backend): wire all parity-gap tools into mcp registry (ADR-0009)"
```

---

## Self-Review (run after writing the plan)

When the plan is complete:

1. **Spec coverage:** every ADR-0009 must-have maps to a task:
   - Masters CRUD (17) → Tasks 3, 4, 5, 6.
   - Transactions writes (3) → Task 7.
   - Settings (2) → Task 8.
   - Budgets reads (2) → Task 9.
   - Goals reads (2) → Task 10.
   - Reports (1) → Task 11.
   - Recurring restore + rename → Task 12.
   - ADR → Task 1.
   - Formatters → Task 2.
   - Wiring + smoke → Task 13.
2. **Placeholder scan:** every step has full code or commands; no "TBD", "TODO", "implement later", "fill in details", "similar to Task N", "appropriate error handling".
3. **Type consistency:** `_resolve_category` reused everywhere; `archive_recurring` name consistent across `temporal.py`, `test_temporal.py`, `TEMPORAL_TOOL_NAMES`, and `test_recurring_restore.py`. `_as_text` wrapper signature `(session, inp) -> str` consistent.

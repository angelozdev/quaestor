# P5 — Reports + Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the monthly report (`monthly_report`) and the atomic bulk CSV importer (`import_csv`) as pure aggregation/formatting/ingestion services that reuse P0/P3/P4 — exposing a stable data contract for P1/P2/P6 to wire later.

**Architecture:** Four new files. `domain/report_types.py` holds the contract dataclasses. `domain/report_markdown.py` is a pure `MonthlyReport -> str` renderer with zero I/O. `services/reports.py` aggregates posted data (income/expense/net, by-category, by-group, MoM drift, USD share) and reuses P4 (`budget_status`, `safe_to_spend`, `goals_progress`) + P3 (`to_pay`) for envelopes/goals/pending, then calls the renderer. `services/importer.py` validates a custom CSV row-by-row in memory and only inserts (via P0 `record_expense`/`record_income`) when every row is valid — atomicity by validate-first.

**Tech Stack:** Python 3.12, SQLModel/SQLAlchemy, in-memory SQLite for tests, `pytest` (run via `uv run pytest`), stdlib `csv`.

## Global Constraints

These apply to every task. Values copied from the P5 spec and the governing ADRs.

- **Money is integer cents.** Every report aggregate is in `to_base` (COP cents), already frozen on each transaction at record time — the report **never** reconverts FX. Account balances are in the account's own currency (cents).
- **Only `posted` counts** in income/expense/net/by-category/by-group/USD-share/balances. `planned` and `skipped` never add to these.
- **Transfers are excluded** from income/expense/by-category/by-group (filter by `type`). They still affect account balances (already reflected in `Account.balance`).
- **`exclude_from_totals` is respected** by report totals/by-category/by-group/USD-share (a transaction whose category has `exclude_from_totals=True` is dropped). `exclude_from_budget` is handled inside P4's `budget_status` for envelopes — the report does not re-apply it.
- **Session-first signatures.** Every service in this codebase takes `session: Session` as its first argument. The spec writes `monthly_report(month)` / `import_csv(content)` conceptually; the real signatures are `monthly_report(session, month, *, today=None)` and `import_csv(session, content, *, dry_run=False)`.
- **`SafeToSpend` is reused, not redefined.** `domain/report_types.py` re-exports P4's `SafeToSpend` from `domain/dtos.py` so the contract has a single source of truth. `MonthlyReport.safe_to_spend` holds that DTO.
- **Decision (transfers in importer):** a row with `type=transfer` is recognised as a valid type but is **rejected** with `RowError(line, "transfer import not supported in v1")`. The single-`account` CSV cannot express a transfer's source+destination; v1 import covers `expense`/`income` only (the bulk of an LM backfill, ADR-009). Because the importer is atomic, any transfer row makes the whole file fail with `ok=False, inserted=0`.
- **Decision (optional category in importer):** per ADR-024 (optional category), an **empty** `category` on an `expense`/`income` row is allowed and yields `category_id=None`. A **non-empty but unknown** category name is an error. (This relaxes the P5 spec table's "empty allowed only if transfer"; ADR-024 is the governing decision per `CLAUDE.md`.)
- **Units:** `CategorySection.pct` and `GroupSection.pct` are percentages of total expense in `[0, 100]` (float, unrounded). `usd_share` is a fraction in `[0, 1]` (float). The renderer multiplies `usd_share` by 100 for display.
- **No wiring.** P5 ships the services + contract only. Endpoints (P1), MCP tools (P2), and screens (P6) are out of scope.
- **Test command:** `uv run pytest` from the `backend/` directory (config: `pythonpath=["src"]`, `testpaths=["tests"]`). Package import root is `quaestor`.

---

## File Structure

- `backend/src/quaestor/domain/report_types.py` — **new.** Contract dataclasses: `EnvelopesSummary`, `EnvelopeLine`, `CategorySection`, `GroupSection`, `GoalLine`, `AccountBalance`, `DriftMoM`, `MonthlyReport`, `RowError`, `ImportResult`; re-exports `SafeToSpend`.
- `backend/src/quaestor/domain/report_markdown.py` — **new.** Pure `render_markdown(report) -> str` + `money(cents, currency)` formatter. No DB, no session.
- `backend/src/quaestor/services/reports.py` — **new.** `monthly_report` + private aggregation helpers.
- `backend/src/quaestor/services/importer.py` — **new.** `import_csv` + private parser/row-validation.
- `backend/tests/domain/test_report_types.py` — **new.** Contract smoke tests.
- `backend/tests/domain/test_report_markdown.py` — **new.** Renderer tests (pure, hand-built reports).
- `backend/tests/services/test_reports.py` — **new.** Aggregation + assembly tests (in-memory SQLite).
- `backend/tests/services/test_importer.py` — **new.** Importer validation/atomicity/insert tests.

Reuses, unchanged: `services/transactions.py` (`record_expense`, `record_income`, `list_transactions`, `delete_transaction`), `services/budgets.py` (`budget_status`, `safe_to_spend`), `services/goals.py` (`goals_progress`), `services/planned.py` (`to_pay`), `services/accounts.py` (`list_accounts`), `services/categories.py` (`list_categories`), `services/fx.py` (`get_current_rate`), `services/tags.py` (`list_tags`, `tag_transaction`), `domain/rules.py` (`month_bounds`, `prev_year_month`), `domain/money.py` (`cents_to_major`, `major_to_cents`), `domain/dtos.py` (`SafeToSpend`, `BudgetStatus`, `GoalProgress`).

---

### Task 1: Contract dataclasses (`domain/report_types.py`)

**Files:**
- Create: `backend/src/quaestor/domain/report_types.py`
- Test: `backend/tests/domain/test_report_types.py`

**Interfaces:**
- Consumes: `SafeToSpend` from `quaestor.domain.dtos`.
- Produces: the dataclasses below. Field names/types here are the contract every later task and P1/P2/P6 rely on.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domain/test_report_types.py`:

```python
from datetime import date

from quaestor.domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GoalLine,
    GroupSection,
    ImportResult,
    MonthlyReport,
    RowError,
    SafeToSpend,  # re-exported from dtos
)


def test_safe_to_spend_is_reexported_from_dtos():
    from quaestor.domain import dtos
    assert SafeToSpend is dtos.SafeToSpend


def test_value_types_hold_their_fields():
    summary = EnvelopesSummary(n_green=2, n_red=1, rollover_generated=5000)
    assert (summary.n_green, summary.n_red, summary.rollover_generated) == (2, 1, 5000)

    line = EnvelopeLine(
        category="Food", allocated=100, rollover_in=10, spent=40,
        available=70, status="under",
    )
    assert line.category == "Food" and line.available == 70

    cat = CategorySection(category="Food", group="Essentials", total=400, pct=25.0)
    assert cat.group == "Essentials" and cat.pct == 25.0

    grp = GroupSection(group="Essentials", total=400, pct=25.0)
    assert grp.group == "Essentials"

    goal = GoalLine(name="Trip", accumulated=300)
    assert goal.target is None and goal.eta is None and goal.on_track is None

    bal = AccountBalance(account="Bank", currency="COP", balance=999)
    assert bal.currency == "COP"

    drift = DriftMoM(
        prev_month="2026-05", income_abs=10, income_pct=5.0,
        expense_abs=-20, expense_pct=None, net_abs=30, net_pct=None,
    )
    assert drift.prev_month == "2026-05" and drift.expense_pct is None


def test_import_result_and_row_error():
    err = RowError(line=2, reason="invalid date '2026-13-40'")
    res = ImportResult(ok=False, inserted=0, tags_created=[], errors=[err], dry_run=True)
    assert res.ok is False and res.errors[0].line == 2 and res.dry_run is True


def test_monthly_report_markdown_is_mutable():
    sts = SafeToSpend(
        year_month="2026-06", income_forecast=0, committed=0,
        assigned_envelopes=0, free=12345, committed_breakdown=[],
    )
    report = MonthlyReport(
        month="2026-06", income=0, expense=0, net=0,
        envelopes_summary=EnvelopesSummary(0, 0, 0), envelopes=[],
        by_category=[], by_group=[], goals=[], balances=[],
        drift_mom=None, usd_share=0.0, pending=[], safe_to_spend=sts, markdown="",
    )
    report.markdown = "rendered"  # must be reassignable (renderer fills it last)
    assert report.markdown == "rendered"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domain/test_report_types.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.domain.report_types'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/quaestor/domain/report_types.py`:

```python
"""P5 contract dataclasses for the monthly report and the CSV importer.

These are the stable types P1 (endpoints), P2 (MCP tools), and P6 (screens) wire
against. SafeToSpend is reused from P4 (domain.dtos) — single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .dtos import SafeToSpend  # re-exported on purpose

__all__ = [
    "SafeToSpend",
    "EnvelopesSummary",
    "EnvelopeLine",
    "CategorySection",
    "GroupSection",
    "GoalLine",
    "AccountBalance",
    "DriftMoM",
    "MonthlyReport",
    "RowError",
    "ImportResult",
]


@dataclass(frozen=True)
class EnvelopesSummary:
    n_green: int  # envelopes with status "under"
    n_red: int  # envelopes with status "over"
    rollover_generated: int  # Σ max(available, 0), COP cents — rolls into next month


@dataclass(frozen=True)
class EnvelopeLine:
    category: str
    allocated: int  # assigned, COP cents
    rollover_in: int  # COP cents
    spent: int  # COP cents
    available: int  # COP cents
    status: str  # "over" | "under"


@dataclass(frozen=True)
class CategorySection:
    category: str
    group: str | None
    total: int  # COP cents
    pct: float  # percentage of total expense, [0, 100]


@dataclass(frozen=True)
class GroupSection:
    group: str
    total: int  # COP cents
    pct: float  # percentage of total expense, [0, 100]


@dataclass(frozen=True)
class GoalLine:
    name: str
    accumulated: int  # saved, COP cents
    target: int | None = None  # COP cents; None => open-ended
    eta: date | None = None  # only on defined goals
    on_track: bool | None = None  # only on defined goals


@dataclass(frozen=True)
class AccountBalance:
    account: str
    currency: str
    balance: int  # cents, in the account's own currency


@dataclass(frozen=True)
class DriftMoM:
    prev_month: str
    income_abs: int  # current - previous, COP cents
    income_pct: float | None  # None when previous == 0
    expense_abs: int
    expense_pct: float | None
    net_abs: int
    net_pct: float | None


@dataclass
class MonthlyReport:  # not frozen: markdown is filled in after the data is built
    month: str
    income: int  # COP cents, posted only
    expense: int
    net: int  # income - expense
    envelopes_summary: EnvelopesSummary
    envelopes: list[EnvelopeLine]
    by_category: list[CategorySection]
    by_group: list[GroupSection]
    goals: list[GoalLine]
    balances: list[AccountBalance]
    drift_mom: DriftMoM | None  # None on cold start (no previous-month activity)
    usd_share: float  # fraction of expense originated in USD, [0, 1]
    pending: list[str]  # alert lines: unconfirmed manual entries
    safe_to_spend: SafeToSpend  # closing line, not headline (ADR-019)
    markdown: str


@dataclass(frozen=True)
class RowError:
    line: int
    reason: str


@dataclass(frozen=True)
class ImportResult:
    ok: bool
    inserted: int  # 0 if not ok or dry_run
    tags_created: list[str]
    errors: list[RowError]
    dry_run: bool
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/domain/test_report_types.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/report_types.py backend/tests/domain/test_report_types.py
git commit -m "feat(p5): add report/importer contract dataclasses"
```

---

### Task 2: Pure markdown renderer (`domain/report_markdown.py`)

**Files:**
- Create: `backend/src/quaestor/domain/report_markdown.py`
- Test: `backend/tests/domain/test_report_markdown.py`

**Interfaces:**
- Consumes: `MonthlyReport` and all value types from Task 1; `SafeToSpend` from dtos; `cents_to_major` from `domain.money`.
- Produces:
  - `money(cents: int, currency: str = "COP") -> str` — e.g. `money(1234567) == "$12,345.67 COP"`.
  - `render_markdown(report: MonthlyReport) -> str` — deterministic. Section order (ADR-019): headline net → envelopes → by category → by group → goals → balances → MoM/USD → pending → safe-to-spend (closing). Reads every field except `markdown`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domain/test_report_markdown.py`:

```python
from datetime import date

from quaestor.domain.dtos import SafeToSpend
from quaestor.domain.report_markdown import money, render_markdown
from quaestor.domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GoalLine,
    GroupSection,
    MonthlyReport,
)


def _full_report():
    return MonthlyReport(
        month="2026-06",
        income=5_000_000, expense=3_000_000, net=2_000_000,
        envelopes_summary=EnvelopesSummary(n_green=2, n_red=1, rollover_generated=150_000),
        envelopes=[
            EnvelopeLine("Food", 1_000_000, 0, 800_000, 200_000, "under"),
            EnvelopeLine("Fun", 200_000, 0, 250_000, -50_000, "over"),
        ],
        by_category=[
            CategorySection("Food", "Essentials", 800_000, 26.666666666666668),
            CategorySection("Uncategorized", None, 100_000, 3.3333333333333335),
        ],
        by_group=[GroupSection("Essentials", 800_000, 26.666666666666668)],
        goals=[
            GoalLine("Trip", 600_000, target=1_200_000, eta=date(2026, 12, 1), on_track=True),
            GoalLine("Buffer", 300_000),
        ],
        balances=[AccountBalance("Bank", "COP", 9_000_000), AccountBalance("USD Wallet", "USD", 12_345)],
        drift_mom=DriftMoM("2026-05", 100_000, 2.0, -50_000, -1.5, 150_000, None),
        usd_share=0.25,
        pending=["Bank: $40,000.00 COP pending"],
        safe_to_spend=SafeToSpend("2026-06", 0, 0, 0, 1_750_000, []),
        markdown="",
    )


def test_money_formats_cents_with_currency():
    assert money(1_234_567) == "$12,345.67 COP"
    assert money(12_345, "USD") == "$123.45 USD"
    assert money(0) == "$0.00 COP"


def test_render_is_deterministic():
    report = _full_report()
    assert render_markdown(report) == render_markdown(report)


def test_render_headline_and_section_order():
    out = render_markdown(_full_report())
    # headline = net + envelope performance (ADR-019)
    assert "# Monthly report — 2026-06" in out
    assert "**Net:** $20,000.00 COP" in out
    assert "2 green / 1 red" in out
    # section ordering: net before envelopes before categories before closing
    assert out.index("Net:") < out.index("## Envelopes")
    assert out.index("## Envelopes") < out.index("## Expense by category")
    assert out.index("## Expense by category") < out.index("## Goals")
    assert out.index("## Goals") < out.index("## Account balances")
    assert out.index("## Account balances") < out.index("## Month-over-month")
    assert out.index("## Month-over-month") < out.index("## Closing")
    # safe-to-spend is the closing line, not the headline
    assert "You closed with $17,500.00 COP free" in out


def test_render_goal_eta_only_on_defined_goals():
    out = render_markdown(_full_report())
    assert "Trip" in out and "ETA 2026-12-01" in out and "on track" in out
    assert "Buffer" in out and "open-ended" in out


def test_render_usd_share_as_percentage():
    out = render_markdown(_full_report())
    assert "USD share of expense: 25.0%" in out


def test_render_cold_start_drift_none():
    report = _full_report()
    report.drift_mom = None
    out = render_markdown(report)
    assert "cold start" in out.lower()


def test_render_empty_sections_do_not_crash():
    report = MonthlyReport(
        month="2026-06", income=0, expense=0, net=0,
        envelopes_summary=EnvelopesSummary(0, 0, 0), envelopes=[],
        by_category=[], by_group=[], goals=[], balances=[],
        drift_mom=None, usd_share=0.0, pending=[],
        safe_to_spend=SafeToSpend("2026-06", 0, 0, 0, 0, []), markdown="",
    )
    out = render_markdown(report)
    assert "# Monthly report — 2026-06" in out
    assert "## Closing" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domain/test_report_markdown.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.domain.report_markdown'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/quaestor/domain/report_markdown.py`:

```python
"""Pure renderer: MonthlyReport -> markdown string. No I/O, no session.

Both views (MCP chat in P2, the /reports screen in P6) consume the same object;
this module turns its data into the markdown half. Section order follows ADR-019:
the headline is net + envelope performance; safe-to-spend is the closing line.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .money import cents_to_major

if TYPE_CHECKING:
    from .report_types import MonthlyReport


def money(cents: int, currency: str = "COP") -> str:
    """Format integer cents, e.g. 1234567 -> '$12,345.67 COP'."""
    return f"${cents_to_major(cents):,.2f} {currency}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def render_markdown(report: "MonthlyReport") -> str:
    lines: list[str] = []

    # 1. Headline — net + envelope performance (ADR-019)
    lines.append(f"# Monthly report — {report.month}")
    lines.append("")
    lines.append(
        f"**Net:** {money(report.net)}  "
        f"(income {money(report.income)} − expense {money(report.expense)})"
    )
    s = report.envelopes_summary
    lines.append(
        f"**Envelopes:** {s.n_green} green / {s.n_red} red · "
        f"rollover generated {money(s.rollover_generated)}"
    )
    lines.append("")

    # 2. Envelopes detail
    lines.append("## Envelopes")
    if report.envelopes:
        lines.append("| Category | Allocated | Rollover in | Spent | Available | Status |")
        lines.append("|---|---|---|---|---|---|")
        for e in report.envelopes:
            lines.append(
                f"| {e.category} | {money(e.allocated)} | {money(e.rollover_in)} | "
                f"{money(e.spent)} | {money(e.available)} | {e.status} |"
            )
    else:
        lines.append("_No envelopes this month._")
    lines.append("")

    # 3. Expense by category
    lines.append("## Expense by category")
    if report.by_category:
        lines.append("| Category | Group | Total | % |")
        lines.append("|---|---|---|---|")
        for c in report.by_category:
            lines.append(
                f"| {c.category} | {c.group or '—'} | {money(c.total)} | {_pct(c.pct)} |"
            )
    else:
        lines.append("_No expenses this month._")
    lines.append("")

    # 4. Expense by group
    lines.append("## Expense by group")
    if report.by_group:
        lines.append("| Group | Total | % |")
        lines.append("|---|---|---|")
        for g in report.by_group:
            lines.append(f"| {g.group} | {money(g.total)} | {_pct(g.pct)} |")
    else:
        lines.append("_No expenses this month._")
    lines.append("")

    # 5. Goals — ETA/on-track only on defined goals
    lines.append("## Goals")
    if report.goals:
        for g in report.goals:
            if g.target is not None:
                track = "on track" if g.on_track else "behind"
                eta = g.eta.isoformat() if g.eta else "—"
                lines.append(
                    f"- **{g.name}**: {money(g.accumulated)} / {money(g.target)} "
                    f"· ETA {eta} · {track}"
                )
            else:
                lines.append(f"- **{g.name}**: {money(g.accumulated)} (open-ended)")
    else:
        lines.append("_No goals._")
    lines.append("")

    # 6. Account balances
    lines.append("## Account balances")
    if report.balances:
        for b in report.balances:
            lines.append(f"- {b.account}: {money(b.balance, b.currency)}")
    else:
        lines.append("_No accounts._")
    lines.append("")

    # 7. Month-over-month drift + USD share
    lines.append("## Month-over-month")
    if report.drift_mom is not None:
        d = report.drift_mom

        def fmt(abs_v: int, pct_v: float | None) -> str:
            p = f"{pct_v:+.1f}%" if pct_v is not None else "n/a"
            return f"{money(abs_v)} ({p})"

        lines.append(
            f"vs {d.prev_month}: income {fmt(d.income_abs, d.income_pct)}, "
            f"expense {fmt(d.expense_abs, d.expense_pct)}, "
            f"net {fmt(d.net_abs, d.net_pct)}"
        )
    else:
        lines.append("_No previous month to compare (cold start)._")
    lines.append(f"USD share of expense: {report.usd_share * 100:.1f}%")
    lines.append("")

    # 8. Pending confirmations (only when present)
    if report.pending:
        lines.append("## Pending confirmations")
        for p in report.pending:
            lines.append(f"- {p}")
        lines.append("")

    # 9. Closing — safe-to-spend (ADR-019: not a headline)
    lines.append("## Closing")
    lines.append(f"You closed with {money(report.safe_to_spend.free)} free to spend.")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/domain/test_report_markdown.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/domain/report_markdown.py backend/tests/domain/test_report_markdown.py
git commit -m "feat(p5): add pure markdown renderer for monthly report"
```

---

### Task 3: Reports — income/expense/net + USD share (`services/reports.py`)

**Files:**
- Create: `backend/src/quaestor/services/reports.py`
- Test: `backend/tests/services/test_reports.py`

**Interfaces:**
- Consumes: `Transaction`, `Category`, `TxType`, `TxStatus` from models; `month_bounds` from rules; `ValidationError` from errors.
- Produces (private, used by later report tasks):
  - `_validate_month(month: str) -> None` — raises `ValidationError` on non-`YYYY-MM`.
  - `_posted_for_totals(session, tx_type: TxType, start, end) -> list[Transaction]` — posted txs of `tx_type` in `[start, end]`, dropping any whose category has `exclude_from_totals=True`.
  - `_totals(session, start, end) -> tuple[int, int, int]` — `(income, expense, net)`.
  - `_usd_share(expenses: list[Transaction], expense_total: int) -> float` — fraction in `[0, 1]`, `0.0` when `expense_total == 0`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_reports.py`:

```python
from datetime import date

import pytest

from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType, TxType
from quaestor.domain.rules import month_bounds
from quaestor.services import accounts, categories, reports, transactions


def _acc(session, currency="COP", balance=100_000_000):
    return accounts.create_account(session, f"Acc {currency}", AccountType.debit, currency, balance=balance)


def _cat(session, name="Food", **kw):
    return categories.create_category(session, name=name, **kw)


def test_validate_month_rejects_malformed(session):
    with pytest.raises(ValidationError):
        reports._validate_month("2026-13")
    with pytest.raises(ValidationError):
        reports._validate_month("June")
    reports._validate_month("2026-06")  # no raise


def test_totals_posted_only_excludes_planned_and_transfer(session):
    from quaestor.services import planned
    acc = _acc(session)
    acc2 = _acc(session, currency="COP")
    cat = _cat(session)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "groceries", category_id=cat.id)
    transactions.record_income(session, acc.id, 80_000, "COP", date(2026, 6, 1), "salary", category_id=cat.id)
    transactions.transfer(session, acc.id, acc2.id, 10_000, "COP", date(2026, 6, 6))  # excluded
    planned.plan_payment(session, payee="rent", amount=50_000, currency="COP",
                         account_id=acc.id, date=date(2026, 6, 10), category_id=cat.id)  # planned, excluded
    start, end = month_bounds("2026-06")
    income, expense, net = reports._totals(session, start, end)
    assert income == 80_000
    assert expense == 30_000
    assert net == 50_000


def test_totals_respect_exclude_from_totals(session):
    acc = _acc(session)
    normal = _cat(session, name="Food")
    excluded = _cat(session, name="Reimbursable", exclude_from_totals=True)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=normal.id)
    transactions.record_expense(session, acc.id, 99_000, "COP", date(2026, 6, 7), "reimb", category_id=excluded.id)
    start, end = month_bounds("2026-06")
    _, expense, _ = reports._totals(session, start, end)
    assert expense == 30_000


def test_usd_share(session):
    acc_cop = _acc(session, currency="COP")
    acc_usd = _acc(session, currency="USD")
    from quaestor.services import fx
    fx.set_fx_rate(session, date(2026, 6, 1), 4000)
    cat = _cat(session)
    transactions.record_expense(session, acc_cop.id, 300_000, "COP", date(2026, 6, 5), "cop", category_id=cat.id)
    # 25 USD * 4000 = 100_000 COP cents to_base
    transactions.record_expense(session, acc_usd.id, 25, "USD", date(2026, 6, 6), "usd", category_id=cat.id)
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    expense_total = sum(t.to_base for t in expenses)
    assert expense_total == 400_000
    assert reports._usd_share(expenses, expense_total) == pytest.approx(0.25)


def test_usd_share_zero_when_no_expense(session):
    assert reports._usd_share([], 0) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.services.reports'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/quaestor/services/reports.py`:

```python
"""Monthly report: posted-only aggregation + formatting (P5).

Reuses P0 (reads), P3 (to_pay), P4 (budget_status, safe_to_spend, goals_progress).
Every aggregate is in to_base (COP cents); FX is never reconverted here.
"""
from __future__ import annotations

import re
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.errors import ValidationError
from ..domain.models import Category, Transaction, TxStatus, TxType
from ..domain.rules import month_bounds

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_month(month: str) -> None:
    if not _MONTH_RE.match(month):
        raise ValidationError(f"malformed month (expected YYYY-MM): {month!r}")


def _posted_for_totals(
    session: Session, tx_type: TxType, start: Date, end: Date
) -> list[Transaction]:
    """Posted txs of one type in [start, end], minus exclude_from_totals categories."""
    rows = session.exec(
        select(Transaction).where(
            Transaction.type == tx_type,
            Transaction.status == TxStatus.posted,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    ).all()
    kept: list[Transaction] = []
    for tx in rows:
        if tx.category_id is not None:
            cat = session.get(Category, tx.category_id)
            if cat is not None and cat.exclude_from_totals:
                continue
        kept.append(tx)
    return kept


def _totals(session: Session, start: Date, end: Date) -> tuple[int, int, int]:
    """(income, expense, net) in COP cents — posted, transfers/planned excluded."""
    expenses = _posted_for_totals(session, TxType.expense, start, end)
    incomes = _posted_for_totals(session, TxType.income, start, end)
    expense = sum(t.to_base for t in expenses)
    income = sum(t.to_base for t in incomes)
    return income, expense, income - expense


def _usd_share(expenses: list[Transaction], expense_total: int) -> float:
    """Fraction of expense (to_base) originated in USD, [0, 1]. 0.0 if no expense."""
    if expense_total == 0:
        return 0.0
    usd = sum(t.to_base for t in expenses if t.currency == "USD")
    return usd / expense_total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/reports.py backend/tests/services/test_reports.py
git commit -m "feat(p5): report income/expense/net + usd share aggregates"
```

---

### Task 4: Reports — by-category + by-group sections

**Files:**
- Modify: `backend/src/quaestor/services/reports.py`
- Test: `backend/tests/services/test_reports.py` (append)

**Interfaces:**
- Consumes: `_posted_for_totals` (Task 3); `CategoryGroup` from models; `CategorySection`, `GroupSection` from report_types.
- Produces:
  - `_category_sections(session, expenses, expense_total) -> list[CategorySection]` — bucket by category (None → `"Uncategorized"`, group `None`), `pct = total/expense_total*100`, sorted by `(-total, category)`.
  - `_group_sections(session, expenses, expense_total) -> list[GroupSection]` — bucket by `CategoryGroup` name (no group / uncategorized → `"Ungrouped"`), sorted by `(-total, group)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_reports.py`:

```python
def test_category_sections_sorted_with_pct_and_uncategorized(session):
    acc = _acc(session)
    grp = categories.create_group(session, name="Essentials")
    food = _cat(session, name="Food", group_id=grp.id)
    fun = _cat(session, name="Fun", group_id=grp.id)
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 5), "f", category_id=food.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 6), "u", category_id=fun.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 7), "none")  # uncategorized
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    total = sum(t.to_base for t in expenses)
    sections = reports._category_sections(session, expenses, total)
    assert [s.category for s in sections] == ["Food", "Fun", "Uncategorized"]
    assert sections[0].group == "Essentials"
    assert sections[-1].group is None
    assert sections[0].total == 200_000
    assert sections[0].pct == pytest.approx(50.0)


def test_group_sections_rollup(session):
    acc = _acc(session)
    essentials = categories.create_group(session, name="Essentials")
    food = _cat(session, name="Food", group_id=essentials.id)
    rent = _cat(session, name="Rent", group_id=essentials.id)
    loose = _cat(session, name="Loose")  # no group
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 5), "a", category_id=food.id)
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 6), "b", category_id=rent.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 7), "c", category_id=loose.id)
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    total = sum(t.to_base for t in expenses)
    groups = reports._group_sections(session, expenses, total)
    assert [g.group for g in groups] == ["Essentials", "Ungrouped"]
    assert groups[0].total == 300_000
    assert groups[0].pct == pytest.approx(75.0)
    assert groups[1].group == "Ungrouped" and groups[1].total == 100_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_reports.py -k "category_sections or group_sections" -q`
Expected: FAIL with `AttributeError: module 'quaestor.services.reports' has no attribute '_category_sections'`

- [ ] **Step 3: Write minimal implementation**

In `backend/src/quaestor/services/reports.py`, add `CategoryGroup` to the models import and the report_types import, then append the two helpers.

Change the models import line:

```python
from ..domain.models import Category, CategoryGroup, Transaction, TxStatus, TxType
```

Add after the existing imports:

```python
from ..domain.report_types import CategorySection, GroupSection
```

Append:

```python
def _group_name(session: Session, category_id: int | None) -> str | None:
    """Resolve a category's group name, or None when uncategorised/ungrouped."""
    if category_id is None:
        return None
    cat = session.get(Category, category_id)
    if cat is None or cat.group_id is None:
        return None
    grp = session.get(CategoryGroup, cat.group_id)
    return grp.name if grp is not None else None


def _category_sections(
    session: Session, expenses: list[Transaction], expense_total: int
) -> list[CategorySection]:
    """Group expenses by category (None -> 'Uncategorized'); pct over total expense."""
    buckets: dict[int | None, int] = {}
    for tx in expenses:
        buckets[tx.category_id] = buckets.get(tx.category_id, 0) + tx.to_base
    sections: list[CategorySection] = []
    for cat_id, total in buckets.items():
        if cat_id is None:
            name, group = "Uncategorized", None
        else:
            cat = session.get(Category, cat_id)
            name = cat.name if cat is not None else f"category {cat_id}"
            group = _group_name(session, cat_id)
        pct = (total / expense_total * 100) if expense_total > 0 else 0.0
        sections.append(CategorySection(category=name, group=group, total=total, pct=pct))
    sections.sort(key=lambda s: (-s.total, s.category))
    return sections


def _group_sections(
    session: Session, expenses: list[Transaction], expense_total: int
) -> list[GroupSection]:
    """Rollup of expenses by CategoryGroup name; pct over total expense (ADR-023)."""
    buckets: dict[str, int] = {}
    for tx in expenses:
        name = _group_name(session, tx.category_id) or "Ungrouped"
        buckets[name] = buckets.get(name, 0) + tx.to_base
    sections = [
        GroupSection(
            group=name,
            total=total,
            pct=(total / expense_total * 100) if expense_total > 0 else 0.0,
        )
        for name, total in buckets.items()
    ]
    sections.sort(key=lambda s: (-s.total, s.group))
    return sections
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/reports.py backend/tests/services/test_reports.py
git commit -m "feat(p5): report by-category and by-group sections"
```

---

### Task 5: Reports — month-over-month drift

**Files:**
- Modify: `backend/src/quaestor/services/reports.py`
- Test: `backend/tests/services/test_reports.py` (append)

**Interfaces:**
- Consumes: `_totals` (Task 3); `prev_year_month`, `month_bounds` from rules; `DriftMoM` from report_types.
- Produces: `_drift(session, month, income, expense, net) -> DriftMoM | None`. Returns `None` when the previous calendar month has no posted income and no posted expense (cold start). Otherwise `*_abs = current - previous`; `*_pct = (current-previous)/previous*100`, or `None` when the previous value is `0`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_reports.py`:

```python
def test_drift_none_on_cold_start(session):
    acc = _acc(session)
    cat = _cat(session)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=cat.id)
    # no May activity -> cold start
    income, expense, net = reports._totals(session, *month_bounds("2026-06"))
    assert reports._drift(session, "2026-06", income, expense, net) is None


def test_drift_abs_and_pct(session):
    acc = _acc(session)
    cat = _cat(session)
    # May: income 100_000, expense 40_000, net 60_000
    transactions.record_income(session, acc.id, 100_000, "COP", date(2026, 5, 10), "s", category_id=cat.id)
    transactions.record_expense(session, acc.id, 40_000, "COP", date(2026, 5, 11), "x", category_id=cat.id)
    # June: income 150_000, expense 60_000, net 90_000
    transactions.record_income(session, acc.id, 150_000, "COP", date(2026, 6, 10), "s", category_id=cat.id)
    transactions.record_expense(session, acc.id, 60_000, "COP", date(2026, 6, 11), "x", category_id=cat.id)
    income, expense, net = reports._totals(session, *month_bounds("2026-06"))
    d = reports._drift(session, "2026-06", income, expense, net)
    assert d is not None and d.prev_month == "2026-05"
    assert d.income_abs == 50_000 and d.income_pct == pytest.approx(50.0)
    assert d.expense_abs == 20_000 and d.expense_pct == pytest.approx(50.0)
    assert d.net_abs == 30_000 and d.net_pct == pytest.approx(50.0)


def test_drift_pct_none_when_previous_zero(session):
    acc = _acc(session)
    cat = _cat(session)
    # May has expense only (income 0); June has income
    transactions.record_expense(session, acc.id, 10_000, "COP", date(2026, 5, 5), "x", category_id=cat.id)
    transactions.record_income(session, acc.id, 50_000, "COP", date(2026, 6, 5), "s", category_id=cat.id)
    transactions.record_expense(session, acc.id, 10_000, "COP", date(2026, 6, 6), "x", category_id=cat.id)
    income, expense, net = reports._totals(session, *month_bounds("2026-06"))
    d = reports._drift(session, "2026-06", income, expense, net)
    assert d is not None
    assert d.income_abs == 50_000 and d.income_pct is None  # previous income was 0
    assert d.expense_pct == pytest.approx(0.0)  # 10_000 -> 10_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_reports.py -k drift -q`
Expected: FAIL with `AttributeError: module 'quaestor.services.reports' has no attribute '_drift'`

- [ ] **Step 3: Write minimal implementation**

In `reports.py`, add `prev_year_month` to the rules import:

```python
from ..domain.rules import month_bounds, prev_year_month
```

Extend the report_types import:

```python
from ..domain.report_types import CategorySection, DriftMoM, GroupSection
```

Append:

```python
def _drift(
    session: Session, month: str, income: int, expense: int, net: int
) -> DriftMoM | None:
    """MoM drift vs the previous calendar month. None on cold start (no prior activity)."""
    prev = prev_year_month(month)
    p_start, p_end = month_bounds(prev)
    p_income, p_expense, p_net = _totals(session, p_start, p_end)
    if p_income == 0 and p_expense == 0:
        return None

    def pct(curr: int, base: int) -> float | None:
        return ((curr - base) / base * 100) if base != 0 else None

    return DriftMoM(
        prev_month=prev,
        income_abs=income - p_income, income_pct=pct(income, p_income),
        expense_abs=expense - p_expense, expense_pct=pct(expense, p_expense),
        net_abs=net - p_net, net_pct=pct(net, p_net),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/reports.py backend/tests/services/test_reports.py
git commit -m "feat(p5): report month-over-month drift"
```

---

### Task 6: Reports — envelopes + envelopes summary

**Files:**
- Modify: `backend/src/quaestor/services/reports.py`
- Test: `backend/tests/services/test_reports.py` (append)

**Interfaces:**
- Consumes: P4 `budgets.budget_status(session, category_id, year_month) -> BudgetStatus`; `Budget`, `Category` from models; `EnvelopeLine`, `EnvelopesSummary` from report_types.
- Produces: `_envelope_lines(session, month) -> tuple[list[EnvelopeLine], EnvelopesSummary]`. One `EnvelopeLine` per `Budget` in the month (sorted by category name). `n_green` = count `status == "under"`; `n_red` = count `status == "over"`; `rollover_generated` = `Σ max(available, 0)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_reports.py`:

```python
def test_envelope_lines_and_summary(session):
    from quaestor.services import budgets
    acc = _acc(session)
    food = _cat(session, name="Food")
    fun = _cat(session, name="Fun")
    budgets.set_budget(session, food.id, "2026-06", 100_000)
    budgets.set_budget(session, fun.id, "2026-06", 50_000)
    transactions.record_expense(session, acc.id, 40_000, "COP", date(2026, 6, 5), "f", category_id=food.id)
    transactions.record_expense(session, acc.id, 70_000, "COP", date(2026, 6, 6), "u", category_id=fun.id)  # over
    lines, summary = reports._envelope_lines(session, "2026-06")
    assert [l.category for l in lines] == ["Food", "Fun"]
    food_line = lines[0]
    assert food_line.allocated == 100_000 and food_line.spent == 40_000
    assert food_line.available == 60_000 and food_line.status == "under"
    fun_line = lines[1]
    assert fun_line.available == -20_000 and fun_line.status == "over"
    assert summary.n_green == 1 and summary.n_red == 1
    assert summary.rollover_generated == 60_000  # only Food's positive available


def test_envelope_lines_empty_when_no_budgets(session):
    lines, summary = reports._envelope_lines(session, "2026-06")
    assert lines == []
    assert summary.n_green == 0 and summary.n_red == 0 and summary.rollover_generated == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_reports.py -k envelope -q`
Expected: FAIL with `AttributeError: module 'quaestor.services.reports' has no attribute '_envelope_lines'`

- [ ] **Step 3: Write minimal implementation**

In `reports.py`, add `Budget` to the models import:

```python
from ..domain.models import Budget, Category, CategoryGroup, Transaction, TxStatus, TxType
```

Extend the report_types import:

```python
from ..domain.report_types import (
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GroupSection,
)
```

Add the budgets service import near the other service imports (add this line after the rules import):

```python
from . import budgets as _budgets
```

Append:

```python
def _envelope_lines(
    session: Session, month: str
) -> tuple[list[EnvelopeLine], EnvelopesSummary]:
    """One EnvelopeLine per budget in the month + the green/red/rollover summary."""
    budgets_ = session.exec(select(Budget).where(Budget.year_month == month)).all()
    lines: list[EnvelopeLine] = []
    for b in budgets_:
        st = _budgets.budget_status(session, b.category_id, month)
        cat = session.get(Category, b.category_id)
        name = cat.name if cat is not None else f"category {b.category_id}"
        lines.append(
            EnvelopeLine(
                category=name, allocated=st.assigned, rollover_in=st.rollover_in,
                spent=st.spent, available=st.available, status=st.status,
            )
        )
    lines.sort(key=lambda e: e.category)
    n_green = sum(1 for e in lines if e.status == "under")
    n_red = sum(1 for e in lines if e.status == "over")
    rollover_generated = sum(max(e.available, 0) for e in lines)
    return lines, EnvelopesSummary(
        n_green=n_green, n_red=n_red, rollover_generated=rollover_generated
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/reports.py backend/tests/services/test_reports.py
git commit -m "feat(p5): report envelope lines and summary from P4"
```

---

### Task 7: Reports — goals + balances + pending

**Files:**
- Modify: `backend/src/quaestor/services/reports.py`
- Test: `backend/tests/services/test_reports.py` (append)

**Interfaces:**
- Consumes: P4 `goals.goals_progress(session, today=...) -> list[GoalProgress]`; P0 `accounts.list_accounts(session)`; P3 `planned.to_pay(session, since, until) -> {"items": [...], "total_base": int}`; `Account` from models; `GoalLine`, `AccountBalance` from report_types; `money` from `domain.report_markdown`.
- Produces:
  - `_goal_lines(session, today) -> list[GoalLine]` — from active goals; defined goals carry `target`/`eta`/`on_track`, open-ended carry only `accumulated`.
  - `_balance_lines(session) -> list[AccountBalance]` — non-archived accounts, sorted by name.
  - `_pending_lines(session, start, end) -> list[str]` — planned txs in the month grouped by account, one line per account (sorted by account name), money-formatted. Empty when nothing is planned.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_reports.py`:

```python
def test_goal_lines_defined_and_open_ended(session):
    from quaestor.services import goals
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                      target_amount=1_200_000, deadline=date(2026, 12, 1))
    goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    lines = reports._goal_lines(session, today=date(2026, 6, 1))
    by_name = {l.name: l for l in lines}
    assert by_name["Trip"].target == 1_200_000 and by_name["Trip"].eta is not None
    assert by_name["Trip"].on_track is not None
    assert by_name["Buffer"].target is None and by_name["Buffer"].eta is None
    assert by_name["Buffer"].on_track is None


def test_balance_lines_exclude_archived_sorted(session):
    a = accounts.create_account(session, "Zeta", AccountType.debit, "COP", balance=500)
    accounts.create_account(session, "Alpha", AccountType.debit, "USD", balance=999)
    archived = accounts.create_account(session, "Old", AccountType.debit, "COP", balance=1)
    accounts.archive_account(session, archived.id)
    balances = reports._balance_lines(session)
    assert [b.account for b in balances] == ["Alpha", "Zeta"]
    assert balances[0].currency == "USD" and balances[0].balance == 999


def test_pending_lines_group_by_account(session):
    from quaestor.services import planned
    acc = _acc(session)
    cat = _cat(session)
    planned.plan_payment(session, payee="rent", amount=40_000, currency="COP",
                         account_id=acc.id, date=date(2026, 6, 10), category_id=cat.id)
    lines = reports._pending_lines(session, *month_bounds("2026-06"))
    assert len(lines) == 1
    assert "Acc COP" in lines[0] and "40,000.00" in lines[0]


def test_pending_lines_empty_when_nothing_planned(session):
    assert reports._pending_lines(session, *month_bounds("2026-06")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_reports.py -k "goal_lines or balance_lines or pending_lines" -q`
Expected: FAIL with `AttributeError: module 'quaestor.services.reports' has no attribute '_goal_lines'`

- [ ] **Step 3: Write minimal implementation**

In `reports.py`, add `Account` to the models import:

```python
from ..domain.models import (
    Account,
    Budget,
    Category,
    CategoryGroup,
    Transaction,
    TxStatus,
    TxType,
)
```

Extend the report_types import to include `GoalLine` and `AccountBalance`:

```python
from ..domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GoalLine,
    GroupSection,
)
```

Add the renderer's money formatter and the remaining service imports (after `from . import budgets as _budgets`):

```python
from ..domain.report_markdown import money
from . import accounts as _accounts
from . import goals as _goals
from . import planned as _planned
```

Append:

```python
def _goal_lines(session: Session, today: Date) -> list[GoalLine]:
    """GoalLine per active goal; ETA/on-track only on defined goals (P4 supplies them)."""
    lines: list[GoalLine] = []
    for p in _goals.goals_progress(session, today=today):
        lines.append(
            GoalLine(
                name=p.name, accumulated=p.saved,
                target=p.target_amount, eta=p.eta, on_track=p.on_track,
            )
        )
    return lines


def _balance_lines(session: Session) -> list[AccountBalance]:
    """Balance per non-archived account (account's own currency), sorted by name."""
    accs = _accounts.list_accounts(session)  # excludes archived
    return [
        AccountBalance(account=a.name, currency=a.currency, balance=a.balance)
        for a in sorted(accs, key=lambda a: a.name)
    ]


def _pending_lines(session: Session, start: Date, end: Date) -> list[str]:
    """Alert lines for unconfirmed (planned) entries in the month, grouped by account."""
    items = _planned.to_pay(session, start, end)["items"]
    by_account: dict[int, int] = {}
    for tx in items:
        by_account[tx.account_id] = by_account.get(tx.account_id, 0) + tx.to_base
    rows: list[tuple[str, int]] = []
    for account_id, total in by_account.items():
        acc = session.get(Account, account_id)
        name = acc.name if acc is not None else f"account {account_id}"
        rows.append((name, total))
    rows.sort(key=lambda r: r[0])
    return [f"{name}: {money(total)} pending" for name, total in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: PASS (16 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/reports.py backend/tests/services/test_reports.py
git commit -m "feat(p5): report goals, balances, pending lines"
```

---

### Task 8: `monthly_report` assembly

**Files:**
- Modify: `backend/src/quaestor/services/reports.py`
- Test: `backend/tests/services/test_reports.py` (append)

**Interfaces:**
- Consumes: every helper from Tasks 3–7; P4 `budgets.safe_to_spend(session, month)`; `render_markdown` from `domain.report_markdown`; `MonthlyReport` from report_types.
- Produces (public): `monthly_report(session: Session, month: str, *, today: Date | None = None) -> MonthlyReport`. Validates `month`; `today` defaults to `date.today()` and is forwarded to `goals_progress` for deterministic ETAs. Builds the full `MonthlyReport`, then sets `report.markdown = render_markdown(report)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_reports.py`:

```python
def test_monthly_report_end_to_end(session):
    from quaestor.services import budgets, goals
    acc = _acc(session)
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    food = _cat(session, name="Food")
    budgets.set_budget(session, food.id, "2026-06", 100_000)
    goals.create_goal(session, name="Buffer", monthly_amount=50_000, savings_account_id=sav.id)
    transactions.record_income(session, acc.id, 500_000, "COP", date(2026, 6, 1), "salary", category_id=food.id)
    transactions.record_expense(session, acc.id, 80_000, "COP", date(2026, 6, 5), "groceries", category_id=food.id)

    report = reports.monthly_report(session, "2026-06", today=date(2026, 6, 15))

    assert report.month == "2026-06"
    assert report.income == 500_000 and report.expense == 80_000 and report.net == 420_000
    assert report.envelopes_summary.n_green == 1
    assert [c.category for c in report.by_category] == ["Food"]
    assert report.drift_mom is None  # cold start
    assert report.usd_share == 0.0
    assert report.safe_to_spend.year_month == "2026-06"
    # markdown is rendered from the same data
    assert report.markdown.startswith("# Monthly report — 2026-06")
    assert "**Net:** $4,200.00 COP" in report.markdown


def test_monthly_report_rejects_malformed_month(session):
    with pytest.raises(ValidationError):
        reports.monthly_report(session, "2026-13")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_reports.py -k monthly_report -q`
Expected: FAIL with `AttributeError: module 'quaestor.services.reports' has no attribute 'monthly_report'`

- [ ] **Step 3: Write minimal implementation**

In `reports.py`, extend the report_types import to include `MonthlyReport`, and add `render_markdown` to the report_markdown import:

```python
from ..domain.report_markdown import money, render_markdown
from ..domain.report_types import (
    AccountBalance,
    CategorySection,
    DriftMoM,
    EnvelopeLine,
    EnvelopesSummary,
    GoalLine,
    GroupSection,
    MonthlyReport,
)
```

Append the public entry point:

```python
def monthly_report(
    session: Session, month: str, *, today: Date | None = None
) -> MonthlyReport:
    """Build the retrospective monthly report (data + markdown) for "YYYY-MM".

    Posted-only aggregates in COP cents; reuses P3/P4 for pending/envelopes/goals/
    safe-to-spend. `today` (defaults to date.today()) drives deterministic goal ETAs.

    Raises:
        ValidationError: malformed month.
        MissingRate: surfaced from P4 safe-to-spend if a forecast needs an absent USD rate.
    """
    _validate_month(month)
    if today is None:
        today = Date.today()
    start, end = month_bounds(month)

    expenses = _posted_for_totals(session, TxType.expense, start, end)
    incomes = _posted_for_totals(session, TxType.income, start, end)
    expense = sum(t.to_base for t in expenses)
    income = sum(t.to_base for t in incomes)
    net = income - expense

    envelopes, envelopes_summary = _envelope_lines(session, month)
    report = MonthlyReport(
        month=month,
        income=income, expense=expense, net=net,
        envelopes_summary=envelopes_summary,
        envelopes=envelopes,
        by_category=_category_sections(session, expenses, expense),
        by_group=_group_sections(session, expenses, expense),
        goals=_goal_lines(session, today),
        balances=_balance_lines(session),
        drift_mom=_drift(session, month, income, expense, net),
        usd_share=_usd_share(expenses, expense),
        pending=_pending_lines(session, start, end),
        safe_to_spend=_budgets.safe_to_spend(session, month),
        markdown="",
    )
    report.markdown = render_markdown(report)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_reports.py -q`
Expected: PASS (18 passed)

- [ ] **Step 5: Run the full domain+services suite to check for regressions**

Run: `cd backend && uv run pytest tests/domain tests/services -q`
Expected: PASS (all green, including the prior P0–P4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/services/reports.py backend/tests/services/test_reports.py
git commit -m "feat(p5): assemble monthly_report (data + markdown)"
```

---

### Task 9: Importer — header/empty validation + parse skeleton

**Files:**
- Create: `backend/src/quaestor/services/importer.py`
- Test: `backend/tests/services/test_importer.py`

**Interfaces:**
- Consumes: stdlib `csv`/`io`; `ImportResult`, `RowError` from report_types.
- Produces (public): `import_csv(session: Session, content: str, *, dry_run: bool = False) -> ImportResult`. In this task it only handles the pre-row failures: empty content, wrong/missing header, header-only (no data rows) → `ImportResult(ok=False, inserted=0, tags_created=[], errors=[RowError(line=1, ...)], dry_run=dry_run)`. The exact mandatory header is `date,type,payee,amount,currency,account,category,tags,notes`.
- Produces (module constants used by Task 10/11): `HEADER: list[str]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_importer.py`:

```python
from quaestor.services import importer

HEADER = "date,type,payee,amount,currency,account,category,tags,notes"


def test_empty_csv_is_global_error(session):
    res = importer.import_csv(session, "")
    assert res.ok is False and res.inserted == 0
    assert res.errors and res.errors[0].line == 1


def test_wrong_header_is_global_error(session):
    res = importer.import_csv(session, "date,amount\n2026-06-01,100")
    assert res.ok is False and res.inserted == 0
    assert res.errors[0].line == 1
    assert "header" in res.errors[0].reason.lower()


def test_header_only_is_global_error(session):
    res = importer.import_csv(session, HEADER + "\n")
    assert res.ok is False and res.inserted == 0
    assert res.errors[0].line == 1


def test_dry_run_flag_is_echoed_on_global_error(session):
    res = importer.import_csv(session, "", dry_run=True)
    assert res.dry_run is True and res.ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_importer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quaestor.services.importer'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/quaestor/services/importer.py`:

```python
"""Atomic bulk CSV importer (P5). Custom documented format, all-or-nothing.

Validate-first: every row is parsed/validated in memory; only when there are zero
errors does it insert (via P0 record_expense/record_income, source="import"). A
single bad row => nothing inserted. transfer rows are rejected in v1.
"""
from __future__ import annotations

import csv
import io

from sqlmodel import Session

from ..domain.report_types import ImportResult, RowError

HEADER = ["date", "type", "payee", "amount", "currency", "account", "category", "tags", "notes"]


def _global_error(reason: str, dry_run: bool) -> ImportResult:
    return ImportResult(
        ok=False, inserted=0, tags_created=[],
        errors=[RowError(line=1, reason=reason)], dry_run=dry_run,
    )


def import_csv(session: Session, content: str, *, dry_run: bool = False) -> ImportResult:
    """Import a custom-format CSV atomically. See module docstring for the contract.

    Returns an ImportResult; row problems are accumulated (never raised) so the
    caller sees every line at once.
    """
    try:
        rows = list(csv.reader(io.StringIO(content)))
    except csv.Error:
        return _global_error("malformed CSV", dry_run)
    if not rows:
        return _global_error("empty CSV", dry_run)
    header = [c.strip() for c in rows[0]]
    if header != HEADER:
        return _global_error(f"invalid header; expected: {','.join(HEADER)}", dry_run)
    data_rows = rows[1:]
    if not data_rows:
        return _global_error("no data rows", dry_run)

    # Row validation + insertion arrive in Task 10/11.
    return ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=dry_run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_importer.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/importer.py backend/tests/services/test_importer.py
git commit -m "feat(p5): importer header/empty validation skeleton"
```

---

### Task 10: Importer — row validation + dry-run

**Files:**
- Modify: `backend/src/quaestor/services/importer.py`
- Test: `backend/tests/services/test_importer.py` (append)

**Interfaces:**
- Consumes: `major_to_cents` from money; `MissingRate` from errors; `accounts.list_accounts`, `categories.list_categories`, `fx.get_current_rate`; `Date.fromisoformat`.
- Produces (internal):
  - `_ValidRow` dataclass: `tx_type: str`, `account_id: int`, `amount_cents: int`, `currency: str`, `date`, `payee: str`, `category_id: int | None`, `tags: list[str]`, `notes: str | None`.
  - `_validate_row(session, raw, line, acc_by_name, cat_by_name) -> tuple[list[RowError], _ValidRow | None]` — accumulates all problems for the row (does not stop at first). Returns `([], vrow)` only when the row is fully valid.
- Produces (behavior): `import_csv` now validates every data row. If any errors → `ImportResult(ok=False, inserted=0, tags_created=[], errors=all, dry_run)`. If no errors and `dry_run=True` → `ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=True)`.

Validation rules (per row, all accumulated):
- column count must equal 9; otherwise the only error for that row is the column-count error.
- `type` ∈ {expense, income, transfer}; `transfer` → `RowError(line, "transfer import not supported in v1")`.
- `date` parses as `YYYY-MM-DD`; else `"invalid date '<v>' (expected YYYY-MM-DD)"`.
- `amount` numeric and `> 0` (parsed via `major_to_cents`); else `"invalid amount '<v>'"` or `"amount must be > 0"`.
- `currency` ∈ {COP, USD}; else `"invalid currency '<v>' (expected COP/USD)"`.
- `account` resolves against non-archived accounts by name; missing → `"account '<v>' does not exist"`.
- when account resolved and currency valid, `currency` must equal the account's currency; else `"currency <c> does not match account '<a>' (<acc_currency>)"`.
- `category` empty → `category_id=None` (ADR-024); non-empty must resolve by name, else `"category '<v>' does not exist"`.
- when `date` valid and `currency == "USD"`, a current rate must exist (`fx.get_current_rate`); else `"no usd_cop rate for <date>"`.
- `tags` split on `;`, trimmed, empties dropped.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_importer.py`:

```python
from datetime import date

from quaestor.domain.models import AccountType
from quaestor.services import accounts, categories, fx, transactions


def _row(date_="2026-06-01", type_="expense", payee="p", amount="100",
         currency="COP", account="Bank", category="Food", tags="", notes=""):
    return ",".join([date_, type_, payee, amount, currency, account, category, tags, notes])


def _csv(*rows):
    return HEADER + "\n" + "\n".join(rows) + "\n"


def _setup_master(session):
    accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    categories.create_category(session, name="Food")


def test_valid_dry_run_inserts_nothing(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(amount="250")), dry_run=True)
    assert res.ok is True and res.inserted == 0 and res.dry_run is True
    assert res.errors == []
    assert transactions.list_transactions(session) == []


def test_invalid_date_reports_line_and_reason(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(date_="2026-13-40")), dry_run=True)
    assert res.ok is False
    assert res.errors[0].line == 2 and "date" in res.errors[0].reason


def test_invalid_type_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(type_="bogus")), dry_run=True)
    assert res.errors[0].line == 2 and "type" in res.errors[0].reason


def test_transfer_type_rejected(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(type_="transfer", category="")), dry_run=True)
    assert res.ok is False
    assert "transfer import not supported" in res.errors[0].reason


def test_non_positive_amount_rejected(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(amount="0")), dry_run=True)
    assert any("amount must be > 0" in e.reason for e in res.errors)


def test_non_numeric_amount_rejected(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(amount="abc")), dry_run=True)
    assert any("invalid amount" in e.reason for e in res.errors)


def test_unknown_account_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(account="Nope")), dry_run=True)
    assert any("account 'Nope' does not exist" in e.reason for e in res.errors)


def test_unknown_category_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(category="Nope")), dry_run=True)
    assert any("category 'Nope' does not exist" in e.reason for e in res.errors)


def test_empty_category_allowed_for_expense(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(category="")), dry_run=True)
    assert res.ok is True and res.errors == []


def test_currency_mismatch_with_account_reported(session):
    _setup_master(session)  # Bank is COP
    res = importer.import_csv(session, _csv(_row(currency="USD")), dry_run=True)
    assert any("does not match account" in e.reason for e in res.errors)


def test_usd_without_rate_reports_missing_rate(session):
    accounts.create_account(session, "Wallet", AccountType.debit, "USD", balance=0)
    categories.create_category(session, name="Food")
    res = importer.import_csv(session, _csv(_row(currency="USD", account="Wallet")), dry_run=True)
    assert any("no usd_cop rate" in e.reason for e in res.errors)


def test_usd_with_rate_validates(session):
    accounts.create_account(session, "Wallet", AccountType.debit, "USD", balance=0)
    categories.create_category(session, name="Food")
    fx.set_fx_rate(session, date(2026, 6, 1), 4000)
    res = importer.import_csv(session, _csv(_row(currency="USD", account="Wallet")), dry_run=True)
    assert res.ok is True and res.errors == []


def test_all_errors_accumulated_across_rows(session):
    _setup_master(session)
    bad_date = _row(date_="nope")
    bad_acct = _row(account="Ghost")
    res = importer.import_csv(session, _csv(bad_date, bad_acct), dry_run=True)
    lines = sorted(e.line for e in res.errors)
    assert lines == [2, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_importer.py -q`
Expected: FAIL — the new tests fail because `import_csv` does not yet validate rows (e.g. `test_invalid_date_reports_line_and_reason` expects `ok is False` but the skeleton returns `ok=True`).

- [ ] **Step 3: Write minimal implementation**

Replace the top imports of `importer.py`:

```python
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date as Date
from decimal import InvalidOperation

from sqlmodel import Session

from ..domain.errors import MissingRate
from ..domain.money import major_to_cents
from ..domain.report_types import ImportResult, RowError
from . import accounts as _accounts
from . import categories as _categories
from . import fx as _fx

HEADER = ["date", "type", "payee", "amount", "currency", "account", "category", "tags", "notes"]
_VALID_TYPES = {"expense", "income", "transfer"}
_VALID_CURRENCIES = {"COP", "USD"}
```

Add the `_ValidRow` dataclass and `_validate_row` after `_global_error`:

```python
@dataclass
class _ValidRow:
    tx_type: str  # "expense" | "income" (transfer is rejected upstream)
    account_id: int
    amount_cents: int
    currency: str
    date: Date
    payee: str
    category_id: int | None
    tags: list[str]
    notes: str | None


def _validate_row(session, raw, line, acc_by_name, cat_by_name):
    """Accumulate every problem in a row. Returns ([], _ValidRow) only when valid."""
    if len(raw) != len(HEADER):
        return [RowError(line, f"expected {len(HEADER)} columns, got {len(raw)}")], None

    date_s, type_s, payee, amount_s, currency, account_s, category_s, tags_s, notes = (
        c.strip() for c in raw
    )
    errors: list[RowError] = []

    tx_type = type_s.lower()
    if tx_type not in _VALID_TYPES:
        errors.append(RowError(line, f"invalid type {type_s!r} (expected expense/income/transfer)"))
    elif tx_type == "transfer":
        errors.append(RowError(line, "transfer import not supported in v1"))

    date = None
    try:
        date = Date.fromisoformat(date_s)
    except ValueError:
        errors.append(RowError(line, f"invalid date {date_s!r} (expected YYYY-MM-DD)"))

    amount_cents = None
    try:
        amount_cents = major_to_cents(amount_s)
        if amount_cents <= 0:
            errors.append(RowError(line, "amount must be > 0"))
            amount_cents = None
    except (InvalidOperation, ValueError):
        errors.append(RowError(line, f"invalid amount {amount_s!r}"))

    if currency not in _VALID_CURRENCIES:
        errors.append(RowError(line, f"invalid currency {currency!r} (expected COP/USD)"))

    account = acc_by_name.get(account_s)
    if account is None:
        errors.append(RowError(line, f"account {account_s!r} does not exist"))
    elif currency in _VALID_CURRENCIES and currency != account.currency:
        errors.append(
            RowError(line, f"currency {currency} does not match account {account_s!r} ({account.currency})")
        )

    category_id = None
    if category_s:
        cat = cat_by_name.get(category_s)
        if cat is None:
            errors.append(RowError(line, f"category {category_s!r} does not exist"))
        else:
            category_id = cat.id

    if date is not None and currency == "USD":
        try:
            _fx.get_current_rate(session, date)
        except MissingRate:
            errors.append(RowError(line, f"no usd_cop rate for {date_s}"))

    tags = [t.strip() for t in tags_s.split(";") if t.strip()]

    if errors:
        return errors, None
    return [], _ValidRow(
        tx_type=tx_type, account_id=account.id, amount_cents=amount_cents,
        currency=currency, date=date, payee=payee, category_id=category_id,
        tags=tags, notes=notes or None,
    )
```

Replace the placeholder tail of `import_csv` (everything after the `if not data_rows:` block) with:

```python
    acc_by_name = {a.name: a for a in _accounts.list_accounts(session)}  # excludes archived
    cat_by_name = {c.name: c for c in _categories.list_categories(session)}

    errors: list[RowError] = []
    valid: list[_ValidRow] = []
    for i, raw in enumerate(data_rows):
        line = i + 2  # header is line 1
        row_errors, vrow = _validate_row(session, raw, line, acc_by_name, cat_by_name)
        errors.extend(row_errors)
        if vrow is not None:
            valid.append(vrow)

    if errors:
        return ImportResult(ok=False, inserted=0, tags_created=[], errors=errors, dry_run=dry_run)

    if dry_run:
        return ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=True)

    # Real insertion arrives in Task 11.
    return ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_importer.py -q`
Expected: PASS (all importer tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/src/quaestor/services/importer.py backend/tests/services/test_importer.py
git commit -m "feat(p5): importer row validation and dry-run"
```

---

### Task 11: Importer — insertion + tags + atomicity

**Files:**
- Modify: `backend/src/quaestor/services/importer.py`
- Test: `backend/tests/services/test_importer.py` (append)

**Interfaces:**
- Consumes: P0 `transactions.record_expense`/`record_income`/`delete_transaction`; `tags.list_tags`/`tag_transaction`; `Source` from models (for the test assertion only).
- Produces (behavior): when there are 0 errors and `dry_run=False`, `import_csv` inserts each valid row via `record_expense`/`record_income` with `source="import"`, links tags (auto-created), and returns `ImportResult(ok=True, inserted=N, tags_created=<sorted new tag names>, errors=[], dry_run=False)`. Atomicity: a single invalid row already short-circuits before any insert (validate-first); a (very unlikely) failure mid-insert compensates by deleting the rows inserted so far and returns `ok=False, inserted=0`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_importer.py`:

```python
from quaestor.domain.models import Source


def test_successful_import_inserts_and_sets_source(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(
        _row(amount="250", payee="coffee"),
        _row(type_="income", amount="1000", payee="salary"),
    ))
    assert res.ok is True and res.inserted == 2 and res.errors == []
    txs = transactions.list_transactions(session)
    assert len(txs) == 2
    assert all(t.source == Source.import_ for t in txs)
    # amounts are major -> cents
    coffee = next(t for t in txs if t.payee == "coffee")
    assert coffee.amount == 25_000  # 250.00 -> cents


def test_tags_auto_created_and_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(
        _row(payee="a", tags="groceries;weekly"),
        _row(payee="b", tags="groceries"),
    ))
    assert res.ok is True and res.inserted == 2
    assert res.tags_created == ["groceries", "weekly"]  # sorted, de-duplicated
    from quaestor.services import tags as tags_svc
    assert {t.name for t in tags_svc.list_tags(session)} == {"groceries", "weekly"}


def test_atomic_one_bad_row_inserts_nothing(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(
        _row(payee="good", amount="100"),
        _row(payee="bad", date_="nope"),
    ))
    assert res.ok is False and res.inserted == 0
    assert transactions.list_transactions(session) == []  # DB intact


def test_dry_run_does_not_create_tags(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(tags="newtag")), dry_run=True)
    assert res.ok is True and res.inserted == 0
    from quaestor.services import tags as tags_svc
    assert tags_svc.list_tags(session) == []


def test_balance_moves_only_on_real_import(session):
    accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=1_000_000)
    categories.create_category(session, name="Food")
    importer.import_csv(session, _csv(_row(amount="100")))  # 100.00 -> 10_000 cents expense
    acc = next(a for a in accounts.list_accounts(session) if a.name == "Bank")
    assert acc.balance == 990_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_importer.py -k "successful_import or tags_auto or atomic or balance_moves" -q`
Expected: FAIL — `import_csv` still returns `inserted=0` and inserts nothing on the real path.

- [ ] **Step 3: Write minimal implementation**

Add the remaining service imports at the top of `importer.py` (after `from . import fx as _fx`):

```python
from . import tags as _tags
from . import transactions as _tx
```

Replace the final block of `import_csv` (from `if dry_run:` onward) with:

```python
    if dry_run:
        return ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=True)

    existing = {t.name for t in _tags.list_tags(session)}
    new_tags = sorted({t for v in valid for t in v.tags if t not in existing})

    inserted_ids: list[int] = []
    try:
        for v in valid:
            if v.tx_type == "income":
                tx = _tx.record_income(
                    session, v.account_id, v.amount_cents, v.currency, v.date,
                    v.payee, category_id=v.category_id, notes=v.notes, source="import",
                )
            else:  # expense
                tx = _tx.record_expense(
                    session, v.account_id, v.amount_cents, v.currency, v.date,
                    v.payee, category_id=v.category_id, notes=v.notes, source="import",
                )
            inserted_ids.append(tx.id)
            if v.tags:
                _tags.tag_transaction(session, tx.id, v.tags)
    except Exception:
        # Unlikely (rows were pre-validated): compensate to keep all-or-nothing.
        for tx_id in reversed(inserted_ids):
            try:
                _tx.delete_transaction(session, tx_id)
            except Exception:
                pass
        return ImportResult(
            ok=False, inserted=0, tags_created=[],
            errors=[RowError(line=0, reason="commit failed; rolled back")], dry_run=False,
        )

    return ImportResult(
        ok=True, inserted=len(valid), tags_created=new_tags, errors=[], dry_run=False,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/services/test_importer.py -q`
Expected: PASS (all importer tests green)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `cd backend && uv run pytest -q`
Expected: PASS (all P0–P5 tests green)

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/services/importer.py backend/tests/services/test_importer.py
git commit -m "feat(p5): importer atomic insertion with tags and source=import"
```

---

## Self-Review

**1. Spec coverage** — every P5 spec requirement maps to a task:

- `monthly_report(month) -> MonthlyReport` with `.markdown` → Task 8 (assembly) + Task 2 (renderer).
- `import_csv(content, dry_run) -> ImportResult` with row validation, atomicity, line-numbered errors → Tasks 9–11.
- Aggregation helpers (expense by category, net, USD share, MoM drift) → Tasks 3–5.
- Contract dataclasses → Task 1.
- Pure renderer (no I/O) → Task 2.
- Posted-only / transfers excluded / `to_base` no reconversion → Task 3 + Global Constraints.
- `exclude_from_totals` respected; `exclude_from_budget` via P4 → Task 3 + Task 6.
- by_category sorted, pct, includes all accounts incl. credit card (accrual, ADR-021 — no special-casing needed: all posted expenses across all accounts are summed) → Task 4.
- by_group rollup by `CategoryGroup` (ADR-023) → Task 4.
- MoM drift with/without previous month → Task 5.
- USD share `0.0` when expense 0 → Task 3.
- ADR-019 ordering: net+envelopes headline, safe-to-spend closing → Task 2 renderer + Task 8 field order.
- Safe-to-spend / envelopes / goals from P4 (P5 only formats); ETA/on-track only on defined goals → Tasks 6, 7, 8.
- Cold start (ADR-009) degrades gracefully (drift None, no rollover) → Task 5 + Task 2 empty-section test.
- Pending line from P3 `to_pay` → Task 7.
- Importer: atomic, row-by-row accumulation, name resolution, tags auto-created, `to_base` via current rate (record_* does this), `source=import`, dry-run validates without inserting, missing/different header or empty CSV → global error → Tasks 9–11.
- Importer error reasons (MissingRate per row, nonexistent name, invalid type/amount/date) → Task 10.

**2. Placeholder scan** — no "TBD"/"add error handling"/"similar to Task N". Tasks 9 and 10 explicitly return a working intermediate `import_csv` (skeleton returns `ok=True, inserted=0`) that later tasks replace; each intermediate is fully specified and its tests pass at that step.

**3. Type consistency** — checked across tasks:
- `EnvelopeLine(category, allocated, rollover_in, spent, available, status)` constructed identically in Task 1, 2 (test), 6.
- `budget_status` returns `BudgetStatus(assigned, rollover_in, spent, available, status, ...)` — Task 6 maps `assigned→allocated`, others 1:1. Verified against `domain/dtos.py`.
- `goals_progress(session, today=...)` returns `GoalProgress(name, saved, target_amount, eta, on_track, ...)` — Task 7 maps `saved→accumulated`, `target_amount→target`. Verified against `services/goals.py`.
- `to_pay(session, since, until)` returns `{"items", "total_base"}` — Task 7 reads `["items"]` and each item's `.account_id`/`.to_base`. Verified against `services/planned.py`.
- `record_expense`/`record_income` signature `(session, account_id, amount, currency, date, payee, category_id=None, notes=None, source="manual", fx_rate=None)` — Task 11 calls match positionally/by-keyword. Verified against `services/transactions.py`.
- `Source.import_ == "import"` so `source="import"` resolves correctly — verified against `domain/models.py`.
- `money(cents, currency="COP")` defined in Task 2, used in Task 7 (`_pending_lines`) and the renderer. Single definition.
- `monthly_report` / `import_csv` are session-first everywhere they are called in tests.

All consistent. Plan is ready to execute.

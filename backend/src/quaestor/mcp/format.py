"""Render service results and domain errors to agent-friendly markdown.

This module is named `format` (per the P2 spec) and shadows the builtin
`format()` for importers; do not call the builtin here.
"""
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal

from ..domain.dates import display_date
from ..domain.errors import (
    IllegalTransition,
    MissingRate,
    NotFound,
    QuaestorError,
    TransferImbalance,
    ValidationError,
)
from ..domain.models import (
    Account,
    Category,
    CategoryGroup,
    FxRate,
    RecurringItem,
    RecurringOccurrence,
    Settings,
    Tag,
    Transaction,
)
from ..domain.planned import OutstandingQueue
from ..domain.dtos import GoalProgress, SafeToSpend  # noqa: F401
from ..domain.money import cents_to_major


def money(cents: int, currency: str) -> str:
    """Render integer cents as major units + currency, e.g. '40000.00 COP'."""
    return f"{cents_to_major(cents)} {currency}"


def domain_error_text(exc: QuaestorError) -> str:
    """Translate a typed domain error into clear agent text (never a stack trace)."""
    if isinstance(exc, MissingRate):
        return (
            "I don't have the USD→COP rate for that date. "
            "Set it with `set_fx_rate` (date, usd_cop) and retry."
        )
    if isinstance(exc, TransferImbalance):
        return f"Could not record the transfer: {exc}."
    if isinstance(exc, IllegalTransition):
        return f"Can't do that: {exc}."
    if isinstance(exc, NotFound):
        return str(exc)
    if isinstance(exc, ValidationError):
        return f"Invalid input: {exc}."
    return f"Error: {exc}."


def _confirmation(verb: str, tx: Transaction, account: Account) -> str:
    lines = [
        f"✅ {verb}: **{tx.payee}** — {money(tx.amount, tx.currency)}",
        f"- Account: {account.name} "
        f"(new balance: {money(account.balance, account.currency)})",
    ]
    if tx.currency != "COP":
        lines.append(f"- Equivalent: {money(tx.to_base, 'COP')}")
    return "\n".join(lines)


def expense_confirmation(tx: Transaction, account: Account) -> str:
    return _confirmation("Expense recorded", tx, account)


def income_confirmation(tx: Transaction, account: Account) -> str:
    return _confirmation("Income recorded", tx, account)


def transfer_confirmation(
    src: Account, dst: Account, amount: int, currency: str
) -> str:
    return "\n".join(
        [
            f"✅ Transfer: {money(amount, currency)} "
            f"from **{src.name}** to **{dst.name}**",
            f"- {src.name}: {money(src.balance, src.currency)}",
            f"- {dst.name}: {money(dst.balance, dst.currency)}",
        ]
    )


def fx_set(fr: FxRate) -> str:
    # Strip trailing zeros while preserving significant digits
    rate_str = str(fr.usd_cop) if fr.usd_cop % 1 else str(fr.usd_cop.to_integral_value())
    return f"✅ USD→COP rate for {display_date(fr.date)}: {rate_str}"


def fx_current(rate, on: Date) -> str:
    if isinstance(rate, str):
        rate_str = rate
    else:
        d = Decimal(str(rate)) if not isinstance(rate, Decimal) else rate
        rate_str = str(d) if d % 1 else str(d.to_integral_value())
    return f"Current USD→COP rate on {display_date(on)}: {rate_str}"


def accounts_table(accounts: list[Account]) -> str:
    if not accounts:
        return "No accounts."
    rows = ["| Account | Type | Balance | Currency |", "|---|---|---|---|"]
    for a in accounts:
        rows.append(
            f"| {a.name} | {a.type.value} | {cents_to_major(a.balance)} | {a.currency} |"
        )
    return "\n".join(rows)


def categories_table(categories: list[Category], groups: list[CategoryGroup]) -> str:
    if not categories:
        return "No categories."
    group_name = {g.id: g.name for g in groups}
    rows = ["| Category | Group | Income |", "|---|---|---|"]
    for c in categories:
        group = group_name.get(c.group_id, "—") if c.group_id else "—"
        rows.append(f"| {c.name} | {group} | {'yes' if c.is_income else 'no'} |")
    return "\n".join(rows)


def tags_list(tags: list[Tag]) -> str:
    if not tags:
        return "No tags."
    return "Tags: " + ", ".join(t.name for t in tags)


def transactions_table(txs: list[Transaction]) -> str:
    if not txs:
        return "No transactions for those filters."
    rows = [
        "| Date | Type | Payee | Amount | Currency | COP |",
        "|---|---|---|---|---|---|",
    ]
    total = 0
    for t in txs:
        total += t.to_base
        rows.append(
            f"| {display_date(t.date)} | {t.type.value} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(t.to_base)} |"
        )
    rows.append("")
    rows.append(f"**Total (COP): {cents_to_major(total)}** · {len(txs)} transaction(s)")
    return "\n".join(rows)


def recurring_created(item: RecurringItem) -> str:
    every = (
        f"{item.interval_count} {item.interval_unit.value}"
        if item.interval_count != 1
        else item.interval_unit.value
    )
    end = f", until {display_date(item.end_date)}" if item.end_date else ""
    return (
        f"✅ Recurring **{item.name}** ({item.type.value}, {item.mode.value}) — "
        f"{money(item.amount, item.currency)} every {every}, "
        f"from {display_date(item.start_date)}{end}. id={item.id}"
    )


def recurring_list(items: list[RecurringItem]) -> str:
    if not items:
        return "No recurring items."
    rows = ["| id | Name | Type | Mode | Amount | Every | Active |", "|---|---|---|---|---|---|---|"]
    for i in items:
        every = (
            f"{i.interval_count} {i.interval_unit.value}"
            if i.interval_count != 1
            else i.interval_unit.value
        )
        rows.append(
            f"| {i.id} | {i.name} | {i.type.value} | {i.mode.value} | "
            f"{cents_to_major(i.amount)} {i.currency} | {every} | "
            f"{'yes' if i.active else 'no'} |"
        )
    return "\n".join(rows)


def payment_planned(tx: Transaction) -> str:
    return (
        f"✅ Planned payment **{tx.payee}** — {money(tx.amount, tx.currency)} "
        f"due {display_date(tx.date)}. id={tx.id} (not yet posted)"
    )


def payment_confirmed(tx: Transaction) -> str:
    return (
        f"✅ Confirmed **{tx.payee}** — {money(tx.amount, tx.currency)} "
        f"posted on {display_date(tx.date)}. id={tx.id}"
    )


def payment_skipped(tx: Transaction) -> str:
    return f"✅ Skipped **{tx.payee}** — {money(tx.amount, tx.currency)}. id={tx.id}"


def recurring_skipped(occ: RecurringOccurrence) -> str:
    return (
        f"✅ Skipped the occurrence for recurring item {occ.recurring_id} "
        f"due {display_date(occ.due_date)}."
    )


def recurring_updated(item: RecurringItem) -> str:
    return "Updated " + recurring_created(item)


def recurring_deleted(item: RecurringItem) -> str:
    return f"Deactivated recurring '{item.name}' (id {item.id}). Existing occurrences stay."


def budget_assigned(status, category_name: str) -> str:
    return (
        f"Assigned {category_name} envelope for {status.year_month}: "
        f"{status.assigned} (available {status.available})."
    )


def goal_saved(goal) -> str:
    kind = "defined" if goal.target_amount is not None else "open-ended"
    return f"Goal '{goal.name}' (id {goal.id}, {kind}, {goal.status.value}), monthly {goal.monthly_amount}."


def goal_contribution_recorded(contribution) -> str:
    return f"Recorded {contribution.amount} contribution to goal {contribution.goal_id}."


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
        sections.append(_to_pay_rows(queue.overdue))
    if queue.upcoming:
        if sections:
            sections.append("")
        sections.append("## Upcoming\n")
        sections.append(_to_pay_rows(queue.upcoming))
    return "\n".join(sections)


def _to_pay_rows(items: list[Transaction]) -> str:
    """The shared row format. Stable, machine-parseable, no extra fields."""
    rows = ["| id | Due | Payee | Amount | Currency | COP |", "|---|---|---|---|---|---|"]
    total = 0
    for t in items:
        total += t.to_base
        rows.append(
            f"| {t.id} | {display_date(t.date)} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(t.to_base)} |"
        )
    rows.append("")
    rows.append(f"**To pay (COP): {cents_to_major(total)}** · {len(items)} item(s)")
    return "\n".join(rows)


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
        f"{display_date(tx.date)}) — {money(tx.amount, tx.currency)} "
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
        deadline = display_date(g.deadline) if g.deadline is not None else "—"
        rows.append(
            f"| id={g.id} | {g.name} | {g.status.value} ({kind}) | "
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
    return f"✅ Recurring restored: '{item.name}' (id={item.id})."

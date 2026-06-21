"""Render service results and domain errors to agent-friendly markdown.

This module is named `format` (per the P2 spec) and shadows the builtin
`format()` for importers; do not call the builtin here.
"""
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal

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
    Tag,
    Transaction,
)
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
    return f"✅ USD→COP rate for {fr.date.isoformat()}: {rate_str}"


def fx_current(rate, on: Date) -> str:
    if isinstance(rate, str):
        rate_str = rate
    else:
        d = Decimal(str(rate)) if not isinstance(rate, Decimal) else rate
        rate_str = str(d) if d % 1 else str(d.to_integral_value())
    return f"Current USD→COP rate on {on.isoformat()}: {rate_str}"


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
            f"| {t.date.isoformat()} | {t.type.value} | {t.payee} | "
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
    end = f", until {item.end_date.isoformat()}" if item.end_date else ""
    return (
        f"✅ Recurring **{item.name}** ({item.type.value}, {item.mode.value}) — "
        f"{money(item.amount, item.currency)} every {every}, "
        f"from {item.start_date.isoformat()}{end}. id={item.id}"
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
        f"due {tx.date.isoformat()}. id={tx.id} (not yet posted)"
    )


def payment_confirmed(tx: Transaction) -> str:
    return (
        f"✅ Confirmed **{tx.payee}** — {money(tx.amount, tx.currency)} "
        f"posted on {tx.date.isoformat()}. id={tx.id}"
    )


def payment_skipped(tx: Transaction) -> str:
    return f"✅ Skipped **{tx.payee}** — {money(tx.amount, tx.currency)}. id={tx.id}"


def recurring_skipped(occ: RecurringOccurrence) -> str:
    return (
        f"✅ Skipped the occurrence for recurring item {occ.recurring_id} "
        f"due {occ.due_date.isoformat()}."
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


def to_pay_table(result: dict) -> str:
    items = result["items"]
    if not items:
        return "Nothing to pay in that window. 🎉"
    rows = ["| id | Due | Payee | Amount | Currency | COP |", "|---|---|---|---|---|---|"]
    for t in items:
        rows.append(
            f"| {t.id} | {t.date.isoformat()} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(t.to_base)} |"
        )
    rows.append("")
    rows.append(
        f"**To pay (COP): {cents_to_major(result['total_base'])}** · {len(items)} item(s)"
    )
    return "\n".join(rows)

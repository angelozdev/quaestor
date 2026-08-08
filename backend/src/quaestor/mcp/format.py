"""Render service results and domain errors to agent-friendly markdown.

This module is named `format` (per the P2 spec) and shadows the builtin
`format()` for importers; do not call the builtin here.
"""

from __future__ import annotations

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
    RecurringItem,
    RecurringOccurrence,
    Tag,
    Transaction,
)
from ..domain.money import cents_to_major, to_cop_cents
from ..domain.planned import OutstandingQueue


def money(cents: int, currency: str) -> str:
    """Render integer cents as major units + currency, e.g. '40000.00 COP'."""
    return f"{cents_to_major(cents)} {currency}"


def domain_error_text(exc: QuaestorError) -> str:
    """Translate a typed domain error into clear agent text (never a stack trace)."""
    if isinstance(exc, MissingRate):
        return "No TRM is set. Set the USD→COP rate with `set_fx_rate` (usd_cop) and retry."
    if isinstance(exc, TransferImbalance):
        return f"Could not record the transfer: {exc}."
    if isinstance(exc, IllegalTransition):
        return f"Can't do that: {exc}."
    if isinstance(exc, NotFound):
        return str(exc)
    if isinstance(exc, ValidationError):
        return f"Invalid input: {exc}."
    return f"Error: {exc}."


def _confirmation(verb: str, tx: Transaction, account: Account, cop_equivalent: int | None) -> str:
    lines = [
        f"✅ {verb}: **{tx.payee}** — {money(tx.amount, tx.currency)}",
        (f"- Account: {account.name} (new balance: {money(account.balance, account.currency)})"),
    ]
    if cop_equivalent is not None and tx.currency != "COP":
        lines.append(f"- Equivalent: {money(cop_equivalent, 'COP')}")
    return "\n".join(lines)


def expense_confirmation(tx: Transaction, account: Account, cop_equivalent: int | None = None) -> str:
    return _confirmation("Expense recorded", tx, account, cop_equivalent)


def income_confirmation(tx: Transaction, account: Account, cop_equivalent: int | None = None) -> str:
    return _confirmation("Income recorded", tx, account, cop_equivalent)


def transfer_confirmation(src: Account, dst: Account, amount_sent: int, amount_received: int) -> str:
    sent = money(amount_sent, src.currency)
    header = f"✅ Transfer: {sent} from **{src.name}** to **{dst.name}**"
    if src.currency != dst.currency:
        header += f" ({money(amount_received, dst.currency)} received)"
    return "\n".join(
        [
            header,
            f"- {src.name}: {money(src.balance, src.currency)}",
            f"- {dst.name}: {money(dst.balance, dst.currency)}",
        ]
    )


def _rate_str(rate: Decimal) -> str:
    return str(rate) if rate % 1 else str(rate.to_integral_value())


def fx_set(rate: Decimal) -> str:
    return f"✅ USD→COP rate (TRM) set: {_rate_str(rate)}"


def fx_current(rate: Decimal) -> str:
    return f"Current USD→COP rate (TRM): {_rate_str(rate)}"


def accounts_table(accounts: list[Account]) -> str:
    if not accounts:
        return "No accounts."
    rows = ["| Account | Type | Balance | Currency |", "|---|---|---|---|"]
    for a in accounts:
        rows.append(f"| {a.name} | {a.type.value} | {cents_to_major(a.balance)} | {a.currency} |")
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


def transactions_table(txs: list[Transaction], trm: Decimal) -> str:
    if not txs:
        return "No transactions for those filters."
    rows = [
        "| Date | Type | Payee | Amount | Currency | COP |",
        "|---|---|---|---|---|---|",
    ]
    total = 0
    for t in txs:
        cop = to_cop_cents(t.amount, t.currency, trm)
        total += cop
        rows.append(
            f"| {display_date(t.date)} | {t.type.value} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(cop)} |"
        )
    rows.append("")
    rows.append(f"**Total (COP): {cents_to_major(total)}** · {len(txs)} transaction(s)")
    return "\n".join(rows)


def recurring_created(item: RecurringItem) -> str:
    every = (
        f"{item.interval_count} {item.interval_unit.value}" if item.interval_count != 1 else item.interval_unit.value
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
        every = f"{i.interval_count} {i.interval_unit.value}" if i.interval_count != 1 else i.interval_unit.value
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
        f"✅ Confirmed **{tx.payee}** — {money(tx.amount, tx.currency)} posted on {display_date(tx.date)}. id={tx.id}"
    )


def payment_skipped(tx: Transaction) -> str:
    return f"✅ Skipped **{tx.payee}** — {money(tx.amount, tx.currency)}. id={tx.id}"


def payment_restored(tx: Transaction) -> str:
    return (
        f"✅ Restored **{tx.payee}** — {money(tx.amount, tx.currency)} "
        f"due {display_date(tx.date)}. id={tx.id} (back in the queue)"
    )


def recurring_skipped(occ: RecurringOccurrence) -> str:
    return f"✅ Skipped the occurrence for recurring item {occ.recurring_id} due {display_date(occ.due_date)}."


def recurring_pending_dates(name: str, dates: list) -> str:
    if not dates:
        return f"No passed due dates are waiting for a decision on {name}."
    listed = "\n".join(f"- {display_date(d)}" for d in dates)
    return f"{name} has {len(dates)} passed due date(s) waiting for your decision:\n{listed}"


def recurring_dates_accepted(name: str, occs: list) -> str:
    if not occs:
        return f"Nothing to accept on {name}."
    listed = ", ".join(display_date(o.due_date) for o in occs)
    return f"✅ Recorded {len(occs)} passed date(s) for {name}: {listed}."


def recurring_dates_declined(name: str, occs: list) -> str:
    if not occs:
        return f"Nothing to decline on {name}."
    listed = ", ".join(display_date(o.due_date) for o in occs)
    return f"✅ Declined {len(occs)} passed date(s) for {name}: {listed}. They will not be charged or offered again."


def recurring_updated(item: RecurringItem) -> str:
    return "Updated " + recurring_created(item)


def recurring_deleted(item: RecurringItem) -> str:
    return f"Deactivated recurring '{item.name}' (id {item.id}). Existing occurrences stay."


def to_pay_table(queue: OutstandingQueue, trm: Decimal) -> str:
    """Render the outstanding queue as markdown.

    Layout: overdue section first (with ⚠️ marker), then upcoming. Empty
    bucket → omitted entirely (silence is the right state). Both empty
    → "Nothing outstanding."

    With both sections present, a closing line carries the combined total —
    the same figure the app's headline shows. A single-section answer already
    ends in its own subtotal, so it closes there unchanged.
    """
    if queue.is_empty:
        return "Nothing outstanding."

    sections: list[str] = []
    if queue.overdue:
        sections.append("## ⚠️ Overdue\n")
        sections.append(_to_pay_rows(queue.overdue, trm))
    if queue.upcoming:
        if sections:
            sections.append("")
        sections.append("## Upcoming\n")
        sections.append(_to_pay_rows(queue.upcoming, trm))
    if queue.overdue and queue.upcoming:
        sections.append("")
        sections.append(
            f"**Total to pay (COP): {cents_to_major(queue.total_cop_cents(trm))}** "
            f"· {len(queue.overdue) + len(queue.upcoming)} item(s)"
        )
    return "\n".join(sections)


def _to_pay_rows(items: list[Transaction], trm: Decimal) -> str:
    """The shared row format. Stable, machine-parseable, no extra fields."""
    rows = ["| id | Due | Payee | Amount | Currency | COP |", "|---|---|---|---|---|---|"]
    total = 0
    for t in items:
        cop = to_cop_cents(t.amount, t.currency, trm)
        total += cop
        rows.append(
            f"| {t.id} | {display_date(t.date)} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(cop)} |"
        )
    rows.append("")
    rows.append(f"**To pay (COP): {cents_to_major(total)}** · {len(items)} item(s)")
    return "\n".join(rows)


def account_card(account: Account) -> str:
    return (
        f"Account **{account.name}** (id={account.id}, "
        f"{account.type.value}, {account.currency}) — "
        f"balance {money(account.balance, account.currency)}"
    )


def category_card(category: Category, group: CategoryGroup | None) -> str:
    group_name = group.name if group is not None else "(no group)"
    kind = "income" if category.is_income else "expense"
    return f"Category **{category.name}** (id={category.id}, {kind}, group: {group_name})"


def category_group_card(group: CategoryGroup) -> str:
    return f"Category group **{group.name}** (id={group.id}, order={group.sort_order})"


def tag_card(tag: Tag) -> str:
    return f"Tag '{tag.name}' (id {tag.id})."


def transaction_card(tx: Transaction, trm: Decimal) -> str:
    cop = to_cop_cents(tx.amount, tx.currency, trm)
    return (
        f"Transaction **{tx.payee}** (id={tx.id}, {tx.type.value}, {tx.status.value}, "
        f"{display_date(tx.date)}) — {money(tx.amount, tx.currency)} "
        f"({money(cop, 'COP')})"
    )


def settings_card(settings) -> str:
    src = f"{settings.default_source_account_id}" if settings.default_source_account_id is not None else "(none)"
    return f"Settings — Base currency: {settings.base_currency}; default source account: {src}"


def monthly_report_card(report) -> str:
    return "\n".join(
        [
            f"# Monthly report — {report.month}",
            f"- Income: {money(report.income, 'COP')}",
            f"- Expense: {money(report.expense, 'COP')}",
            f"- Net: {money(report.net, 'COP')}",
            "",
            report.markdown,
        ]
    )


def recurring_restored(item: RecurringItem) -> str:
    return f"✅ Recurring restored: '{item.name}' (id={item.id})."


def fund_saved(fund, category_name: str) -> str:
    """The rule as stored — no month is walked, so no rate is needed to confirm a write."""
    detail = {
        "fixed": lambda: f"{money(fund.amount or 0, 'COP')} each month",
        "average": lambda: f"the average of the last {fund.window_months} months",
        "from-recurring": lambda: "what its obligations come to",
        "target-by-date": lambda: f"{money(fund.target_amount or 0, 'COP')} by {fund.target_month}",
    }[fund.rule.value]()
    carries = "accumulating" if fund.accumulates else "resetting"
    return f"✅ Fund on **{category_name}** — asks {detail}, from {fund.start_month}, {carries}. id={fund.id}"


def fund_deleted(name: str) -> str:
    return f"✅ Fund on '{name}' deleted."


def funds_list(lines: list) -> str:
    if not lines:
        return "No funds."
    rows = ["| id | Category | Rule | Since | Accumulates |", "|---|---|---|---|---|"]
    for line in lines:
        rows.append(
            f"| {line.fund_id} | {line.name} | {line.rule} | {line.start_month} | "
            f"{'yes' if line.accumulates else 'no'} |"
        )
    return "\n".join(rows)


def fund_card(status) -> str:
    parts = [
        f"Fund on **{status.name}** ({status.rule}) — {status.year_month}",
        f"- Asks: {money(status.asks, 'COP')}",
        f"- Holds: {money(status.holds, 'COP')}",
        f"- Spent this month: {money(status.spent, 'COP')}",
        f"- Carries into next month: {money(status.carries, 'COP')}",
        f"- Next month has: {money(status.next_month_has, 'COP')}",
        f"- {'On track' if status.on_track else 'Behind'}",
    ]
    if status.whole_by is not None:
        parts.append(f"- Whole by: {status.whole_by}")
    return "\n".join(parts)


def fund_preview_card(preview, category_name: str) -> str:
    lines = [f"A fund on **{category_name}** would ask {money(preview.would_ask, 'COP')} its first month."]
    if preview.warning:
        lines.append(f"⚠️ {preview.warning}")
    return "\n".join(lines)


def money_available_card(view) -> str:
    """The month's number opened into the terms that make it (AC-10)."""
    lines = [
        f"# Money available — {view.year_month}",
        f"- Income: {money(view.income, 'COP')}",
    ]
    for fund in view.funds:
        lines.append(f"- Fund {fund.name}: −{money(fund.asks, 'COP')}")
    lines.append(f"- Uncovered: −{money(view.uncovered, 'COP')}")
    lines.append(f"- **Available: {money(view.free, 'COP')}**")
    return "\n".join(lines)


def money_rates_card(rates) -> str:
    """What the owner earns and costs a month — never the money available (AC-14b)."""
    return "\n".join(
        [
            f"# Monthly rates — {rates.year_month}",
            f"- Earning: {money(rates.earning, 'COP')} a month",
            f"- Cost: {money(rates.cost, 'COP')} a month",
            f"- Margin: {money(rates.margin, 'COP')} a month",
        ]
    )

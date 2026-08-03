"""Balance sign rules, envelope math and goal progress.

The recurrence date engine lives in `recurrence.py`; the calendar helpers it
owns are imported from there.
"""

from __future__ import annotations

from datetime import date

from .dtos import BudgetStatus, GoalProgress
from .models import TransferDirection, TxType
from .recurrence import add_months, last_day_of_month


def delta_balance(tx_type: TxType, amount: int) -> int:
    """Centavos to add to the account balance (amount always positive)."""
    if tx_type == TxType.income:
        return amount
    if tx_type == TxType.expense:
        return -amount
    raise ValueError("delta_balance only applies to expense/income; transfer uses transfer_deltas")


def category_is_income_for(tx_type: TxType) -> bool:
    """Whether this movement must carry an income category (ADR-0042).

    Raises:
        ValueError: transfer carries no category at all, so it has no
            direction; `services.categories.resolve_for_movement` refuses it
            before reaching here.
    """
    if tx_type == TxType.income:
        return True
    if tx_type == TxType.expense:
        return False
    raise ValueError("a transfer carries no category, so it has no direction")


def transfer_deltas(amount: int) -> tuple[int, int]:
    """(delta_from, delta_to) for an internal transfer."""
    return (-amount, amount)


def leg_delta_balance(direction: TransferDirection | None, amount: int) -> int:
    """Centavos this transfer leg added to its account (amount always positive).

    Raises:
        ValueError: the leg carries no stored direction (ADR-0032).
    """
    if direction == TransferDirection.out:
        return -amount
    if direction == TransferDirection.in_:
        return amount
    raise ValueError("leg_delta_balance requires a stored transfer direction")


def month_bounds(year_month: str) -> tuple[date, date]:
    """First and last calendar day of a "YYYY-MM" string."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    return date(year, month, 1), date(year, month, last_day_of_month(year, month))


def prev_year_month(year_month: str) -> str:
    """The "YYYY-MM" of the previous calendar month."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def envelope_status_calc(
    category_id: int, year_month: str, assigned: int, rollover_in: int, spent: int
) -> BudgetStatus:
    """Envelope math: available, pct_used, over/under (ADR-003/005). Pure."""
    denom = rollover_in + assigned
    available = denom - spent
    pct_used = round(spent / denom * 100) if denom > 0 else 0
    status = "over" if spent > denom else "under"
    return BudgetStatus(
        category_id=category_id,
        year_month=year_month,
        assigned=assigned,
        rollover_in=rollover_in,
        spent=spent,
        available=available,
        pct_used=pct_used,
        status=status,
    )


def safe_to_spend_calc(
    income_forecast: int,
    committed: int,
    assigned_envelopes: int,
    unbudgeted_spending: int,
    overspend: int,
) -> int:
    """Safe-to-spend headline cascade (ADR-003/005/014/016). Pure.

    free = income_forecast - committed - assigned_envelopes
           - unbudgeted_spending - overspend
    """
    return income_forecast - committed - assigned_envelopes - unbudgeted_spending - overspend


def goal_progress_calc(
    goal_id: int,
    name: str,
    monthly_amount: int,
    saved: int,
    target_amount: int | None,
    deadline: date | None,
    today: date,
) -> GoalProgress:
    """Goal status math (fixed monthly amount). Pure.

    Defined iff both target_amount and deadline are set; open-ended iff neither
    (the only-one case is rejected upstream in create_goal).
    """
    if target_amount is None or deadline is None:
        return GoalProgress(
            goal_id=goal_id,
            name=name,
            type="open-ended",
            monthly_amount=monthly_amount,
            saved=saved,
        )
    remaining = max(target_amount - saved, 0)
    months_left = (deadline.year * 12 + deadline.month) - (today.year * 12 + today.month)
    if months_left < 1:
        months_left = 1
    monthly_required = -(-remaining // months_left)  # ceil division
    on_track = monthly_amount >= monthly_required
    eta = today if remaining == 0 else add_months(today, -(-remaining // monthly_amount))
    return GoalProgress(
        goal_id=goal_id,
        name=name,
        type="defined",
        monthly_amount=monthly_amount,
        saved=saved,
        target_amount=target_amount,
        deadline=deadline,
        monthly_required=monthly_required,
        on_track=on_track,
        eta=eta,
        remaining=remaining,
    )

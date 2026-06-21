"""Savings goals: create, standalone contribution, progress, and the P3 hook seam (ADR-006/007)."""
from __future__ import annotations

import uuid
from datetime import date as Date

from sqlmodel import Session, select

from ..domain.dtos import GoalProgress
from ..domain.errors import NotFound, ValidationError
from ..domain.models import (
    Account,
    AccountType,
    ContributionSource,
    Goal,
    GoalContribution,
    GoalStatus,
    Settings,
    Source,
    Transaction,
    TxStatus,
    TxType,
)
from ..domain.money import to_base_cents
from ..domain.rules import goal_progress_calc, month_bounds, transfer_deltas
from . import transactions as _tx

_UNSET = object()


def create_goal(
    session: Session,
    name: str,
    monthly_amount: int,
    savings_account_id: int,
    target_amount: int | None = None,
    deadline: Date | None = None,
) -> Goal:
    """Create a savings goal (defined if target+deadline; open-ended if neither).

    Raises:
        ValidationError: monthly_amount <= 0; only one of target/deadline given;
            target_amount <= 0; savings account missing, not savings, or archived.
    """
    if monthly_amount <= 0:
        raise ValidationError("monthly_amount must be > 0")
    has_target = target_amount is not None
    has_deadline = deadline is not None
    if has_target != has_deadline:
        raise ValidationError(
            "a defined goal needs both target_amount and deadline; "
            "an open-ended goal needs neither"
        )
    if has_target and target_amount <= 0:
        raise ValidationError("target_amount must be > 0")
    acc = session.get(Account, savings_account_id)
    if acc is None:
        raise ValidationError(f"savings account {savings_account_id} does not exist")
    if acc.type != AccountType.savings:
        raise ValidationError(f"account {savings_account_id} is not a savings account")
    if acc.archived:
        raise ValidationError(f"savings account {savings_account_id} is archived")
    goal = Goal(
        name=name, monthly_amount=monthly_amount, savings_account_id=savings_account_id,
        target_amount=target_amount, deadline=deadline, status=GoalStatus.active,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


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


def _saved(session: Session, goal_id: int) -> int:
    rows = session.exec(
        select(GoalContribution.amount).where(GoalContribution.goal_id == goal_id)
    ).all()
    return sum(rows)


def _maybe_mark_reached(session: Session, goal: Goal) -> None:
    """Flip a defined goal to reached once its contributions meet target. No-op otherwise.

    Relies on autoflush: any contribution added earlier in this transaction is
    visible to the _saved query.
    """
    if goal.target_amount is None:
        return
    if _saved(session, goal.id) >= goal.target_amount:
        goal.status = GoalStatus.reached
        session.add(goal)


def goal_contribution(
    session: Session, goal_id: int, amount: int, date: Date
) -> GoalContribution:
    """Standalone manual contribution: internal transfer + GoalContribution, atomic.

    Raises:
        ValidationError: amount <= 0; no default source account; same source/dest;
            missing/archived source or savings account; currency mismatch.
        NotFound: the goal does not exist.
    """
    if amount <= 0:
        raise ValidationError("amount must be > 0")
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise NotFound(f"goal {goal_id} not found")
    dst = session.get(Account, goal.savings_account_id)
    if dst is None or dst.archived:
        raise ValidationError("goal savings account is missing or archived")
    settings = session.get(Settings, 1)
    src_id = settings.default_source_account_id if settings else None
    if src_id is None:
        raise ValidationError("no default source account configured for transfers")
    if src_id == dst.id:
        raise ValidationError("source and destination cannot be the same account")
    src = session.get(Account, src_id)
    if src is None or src.archived:
        raise ValidationError(f"source account {src_id} is missing or archived")
    if src.currency != dst.currency:
        raise ValidationError("transfer currency must match both accounts")
    rate = _tx._resolve_fx(session, dst.currency, date, None)
    base = to_base_cents(amount, rate)
    group = uuid.uuid4().hex
    d_from, d_to = transfer_deltas(amount)
    try:
        leg_from = Transaction(
            date=date, payee=f"Goal: {goal.name}", type=TxType.transfer,
            status=TxStatus.posted, amount=amount, currency=dst.currency, fx_rate=rate,
            to_base=base, account_id=src.id, transfer_group_id=group, source=Source.manual,
        )
        leg_to = Transaction(
            date=date, payee=f"Goal: {goal.name}", type=TxType.transfer,
            status=TxStatus.posted, amount=amount, currency=dst.currency, fx_rate=rate,
            to_base=base, account_id=dst.id, transfer_group_id=group, source=Source.manual,
        )
        src.balance += d_from
        dst.balance += d_to
        session.add_all([leg_from, leg_to, src, dst])
        session.flush()  # assign leg_to.id for the contribution link
        contribution = GoalContribution(
            goal_id=goal.id, date=date, amount=base,
            source=ContributionSource.manual, transaction_id=leg_to.id,
        )
        session.add(contribution)
        _maybe_mark_reached(session, goal)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(contribution)
    return contribution


def goals_progress(
    session: Session,
    goal_ids: list[int] | None = None,
    today: Date | None = None,
) -> list[GoalProgress]:
    """Progress of each goal (all active ones if goal_ids=None).

    today defaults to date.today(); pass it explicitly for deterministic tests.
    """
    if today is None:
        today = Date.today()
    stmt = select(Goal)
    if goal_ids is not None:
        stmt = stmt.where(Goal.id.in_(goal_ids))
    else:
        stmt = stmt.where(Goal.status == GoalStatus.active)
    goals_ = session.exec(stmt.order_by(Goal.id)).all()
    return [
        goal_progress_calc(
            goal.id, goal.name, goal.monthly_amount, _saved(session, goal.id),
            goal.target_amount, goal.deadline, today,
        )
        for goal in goals_
    ]


def propose_goal_contributions(period: str, session: Session) -> list[Transaction]:
    """Rollover hook: create one `planned` transfer per active goal (no money moved).

    Idempotent per (goal_id, period): skips a goal that already has any transaction
    carrying its goal_id dated within the period (planned, posted, or skipped), so
    daily re-runs of close_month never duplicate a proposal.

    Does NOT commit — close_month owns the transaction. Writes directly to session.

    Raises:
        ValidationError: a goal's savings account is missing or archived.
    """
    start, end = month_bounds(period)
    created: list[Transaction] = []
    goals_ = session.exec(select(Goal).where(Goal.status == GoalStatus.active)).all()
    for goal in goals_:
        existing = session.exec(
            select(Transaction).where(
                Transaction.goal_id == goal.id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).first()
        if existing is not None:
            continue
        dst = session.get(Account, goal.savings_account_id)
        if dst is None:
            raise ValidationError(f"goal {goal.id} savings account is missing")
        if dst.archived:
            raise ValidationError(f"goal {goal.id} savings account is archived")
        rate = _tx._resolve_fx(session, dst.currency, end, None)
        tx = Transaction(
            date=end, payee=f"Goal: {goal.name}", type=TxType.transfer,
            status=TxStatus.planned, amount=goal.monthly_amount, currency=dst.currency,
            fx_rate=rate, to_base=to_base_cents(goal.monthly_amount, rate),
            account_id=goal.savings_account_id, goal_id=goal.id, source=Source.manual,
        )
        session.add(tx)
        created.append(tx)
    return created


def record_confirmed_contribution(tx: Transaction, session: Session) -> GoalContribution | None:
    """Post-confirm hook: record a confirmed GoalContribution for a goal transfer.

    No-op (returns None) when tx carries no goal_id. Does NOT commit — runs inside
    confirm_payment's transaction, which has already materialized the real transfer.
    """
    if tx.goal_id is None:
        return None
    goal = session.get(Goal, tx.goal_id)
    if goal is None:
        return None
    contribution = GoalContribution(
        goal_id=goal.id, date=tx.date, amount=tx.to_base,
        source=ContributionSource.confirmed, transaction_id=tx.id,
    )
    session.add(contribution)
    _maybe_mark_reached(session, goal)
    return contribution


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

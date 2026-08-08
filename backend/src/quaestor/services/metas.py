"""Metas — a named thing to save for, belonging to no category (ADR-0046).

Nothing here stores what a meta holds. Every figure is folded forward from the
meta's start month to the month being asked about, so a past month answers as
that month stood and cancelling in December cannot rewrite what September
reported.

**The month always charges its instalment.** `meta_ask_calc` reads what the
meta opened the month with and nothing else; contributing, completing,
cancelling and editing are separate terms in the month, never adjustments to
the instalment. An instalment of zero happens only because nothing is missing.

This module does not import `services.funds`. Both read the same
`MonthAggregate` and hand their asks to `month_available`, which is the one
place the two nouns meet.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from ..domain.dtos import MetaStatus
from ..domain.errors import NotFound, ValidationError
from ..domain.models import Meta
from ..domain.money import to_cop_cents
from ..domain.rules import (
    is_year_month,
    meta_ask_calc,
    meta_uncovered_calc,
    months_to_meta,
    next_year_month,
    year_month_of,
)
from .month_aggregate import MonthAggregate


@dataclass(frozen=True)
class MetaPreview:
    """What a meta would ask before it exists (AC-45).

    The surprise arrives at creation, never later on the headline.
    """

    asks: int
    months_left: int
    over_the_month: bool


def _validate_year_month(year_month: str, what: str = "year_month") -> str:
    if not is_year_month(year_month):
        raise ValidationError(f"malformed {what} (expected YYYY-MM): {year_month!r}")
    return year_month


def _require_meta(session: Session, meta_id: int) -> Meta:
    meta = session.get(Meta, meta_id)
    if meta is None:
        raise NotFound(f"meta {meta_id} not found")
    return meta


def _refuse_name_already_held(session: Session, name: str, *, excluding: int | None = None) -> None:
    """Two live metas may not carry one name, the way two categories may not.

    An archived meta's name is free, and restoring over a name a live meta has
    taken is refused where the restore happens (AC-22).
    """
    held = session.exec(select(Meta).where(Meta.name == name, Meta.archived == False)).first()  # noqa: E712
    if held is not None and held.id != excluding:
        raise ValidationError(f"another meta already holds the name {name!r}")


def _validate_spec(name: str, amount: int, target_month: str, today_month: str) -> None:
    if not name or not name.strip():
        raise ValidationError("a meta needs a name")
    if amount <= 0:
        raise ValidationError("a meta needs an amount above zero")
    _validate_year_month(target_month, "target_month")
    if target_month < today_month:
        raise ValidationError(f"there is no way to save into the past: {target_month} is behind {today_month}")


def _contributions_in(agg: MonthAggregate, meta: Meta, month: str) -> int:
    return agg.contributions.get(meta.id, {}).get(month, 0)


def _bought(agg: MonthAggregate, meta: Meta) -> bool:
    """Whether a purchase has been pointed at this meta, in any month up to now."""
    return bool(agg.linked_to(meta.id))


@dataclass(frozen=True)
class _Month:
    opening: int
    ask: int
    contributed: int
    holds: int


def _walk(agg: MonthAggregate, meta: Meta) -> _Month:
    """Fold the meta forward to the month this aggregate holds (ADR-0046)."""
    year_month = agg.year_month
    month = meta.start_month
    opening = meta.stated_opening or 0
    if year_month < month:
        return _Month(opening=0, ask=0, contributed=0, holds=0)
    while True:
        ask = meta_ask_calc(meta.amount, opening, months_to_meta(month, meta.target_month))
        contributed = _contributions_in(agg, meta, month)
        holds = opening + ask + contributed
        if holds > meta.amount:
            contributed = max(meta.amount - opening - ask, 0)
            holds = opening + ask + contributed
        if month == year_month:
            return _Month(opening=opening, ask=ask, contributed=contributed, holds=holds)
        opening = holds
        month = next_year_month(month)


def _status(agg: MonthAggregate, meta: Meta) -> MetaStatus:
    walked = _walk(agg, meta)
    bought = _bought(agg, meta)
    complete = bought or walked.holds >= meta.amount
    progress = min(round(walked.holds * 100 / meta.amount), 100) if meta.amount else 0
    return MetaStatus(
        meta_id=meta.id,
        name=meta.name,
        year_month=agg.year_month,
        amount=meta.amount,
        currency=meta.currency,
        target_month=meta.target_month,
        asks=walked.ask,
        holds=walked.holds,
        contributed=walked.contributed,
        progress=progress,
        complete=complete,
        closed=meta.closed,
        waiting=meta.target_month < agg.year_month and not bought and not meta.closed,
    )


def statuses(agg: MonthAggregate) -> list[MetaStatus]:
    """Every live meta, as the month reports it. No DB access."""
    return [_status(agg, meta) for meta in agg.metas]


def asks_total(agg: MonthAggregate) -> int:
    """What every meta asks this month, in COP cents.

    A meta held in another currency converts at the app's single rate, the same
    way every other foreign figure does (ADR-0031).
    """
    return sum(_ask_in_cop(agg, meta) for meta in agg.metas)


def _ask_in_cop(agg: MonthAggregate, meta: Meta) -> int:
    return to_cop_cents(_walk(agg, meta).ask, meta.currency, agg.trm)


def uncovered_total(agg: MonthAggregate) -> int:
    """What every linked purchase cost past what its meta had, in COP cents.

    The seam where double counting would enter. A linked movement is out of its
    category's spending entirely (`spent_in` drops it), so the only thing it
    can cost the month is its own excess — what it cost, less what the meta
    opened the month with, less what the meta asks now (AC-12).
    """
    return sum(_meta_uncovered(agg, meta) for meta in agg.metas)


def _meta_uncovered(agg: MonthAggregate, meta: Meta) -> int:
    spent = sum(
        agg.to_cop_cents(tx)
        for tx in agg.linked_to(meta.id, posted_only=False)
        if year_month_of(tx.date) == agg.year_month
    )
    if not spent:
        return 0
    walked = _walk(agg, meta)
    return to_cop_cents(
        meta_uncovered_calc(_to_meta_currency(agg, meta, spent), walked.opening, walked.ask),
        meta.currency,
        agg.trm,
    )


def _to_meta_currency(agg: MonthAggregate, meta: Meta, cop_cents: int) -> int:
    """A purchase reaches its meta in the meta's own currency (AC-26)."""
    if meta.currency == "COP":
        return cop_cents
    return round(cop_cents / float(agg.trm))


def contributed_total(agg: MonthAggregate) -> int:
    """What the owner set aside by hand this month, in COP cents."""
    return sum(to_cop_cents(_contributions_in(agg, meta, agg.year_month), meta.currency, agg.trm) for meta in agg.metas)


def create_meta(
    session: Session,
    *,
    name: str,
    amount: int,
    target_month: str,
    today: str,
    currency: str = "COP",
    stated_opening: int | None = None,
) -> Meta:
    """Open a meta for a named thing.

    `stated_opening` is what the owner already had. It costs no month — unlike
    a contribution, which is money set aside now (AC-34).

    Raises:
        ValidationError: no name, an amount at or below zero, a malformed
            target month, a target month already behind, or a name a live meta
            already holds.
    """
    _validate_spec(name, amount, target_month, today)
    _refuse_name_already_held(session, name)
    meta = Meta(
        name=name.strip(),
        amount=amount,
        currency=currency,
        start_month=today,
        target_month=target_month,
        stated_opening=stated_opening,
    )
    session.add(meta)
    session.commit()
    session.refresh(meta)
    return meta


def set_meta(session: Session, meta_id: int, *, today: str, **changes) -> Meta:
    """Change a meta's name, amount or target month while it runs (AC-11).

    What it asks recomputes at once, from what it holds now over the months
    from this one through the target — the month being edited is one of them.

    Raises:
        NotFound: no such meta.
        ValidationError: every refusal `create_meta` raises.
    """
    meta = _require_meta(session, meta_id)
    name = changes.get("name", meta.name)
    amount = changes.get("amount", meta.amount)
    target_month = changes.get("target_month", meta.target_month)
    _validate_spec(name, amount, target_month, today)
    _refuse_name_already_held(session, name, excluding=meta.id)
    meta.name = name.strip()
    meta.amount = amount
    meta.target_month = target_month
    session.add(meta)
    session.commit()
    session.refresh(meta)
    return meta


def preview_meta(*, amount: int, target_month: str, today: str, income: int) -> MetaPreview:
    """What a meta would ask in its first month, before it exists (AC-45).

    Raises:
        ValidationError: every refusal `create_meta` raises about the amount
            and the month.
    """
    _validate_spec("preview", amount, target_month, today)
    months_left = months_to_meta(today, target_month)
    asks = meta_ask_calc(amount, 0, months_left)
    return MetaPreview(asks=asks, months_left=months_left, over_the_month=income > 0 and asks > income)

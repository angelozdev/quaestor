"""Metas — a named thing to save for, belonging to no category (ADR-0046).

Nothing here stores what a meta holds. Every figure is folded forward from the
meta's start month to the month being asked about, so a past month answers as
that month stood and cancelling in December cannot rewrite what September
reported.

**No act of the owner's waives the instalment.** `meta_ask_calc` reads what the
meta opened the month with and nothing else; contributing, cancelling and
editing are separate terms in the month, never adjustments to what it asks.

The one thing that ends the series is the purchase, and only from the month
after the one it was made in — the purchase month still charges, because what
it asks is part of what covered the thing. Saying the meta wants a new amount
or a new month from then on resumes it, and it stays resumed (ADR-0048,
ADR-0049, narrowing ADR-0046 on this point).

This module does not import `services.funds`, and `services.funds` does not
import this. Both read the same `MonthAggregate` and hand their folds to
`services.month`, which is the one place the two nouns meet.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from ..domain.dtos import MetaStatus
from ..domain.errors import NotFound, ValidationError
from ..domain.models import Meta, MetaAmendment, MetaContribution
from ..domain.money import to_cop_cents
from ..domain.rules import (
    meta_ask_calc,
    months_to_meta,
    next_year_month,
    uncovered_excess_calc,
    year_month_of,
)
from .month_aggregate import MonthAggregate, load_month, require_year_month


@dataclass(frozen=True)
class MetaPreview:
    """What a meta would ask before it exists (AC-45).

    The surprise arrives at creation, never later on the headline.
    """

    asks: int
    over_the_month: bool


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
    require_year_month(target_month, "target_month")
    if target_month < today_month:
        raise ValidationError(f"there is no way to save into the past: {target_month} is behind {today_month}")


def _contributions_in(agg: MonthAggregate, meta: Meta, month: str) -> int:
    return agg.contributions.get(meta.id, {}).get(month, 0)


def _bought(agg: MonthAggregate, meta: Meta) -> bool:
    """Whether a purchase has been pointed at this meta, in any month up to now."""
    return bool(agg.linked_to(meta.id))


def _bought_in(agg: MonthAggregate, meta: Meta) -> str | None:
    """The month the thing was first bought, if it was.

    Posted only. A debt owed this month is netted against what the meta holds
    because it costs this month (AC-12), and that is the month's arithmetic; it
    is not the meta finishing. A planned purchase leaves the meta asking until
    the money leaves (AC-43).
    """
    months = [year_month_of(tx.date) for tx in agg.linked_to(meta.id)]
    return min(months) if months else None


def _finished_before(agg: MonthAggregate, meta: Meta, month: str) -> bool:
    """Whether the meta had already finished when this month began.

    A purchase ends the series as of the month it was made: that month still
    asks, because what it asks is part of what covered the purchase, and every
    month after it does not (AC-8).

    Saying the meta wants more — a new amount, or a new month — is AC-8's
    second and third offers, and it starts a new series from the month the
    owner said it. So an amendment resumes the meta and it stays resumed.

    The purchase month counts as one where the owner may say it. That is where
    the screen puts the two offers: a meta completes the moment its purchase is
    linked, and the answer is given on the same screen, in the same month. An
    amendment later than the month being read never reaches back into it — a
    past month answers as that month stood (AC-27).
    """
    bought_in = _bought_in(agg, meta)
    if bought_in is None or month <= bought_in:
        return False
    return not any(bought_in <= row.year_month <= month for row in agg.amendments.get(meta.id, []))


@dataclass(frozen=True)
class _Month:
    """What one month did to a meta.

    `contributed` is what the meta **took** of what the owner offered by hand,
    which is not always the whole of it: the room is recomputed on every read,
    so lowering the amount or dating the purchase before this month can leave
    part of a contribution that fitted when it was made with nowhere to go.
    """

    ask: int
    holds: int
    released: int = 0
    contributed: int = 0


def _wanted_as_of(meta: Meta, amendments: Iterable[MetaAmendment], month: str) -> tuple[int, str]:
    """What the meta wanted, and by when, as of one month (AC-11).

    The meta's own amount and target are the first term of the series; each
    amendment replaces them from its own month on, so the answer is the last one
    at or before the month. Nothing is rewritten, which is why a past month
    still answers as that month stood (AC-27).

    The rule lives here alone: the read path folds it over the rows the
    aggregate carries and the write path over the rows it queries, and a second
    copy is how an edit came to silently undo an earlier one.

    Args:
        meta: the meta, whose own columns are the series' first term.
        amendments: this meta's amendments, in any order.
        month: the month being asked about, YYYY-MM.
    """
    effective = [row for row in amendments if row.year_month <= month]
    if not effective:
        return meta.amount, meta.target_month
    last = max(effective, key=lambda row: row.year_month)
    return last.amount, last.target_month


def _wanted_in(agg: MonthAggregate, meta: Meta, month: str) -> tuple[int, str]:
    """What the meta wanted as of one month, over the amendments in memory."""
    return _wanted_as_of(meta, agg.amendments.get(meta.id, ()), month)


def _month_of(agg: MonthAggregate, meta: Meta, month: str, opening: int) -> _Month:
    """What one month does to a meta that entered it holding `opening`.

    A meta stops the month after its purchase and keeps what it had: the thing
    is bought, and asking again would set money aside for something the owner
    already owns. The purchase month itself still asks, because what it asks is
    part of what covered the purchase (AC-12). Nothing is freed either — that
    money is in the thing (AC-39).

    Holding more than the meta wants means the owner lowered the amount below
    what it already had: the excess is freed and the meta asks nothing. A month
    never overfills either — a contribution larger than what is missing is
    taken only up to the amount.
    """
    if _finished_before(agg, meta, month):
        return _Month(ask=0, holds=opening)
    amount, target = _wanted_in(agg, meta, month)
    if opening > amount:
        return _Month(ask=0, holds=amount, released=opening - amount)
    ask = meta_ask_calc(amount, opening, months_to_meta(month, target))
    contributed = min(_contributions_in(agg, meta, month), max(amount - opening - ask, 0))
    return _Month(ask=ask, holds=opening + ask + contributed, contributed=contributed)


@dataclass(frozen=True)
class _Walked:
    """A meta folded to one month, and whether it had finished by the end of it.

    Two acts finish a meta and neither is a field on it: the purchase, which the
    aggregate carries, and lowering the amount below what it already held
    (AC-16), which only exists as a released month inside the fold. Both are
    answered by the one walk that produced the figures, so nothing folds twice.
    """

    month: _Month
    finished: bool


def _walk(agg: MonthAggregate, meta: Meta) -> _Walked:
    """Fold the meta forward to the month this aggregate holds (ADR-0046).

    What a month holds is what the next one opens with — one rule, one line,
    rather than one per branch of the month.
    """
    if agg.year_month < meta.start_month:
        return _Walked(_Month(ask=0, holds=0), finished=False)
    finished = _bought_in(agg, meta) is not None
    month, opening = meta.start_month, meta.stated_opening or 0
    while month < agg.year_month:
        step = _month_of(agg, meta, month, opening)
        finished = finished or step.released > 0
        opening, month = step.holds, next_year_month(month)
    last = _month_of(agg, meta, month, opening)
    return _Walked(last, finished or last.released > 0)


def _status(agg: MonthAggregate, meta: Meta, walked: _Walked, cancelled: bool = False) -> MetaStatus:
    """What one meta reports for the month this aggregate holds.

    The walk is handed in rather than taken, the way a fund's is: every figure
    below comes out of it, and the month reads several of them per meta.

    A meta is **complete** when it will ask nothing after this month: the thing
    was bought and the owner has not restarted it, or he lowered the amount
    below what it already held — strictly below, because a meta that has
    exactly filled up has not finished: it is waiting for the purchase, and
    AC-17 keeps it running while its sibling completes. What a full meta stops
    doing is asking, and that falls out of the arithmetic rather than a flag.

    Saying a bought meta wants more resumes it and it stays resumed
    (ADR-0049), so it is running again — the screen names it neither cumplida
    nor closable, and offers to put money in. A purchase is timeless and this
    is not: the question is what the month after this one will ask.
    """
    month = walked.month
    amount, target = _wanted_in(agg, meta, agg.year_month)
    bought = _bought(agg, meta)
    complete = _finished_before(agg, meta, next_year_month(agg.year_month)) or month.released > 0
    progress = min(round(month.holds * 100 / amount), 100) if amount else 0
    return MetaStatus(
        meta_id=meta.id,
        name=meta.name,
        year_month=agg.year_month,
        amount=amount,
        currency=meta.currency,
        target_month=target,
        asks=month.ask,
        asks_cop=to_cop_cents(month.ask, meta.currency, agg.trm),
        holds=month.holds,
        progress=progress,
        complete=complete,
        closed=meta.closed,
        waiting=target < agg.year_month and not bought and not meta.closed,
        cancelled=cancelled,
        released=_released_by(agg, meta, walked) if cancelled else to_cop_cents(month.released, meta.currency, agg.trm),
    )


def statuses(agg: MonthAggregate) -> list[MetaStatus]:
    """Every meta the month charges, as the month reports it. No DB access.

    A closed meta is among them. Closing releases nothing (AC-39), so the month
    the purchase was made in goes on charging its instalment, and a breakdown
    that named every other claim but not that one would not add up. Leaving the
    metas screen is a different act, and `list_metas` is where it happens.
    """
    return [_status(agg, meta, _walk(agg, meta)) for meta in agg.metas]


@dataclass(frozen=True)
class MetaFold:
    """What every meta does to one month, folded once.

    `lines` is what each of them reports: the live ones, and the ones cancelled
    in this month, which the month must still name because it charged their
    instalment and handed back what they held.

    `asks` is what they claim of the month in COP, the cancelled ones included
    — cancelling part-way through does not hand the instalment back, and
    releasing more than was ever taken would mint money (product ADR-014). The
    two are one term and are never offered apart: a caller free to take the
    first and forget the second is how a charge goes unnamed, which is what
    ADR-0049's postmortem is about.

    `contributed` is what the metas **took** of what the owner set aside by hand
    this month, and never what he offered them: a meta with no room for all of
    it leaves the rest in the month (AC-14), and charging the offer would take
    that rest out of the money available without it reaching anything. Cancelled
    metas are in it for the same reason `asks` counts them — charging one side
    and not the other would hand him that money twice. `released` is what came
    back to the month, from cancellations and from amounts lowered below what
    the meta already held (AC-15, AC-16); it is read for that one month and
    never again, so November cannot give back what October already gave.
    `uncovered` is what each linked purchase cost past what its meta had
    (AC-12), the seam where double counting would enter.

    All of it comes out of one walk per meta, because walking the metas is the
    dominant cost of the month's read path.
    """

    lines: list[MetaStatus]
    asks: int
    contributed: int
    released: int
    uncovered: int


def fold(agg: MonthAggregate) -> MetaFold:
    """Every meta's month, walked once. The seam `services.month` reads."""
    cancelled = agg.cancelled_this_month
    charged = list(agg.metas) + cancelled
    walked = {meta.id: _walk(agg, meta) for meta in charged}
    return MetaFold(
        lines=[_status(agg, meta, walked[meta.id]) for meta in agg.metas]
        + [_status(agg, meta, walked[meta.id], cancelled=True) for meta in cancelled],
        asks=sum(_ask_in_cop(agg, meta, walked[meta.id]) for meta in charged),
        contributed=sum(to_cop_cents(walked[meta.id].month.contributed, meta.currency, agg.trm) for meta in charged),
        released=sum(to_cop_cents(walked[meta.id].month.released, meta.currency, agg.trm) for meta in agg.metas)
        + sum(_released_by(agg, meta, walked[meta.id]) for meta in cancelled),
        uncovered=sum(_meta_uncovered(agg, meta, walked[meta.id]) for meta in agg.metas),
    )


def _off_the_screen(agg: MonthAggregate, meta: Meta, walked: _Walked) -> bool:
    """Whether the metas screen leaves this meta out of the month being read.

    A meta that had not been created yet is no part of that month, and listing
    it would put `lleva 0 · pide 0 · 0%` in every month before it existed.

    A closed one leaves from the month it finished, and not one month earlier:
    a month it ran through still names it with what it held and what it asked,
    because every figure the screen shows is worked out from the month being
    read (AC-27).
    """
    if agg.year_month < meta.start_month:
        return True
    return meta.closed and walked.finished


def list_metas(session: Session, year_month: str) -> list[MetaStatus]:
    """Every live meta, as the month reports it.

    Ordered the way the screen needs them (AC-44): the ones waiting on an
    answer first — completed and not yet closed, then past their month — and
    the ones still running below, nearest month first.

    Raises:
        ValidationError: malformed year_month.
        MissingRate: no TRM is set.
    """
    require_year_month(year_month)
    agg = load_month(session, year_month)
    walked = {meta.id: _walk(agg, meta) for meta in agg.metas}
    found = [
        _status(agg, meta, walked[meta.id]) for meta in agg.metas if not _off_the_screen(agg, meta, walked[meta.id])
    ]
    return sorted(found, key=lambda m: (not (m.complete or m.waiting), m.target_month, m.name))


def list_archived(session: Session) -> list[Meta]:
    """Every meta the owner cancelled, newest cancellation first.

    A cancelled meta is archived and never destroyed (AC-29), so the only way
    the promise is worth anything is if the owner can still see it. It reports
    no month's figures — it holds nothing and asks nothing — so this answers
    with the metas themselves rather than a month's reading of them, and needs
    no rate to do it.

    A closed meta is archived too and belongs to none of this: it handed nothing
    back, and restoring it would charge the month a purchase already made.
    """
    found = session.exec(select(Meta).where(Meta.archived, Meta.closed == False)).all()  # noqa: E712
    return sorted(found, key=lambda meta: (meta.cancelled_month or "", meta.name), reverse=True)


def _ask_in_cop(agg: MonthAggregate, meta: Meta, walked: _Walked) -> int:
    """What one meta asks the month, in COP cents.

    A meta held in another currency converts at the app's single rate, the same
    way every other foreign figure does (ADR-0031).
    """
    return to_cop_cents(walked.month.ask, meta.currency, agg.trm)


def _meta_uncovered(agg: MonthAggregate, meta: Meta, walked: _Walked) -> int:
    """What one linked purchase cost past what its meta had, in COP cents.

    A linked movement is out of its category's spending entirely (`spent_in`
    drops it), so the only thing it can cost the month is its own excess: only
    what the meta cannot cover costs the month (AC-43), and what it can cover
    is what it holds. Measuring against the instalment alone charged a hand
    contribution once as a contribution and again as a gap (AC-13, AC-14).
    """
    spent = sum(
        agg.to_cop_cents(tx)
        for tx in agg.linked_to(meta.id, posted_only=False)
        if year_month_of(tx.date) == agg.year_month
    )
    if not spent:
        return 0
    return to_cop_cents(
        uncovered_excess_calc(_to_meta_currency(agg, meta, spent), walked.month.holds),
        meta.currency,
        agg.trm,
    )


def _to_meta_currency(agg: MonthAggregate, meta: Meta, cop_cents: int) -> int:
    """A purchase reaches its meta in the meta's own currency (AC-26)."""
    if meta.currency == "COP":
        return cop_cents
    return round(cop_cents / float(agg.trm))


def _released_by(agg: MonthAggregate, meta: Meta, walked: _Walked) -> int:
    """What cancelling one meta hands back to the month: everything it held."""
    return to_cop_cents(walked.month.holds, meta.currency, agg.trm)


def contribute(session: Session, meta_id: int, *, year_month: str, amount: int) -> MetaContribution:
    """Set money aside by hand, on top of what the meta asks that month.

    Trimmed to what is missing: a meta never holds more than the thing costs
    (AC-14). Returns the contribution as it was written, whose `amount` is what
    was actually put in — money may go into any month (AC-42), so the row just
    made is not always the newest one on record and cannot be found again by
    re-reading the history.

    Raises:
        NotFound: no such meta.
        ValidationError: an amount at or below zero, or a cancelled meta.
    """
    meta = _require_meta(session, meta_id)
    if meta.archived:
        raise ValidationError(f"the meta {meta.name!r} was cancelled and takes no contribution")
    if amount <= 0:
        raise ValidationError("a contribution needs an amount above zero")
    room = _room_left(session, meta, year_month)
    put_in = min(amount, room)
    if put_in <= 0:
        raise ValidationError(f"the meta {meta.name!r} needs nothing more")
    made = MetaContribution(meta_id=meta.id, year_month=year_month, amount=put_in)
    session.add(made)
    session.commit()
    session.refresh(made)
    return made


def _room_left(session: Session, meta: Meta, year_month: str) -> int:
    agg = load_month(session, year_month)
    if _finished_before(agg, meta, year_month):
        return 0
    wanted, _ = _wanted_in(agg, meta, year_month)
    return wanted - _walk(agg, meta).month.holds


def remove_contribution(session: Session, contribution_id: int) -> None:
    """Take back a contribution: the meta and its month return to what they were.

    Raises:
        NotFound: no such contribution.
    """
    row = session.get(MetaContribution, contribution_id)
    if row is None:
        raise NotFound(f"contribution {contribution_id} not found")
    session.delete(row)
    session.commit()


def contributions_of(session: Session, meta_id: int) -> list[MetaContribution]:
    """Every contribution made to one meta, oldest first (AC-42)."""
    rows = session.exec(select(MetaContribution).where(MetaContribution.meta_id == meta_id)).all()
    return sorted(rows, key=lambda r: (r.year_month, r.id))


def cancel_meta(session: Session, meta_id: int, *, year_month: str) -> Meta:
    """Stop a meta and hand back what it held, in this month (AC-15).

    Cancelling is not closing. A meta whose purchase has been linked is
    finished, not abandoned, and closing it releases nothing (AC-39).

    Raises:
        NotFound: no such meta.
        ValidationError: the meta was already bought.
    """
    meta = _require_meta(session, meta_id)
    if _bought(load_month(session, year_month), meta):
        raise ValidationError(f"the meta {meta.name!r} was bought, so it is closed rather than cancelled")
    meta.archived = True
    meta.cancelled_month = year_month
    session.add(meta)
    session.commit()
    session.refresh(meta)
    return meta


def close_meta(session: Session, meta_id: int, *, year_month: str) -> Meta:
    """Finish a meta whose purchase has been made. Releases nothing (AC-39).

    A meta that never finished is refused, because closing releases nothing: it
    would archive money the month had already set aside without handing it back
    to anything, and the month's terms would stop adding up. Cancelling is the
    act for a meta the owner no longer wants, and it says which month it freed.

    What is asked is whether the meta ever finished, not whether it is finished
    now. A meta the owner kept on after its purchase is asking again, and
    cancelling it is already refused for having been bought (AC-39) — reading
    the month's answer here would leave it with no way to end at all.

    Raises:
        NotFound: no such meta.
        ValidationError: the meta never finished.
    """
    meta = _require_meta(session, meta_id)
    if not _walk(load_month(session, year_month), meta).finished:
        raise ValidationError(f"the meta {meta.name!r} is still running, so it is cancelled rather than closed")
    meta.closed = True
    meta.archived = True
    session.add(meta)
    session.commit()
    session.refresh(meta)
    return meta


def restore_meta(session: Session, meta_id: int, *, today: str) -> Meta:
    """Bring a cancelled meta back, starting again from nothing.

    Cancelling handed everything it held back to that month (AC-15), so there
    is nothing left to resume from: a restored meta begins at the month it is
    restored in and fills from zero. Resuming with the old holdings would give
    the owner the same money twice.

    A meta that was never cancelled is refused: restoring rewrites its start
    month and drops what the owner stated it already had, which on a running
    meta would throw away the history every figure is derived from.

    A closed meta is refused for the same reason: its purchase was made, and
    bringing it back would charge the month an instalment toward a thing the
    owner already owns.

    Raises:
        NotFound: no such meta.
        ValidationError: the meta is not archived, it was closed rather than
            cancelled, or a live meta has taken its name since (AC-22).
    """
    meta = _require_meta(session, meta_id)
    if not meta.archived:
        raise ValidationError(f"the meta {meta.name!r} is still running, so there is nothing to bring back")
    if meta.closed:
        raise ValidationError(f"the meta {meta.name!r} was bought and closed, so there is nothing to bring back")
    _refuse_name_already_held(session, meta.name, excluding=meta.id)
    meta.archived = False
    meta.closed = False
    meta.cancelled_month = None
    meta.start_month = today
    meta.stated_opening = None
    session.add(meta)
    session.commit()
    session.refresh(meta)
    return meta


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

    A field left out of `changes` keeps what the meta wants *now*, which is the
    last amendment rather than the columns: those hold the original spec and
    stop moving the moment the first edit is made. Defaulting from them would
    let one edit silently undo an earlier one, since a month's amendment carries
    both halves and the last one written wins.

    Raises:
        NotFound: no such meta.
        ValidationError: every refusal `create_meta` raises.
    """
    meta = _require_meta(session, meta_id)
    wanted = _wanted_now(session, meta, today)
    name = changes.get("name", meta.name)
    amount = changes.get("amount", wanted[0])
    target_month = changes.get("target_month", wanted[1])
    _validate_spec(name, amount, target_month, today)
    _refuse_name_already_held(session, name, excluding=meta.id)
    meta.name = name.strip()
    session.add(meta)
    if (amount, target_month) != wanted:
        _amend(session, meta, today, amount, target_month)
    session.commit()
    session.refresh(meta)
    return meta


def _wanted_now(session: Session, meta: Meta, year_month: str) -> tuple[int, str]:
    """What the meta wanted as of one month, over the amendments on record."""
    rows = session.exec(select(MetaAmendment).where(MetaAmendment.meta_id == meta.id)).all()
    return _wanted_as_of(meta, rows, year_month)


def _amend(session: Session, meta: Meta, year_month: str, amount: int, target_month: str) -> None:
    """Record what the meta wants from this month on, replacing this month's own.

    One row per month: editing twice in October leaves October with one
    amendment, the last one, rather than a trail nothing reads.
    """
    existing = session.exec(
        select(MetaAmendment).where(MetaAmendment.meta_id == meta.id, MetaAmendment.year_month == year_month)
    ).first()
    if existing is not None:
        existing.amount = amount
        existing.target_month = target_month
        session.add(existing)
        return
    session.add(MetaAmendment(meta_id=meta.id, year_month=year_month, amount=amount, target_month=target_month))


def preview_meta(
    *,
    amount: int,
    target_month: str,
    today: str,
    income: int,
    trm: Decimal,
    currency: str = "COP",
    stated_opening: int | None = None,
) -> MetaPreview:
    """What a meta would ask in its first month, before it exists (AC-45).

    What the owner says he already put by is the month it would open with
    (AC-34), so the figure the form shows is the one the meta will ask.

    `asks` is the meta's own currency, the way every figure a meta reports is
    (AC-26). The warning is a peso comparison and converts before it makes it:
    a dollar instalment and the month's income are not the same unit, and
    weighing one against the other unconverted is what ADR-0049 names.

    Raises:
        ValidationError: every refusal `create_meta` raises about the amount
            and the month.
    """
    _validate_spec("preview", amount, target_month, today)
    months_left = months_to_meta(today, target_month)
    asks = meta_ask_calc(amount, stated_opening or 0, months_left)
    costs_the_month = to_cop_cents(asks, currency, trm)
    return MetaPreview(asks=asks, over_the_month=income > 0 and costs_the_month > income)

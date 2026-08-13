"""Output DTOs returned by the fund and recurring services (not DB models)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RecurringOccurrence


@dataclass(frozen=True)
class FundLine:
    """One fund, as the screen and the assistant list it."""

    fund_id: int
    category_id: int
    name: str
    rule: str
    start_month: str
    accumulates: bool


@dataclass(frozen=True)
class FundCharge:
    """One term of what a fund asks: the charge it is filling for (ADR-0054).

    `costs` is the whole charge in pesos and `asks` its share of this month,
    which is `costs` less what the fund already holds against it, spread over
    the months left before `charge_month`. A charge landing in the month being
    read is due rather than being saved for, which is `charge_month` against
    that month and is not carried apart.

    `can_be_spread` says a whole month fits between this charge and the one
    after it. A charge that lands every month never has one, which is why it
    can never be the surprise the warning is about.
    """

    name: str
    costs: int
    charge_month: str
    asks: int
    can_be_spread: bool


@dataclass(frozen=True)
class FundStatus:
    """What one fund asks, holds and reports for one month (ADR-0043).

    `spent` is what the category cost that month; `carries` is what survives
    into the next one, which is nothing at all for a fund that resets; and
    `next_month_has` is that carry plus what the rule asks then, so a screen
    can say what next month starts with without doing the arithmetic itself.

    `charges` are the terms `asks` is the sum of, so the figure opens into
    what produced it and nothing in it is unattributable (ADR-0054). Only the
    rules that fill for dated charges have any.

    `has_repeating_charges` is about the category, not the month, and exists
    because an empty `charges` says two different things: every charge is
    skipped or already paid, which passes, and the category has no repeating
    charge left, which does not (AC-8 against AC-9).

    `averaged_over` is filled by the `average` rule only; `spreads_over` and
    `whole_by` by the rules that save toward a dated charge.
    """

    fund_id: int
    category_id: int
    name: str
    year_month: str
    rule: str
    asks: int
    holds: int
    spent: int
    carries: int
    next_month_has: int
    accumulates: bool
    accumulation_is_implied: bool
    on_track: bool
    charges: list[FundCharge] = field(default_factory=list)
    has_repeating_charges: bool = False
    averaged_over: int | None = None
    spreads_over: int | None = None
    whole_by: str | None = None


@dataclass(frozen=True)
class MetaStatus:
    """What one meta asks and holds for one month (ADR-0046).

    `holds` is what it opened the month with plus what it asks plus what the
    owner contributed by hand in it — the contribution is inside `holds` and is
    not reported apart, because the figure a screen shows is the month-level
    one. `progress` is `holds` against the amount, capped at one hundred.

    `waiting` says the target month has passed with no purchase linked: the
    meta asks nothing and is holding still until the owner links, closes or
    moves it (AC-19).

    `cancelled` is true only in the month the owner cancelled it, which is the
    last month that names it. A breakdown that listed it without saying which
    one it was would leave the owner unable to tell a live meta from one they
    had just called off.

    `released` is what this meta handed back to the month — everything it held
    if it was cancelled, the excess if the owner lowered its amount below what
    it already had. Every meta carries its own, so a breakdown can name where
    each give-back came from and still add up.

    Two currencies live here, and which is which is the point. `amount`,
    `asks`, `holds` are the meta's own, because every figure a meta reports is
    worked out in the currency it is held in (AC-26). `asks_cop` and `released`
    are the month's pesos, converted at read time from the one rate
    (ADR-0031) — a breakdown of the money available is a peso column and has to
    add up as one.
    """

    meta_id: int
    name: str
    year_month: str
    amount: int
    currency: str
    target_month: str
    asks: int
    asks_cop: int
    holds: int
    progress: int
    complete: bool
    closed: bool
    waiting: bool
    cancelled: bool = False
    released: int = 0


@dataclass(frozen=True)
class MonthSplit:
    """What share of a month is spent, set aside, or left (AC-37).

    `consumo + ahorro + libre == income` in every month, including the ones the
    owner contributes, cancels or edits in — which is why `libre` is a
    subtraction and never a second sum.

    `ahorro` is net: a month a meta is cancelled is a month savings come back
    out, so it can be negative. `set_aside` is the same month before the
    give-back — what the owner actually put by — and `released` is what came
    back: `set_aside - released == ahorro`. The second name says the ACT rather
    than the noun, so it cannot be read as a synonym for the first. Both travel
    because a month that had one of each would otherwise report a negative
    ahorro and hide the money that was genuinely set aside beside it.

    `gave_back` is every meta that returned money this month, cancelled or
    lowered, each carrying its own share, so `Σ gave_back[].released` is
    `released` and a screen can name where each one came from.
    """

    year_month: str
    income: int
    consumo: int
    ahorro: int
    libre: int
    ahorro_share: int
    set_aside: int
    set_aside_share: int
    released: int
    gave_back: list[MetaStatus]


@dataclass(frozen=True)
class MonthAvailable:
    """The money available for one month, opened into the terms that make it.

    `income − Σ funds asks − Σ metas asks − contributed + released − uncovered
    = free` holds exactly. `uncovered` is one term and not three (AC-10,
    ADR-0044); `contributed` and `released` are their own because a month the
    owner acted in must say so rather than fold it into another term
    (ADR-0046).
    """

    year_month: str
    income: int
    funds: list[FundStatus]
    uncovered: int
    free: int
    metas: list[MetaStatus] = field(default_factory=list)
    contributed: int = 0
    released: int = 0


@dataclass(frozen=True)
class MonthRates:
    """What the owner earns and what the owner costs, each a month's worth.

    Rates are smoothed across a cycle and are never the money available: a
    quarterly income counts every month here and only in the month it is due
    there (AC-14b).
    """

    year_month: str
    earning: int
    cost: int
    margin: int


@dataclass(frozen=True)
class FundPreview:
    """What a fund would ask before it exists, and the warning it carries (AC-24).

    `crowded` are the charges the warning is about: the ones that could be
    spread and have no month to spread over. All of them, because naming one of
    two would promise a month cheaper than it is. They travel beside `warning`
    rather than instead of it because the two surfaces word them differently —
    the screen says it in Spanish with the owner's own money format, while the
    assistant prints the sentence it is handed (ADR-0054).

    `has_something_to_spread` answers the category rather than the rule being
    previewed: a category whose charges all land every month can only ever ask
    zero from the obligations rule, so it is not offered one (ADR-0054).
    """

    category_id: int
    would_ask: int
    warning: str | None = None
    crowded: list[FundCharge] = field(default_factory=list)
    has_something_to_spread: bool = False


@dataclass(frozen=True)
class RunFailure:
    """One obligation the engine could not charge, and why (ADR-0036)."""

    recurring_id: int
    name: str
    reason: str

    def __str__(self) -> str:
        return f"{self.name}: {self.reason}"


@dataclass(frozen=True)
class MaterializationReport:
    """The outcome of one engine run: what landed, and what needs attention.

    A run is no longer all-or-nothing — each charge commits on its own, so a
    failure costs its obligation the day and nothing else (ADR-0036).
    """

    created: list[RecurringOccurrence]
    failures: list[RunFailure]

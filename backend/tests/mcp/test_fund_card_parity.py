"""The assistant's fund card says every figure the screen is offered (ADR-0006/0009).

`services.funds.fund_status` is the one place a fund's month is computed, and
both surfaces read it: the screen through `FundStatusOut`, the assistant through
`format.fund_card`. Nothing else made them agree — feature 010 added three
figures and deleting all three from the card left both test streams green.

These are the tests that would have caught it. They compare the surfaces against
the DTO rather than against each other, so a figure added to the fund and given
to only one of them fails here.

`NOT_ON_THE_CARD` is the third answer, and the only one that admits a gap: what
the fund reports and the assistant is deliberately not given. Feature 014 put
the breakdown there because the owner left that surface alone on purpose
(ADR-0054, AC-18), and naming it is what keeps the divergence written instead
of discovered. A field arrives in that tuple by decision; one that arrives by
omission still fails the classification test.
"""

from dataclasses import fields

from quaestor.api.schemas import FundStatusOut
from quaestor.domain.dtos import FundStatus
from quaestor.mcp import format

MONEY_FIGURES = ("asks", "holds", "spent", "carries", "next_month_has")

DESCRIBES_THE_FUND = (
    "fund_id",
    "category_id",
    "recurring_id",
    "name",
    "currency",
    "year_month",
    "rule",
    "accumulates",
    "accumulation_is_implied",
    "on_track",
    "averaged_over",
    "spreads_over",
    "whole_by",
)

NOT_ON_THE_CARD = ("charges", "has_repeating_charges", "asks_cop", "holds_cop")
"""`asks_cop` and `holds_cop` are `asks` and `holds` in pesos, and they are held
back on purpose: the card states each figure once, in the fund's own currency,
and printing both would say the same money twice. They exist for the totals that
add funds together (ADR-0057)."""


def _status(**overrides) -> FundStatus:
    spec = {
        "fund_id": 1,
        "category_id": 1,
        "name": "Mercado",
        "year_month": "2026-11",
        "rule": "fixed",
        "asks": 110_000,
        "holds": 220_000,
        "spent": 330_000,
        "carries": 440_000,
        "next_month_has": 550_000,
        "accumulates": True,
        "accumulation_is_implied": False,
        "on_track": True,
    }
    return FundStatus(**{**spec, **overrides})


def test_the_card_states_every_money_figure_the_fund_reports():
    status = _status()
    card = format.fund_card(status)
    for figure in MONEY_FIGURES:
        rendered = format.money(getattr(status, figure), status.currency)
        assert rendered in card, f"the card never states {figure} ({rendered})"


def test_the_card_states_the_figures_in_the_fund_s_own_currency():
    """A fund filling for a dollar charge does not print dollars as pesos.

    The defect this pins is two days old and cost 1.325 green tests: hard-coding
    "COP" where the noun's own currency belonged reported an 800 dollar
    contribution as $800 instead of $3.200.000 (CHARTER §6).
    """
    card = format.fund_card(_status(currency="USD", asks=5_000, asks_cop=20_000_000))
    assert format.money(5_000, "USD") in card
    assert format.money(5_000, "COP") not in card


def test_a_new_figure_on_the_fund_has_to_be_classified_before_it_ships():
    reported = {field.name for field in fields(FundStatus)}
    classified = set(DESCRIBES_THE_FUND) | set(NOT_ON_THE_CARD)
    assert reported - classified == set(MONEY_FIGURES)


def test_what_the_card_is_not_given_is_not_on_it():
    card = format.fund_card(_status())
    assert not [held_back for held_back in NOT_ON_THE_CARD if held_back in card]


def test_the_screen_and_the_assistant_are_offered_the_same_fields():
    assert {field.name for field in fields(FundStatus)} == set(FundStatusOut.model_fields)

"""The assistant's fund card says every figure the screen is offered (ADR-0006/0009).

`services.funds.fund_status` is the one place a fund's month is computed, and
both surfaces read it: the screen through `FundStatusOut`, the assistant through
`format.fund_card`. Nothing else made them agree — feature 010 added three
figures and deleting all three from the card left both test streams green.

These are the tests that would have caught it. They compare the surfaces against
the DTO rather than against each other, so a figure added to the fund and given
to only one of them fails here.
"""

from dataclasses import fields

from quaestor.api.schemas import FundStatusOut
from quaestor.domain.dtos import FundStatus
from quaestor.mcp import format

MONEY_FIGURES = ("asks", "holds", "spent", "carries", "next_month_has")

DESCRIBES_THE_FUND = (
    "fund_id",
    "category_id",
    "name",
    "year_month",
    "rule",
    "accumulates",
    "accumulation_is_implied",
    "on_track",
    "averaged_over",
    "spreads_over",
    "whole_by",
)


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
        rendered = format.money(getattr(status, figure), "COP")
        assert rendered in card, f"the card never states {figure} ({rendered})"


def test_a_new_figure_on_the_fund_has_to_be_classified_before_it_ships():
    reported = {field.name for field in fields(FundStatus)}
    assert reported - set(DESCRIBES_THE_FUND) == set(MONEY_FIGURES)


def test_the_screen_and_the_assistant_are_offered_the_same_fields():
    assert {field.name for field in fields(FundStatus)} == set(FundStatusOut.model_fields)

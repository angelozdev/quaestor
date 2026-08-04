"""The assistant's fund tools: the same capabilities, the same refusals (AC-28).

The tools speak category names and answer in text; every rule they appear to
enforce is `services.funds` speaking through `_as_text`.
"""

from quaestor.mcp.tools import funds as fund_tools
from quaestor.services import categories, fx


def _seeded(session, name="Restaurantes", is_income=False):
    fx.set_trm(session, "4000")
    return categories.create_category(session, name, is_income=is_income)


def _create(session, name="Restaurantes", amount=20_000_000, start="2026-11"):
    return fund_tools.create_fund(
        session,
        fund_tools.CreateFundInput(category=name, rule="fixed", amount=amount, start_month=start),
    )


def test_creating_a_fund_confirms_the_rule_it_stored(session):
    _seeded(session)
    out = _create(session)
    assert out.startswith("✅ Fund on **Restaurantes**")
    assert "200000.00 COP each month" in out
    assert "from 2026-11" in out


def test_the_list_names_the_category_and_says_no_funds_when_empty(session):
    _seeded(session)
    assert fund_tools.list_funds(session) == "No funds."
    _create(session)
    assert "Restaurantes" in fund_tools.list_funds(session)


def test_a_fund_on_an_income_category_is_refused_in_words(session):
    _seeded(session, "Salario", is_income=True)
    out = _create(session, "Salario")
    assert "Invalid input" in out and "going out" in out


def test_a_second_fund_on_the_same_category_is_refused_in_words(session):
    _seeded(session)
    _create(session)
    out = fund_tools.create_fund(
        session,
        fund_tools.CreateFundInput(category="Restaurantes", rule="average", window_months=3, start_month="2026-11"),
    )
    assert "already has a fund" in out


def test_an_unknown_category_is_a_not_found_the_agent_can_act_on(session):
    _seeded(session)
    out = _create(session, "Ninguna")
    assert "not found" in out


def test_the_status_of_one_fund_reads_a_month(session):
    _seeded(session)
    _create(session)
    out = fund_tools.fund_status(session, fund_tools.FundStatusInput(category="Restaurantes", month="2026-11"))
    assert "Asks: 200000.00 COP" in out
    assert "Holds: 0.00 COP" in out


def test_asking_for_a_fund_that_does_not_exist_says_how_to_make_one(session):
    _seeded(session)
    out = fund_tools.fund_status(session, fund_tools.FundStatusInput(category="Restaurantes", month="2026-11"))
    assert "has no fund" in out and "create_fund" in out


def test_the_money_available_states_its_terms_and_the_figure(session):
    _seeded(session)
    _create(session)
    out = fund_tools.money_available(session, fund_tools.MonthInput(month="2026-11"))
    assert "Money available — 2026-11" in out
    assert "Fund Restaurantes: −200000.00 COP" in out
    assert "Available: -200000.00 COP" in out


def test_the_rates_are_a_separate_answer_from_the_money_available(session):
    _seeded(session)
    out = fund_tools.money_rates(session, fund_tools.MonthInput(month="2026-11"))
    assert "Monthly rates — 2026-11" in out
    assert "Earning:" in out and "Cost:" in out and "Margin:" in out
    assert "Money available" not in out


def test_a_malformed_month_is_refused_in_words(session):
    _seeded(session)
    assert "Invalid input" in fund_tools.money_available(session, fund_tools.MonthInput(month="2026-6"))


def test_reading_the_number_without_a_rate_says_to_set_one(session):
    categories.create_category(session, "Restaurantes")
    out = fund_tools.money_available(session, fund_tools.MonthInput(month="2026-11"))
    assert "No TRM is set" in out and "set_fx_rate" in out


def test_setting_what_a_fund_holds_goes_through_the_same_door(session):
    _seeded(session)
    _create(session)
    assert "✅" in fund_tools.set_fund(session, fund_tools.SetFundInput(category="Restaurantes", balance=5_000_000))
    out = fund_tools.fund_status(session, fund_tools.FundStatusInput(category="Restaurantes", month="2026-11"))
    assert "Holds: 50000.00 COP" in out


def test_deleting_a_fund_leaves_the_list_empty(session):
    _seeded(session)
    _create(session)
    assert fund_tools.delete_fund(session, fund_tools.FundInput(category="Restaurantes")) == (
        "✅ Fund on 'Restaurantes' deleted."
    )
    assert fund_tools.list_funds(session) == "No funds."


def test_the_preview_warns_without_creating_anything(session):
    _seeded(session)
    out = fund_tools.preview_fund(
        session,
        fund_tools.PreviewFundInput(
            category="Restaurantes",
            rule="target-by-date",
            target_amount=300_000_000,
            target_month="2026-11",
            start_month="2026-11",
        ),
    )
    assert "would ask 3000000.00 COP" in out
    assert "⚠️" in out and "leaves no month to save in" in out
    assert fund_tools.list_funds(session) == "No funds."

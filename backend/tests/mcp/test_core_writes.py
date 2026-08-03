from datetime import date

from quaestor.domain.models import TxType
from quaestor.mcp.tools import core
from quaestor.mcp.tools.core import (
    GetFxRateInput,
    RecordExpenseInput,
    RecordIncomeInput,
    SetFxRateInput,
    TransferInput,
)
from quaestor.services import accounts, fx

from tests.support.categories import a_named_category


def test_record_expense_confirms_and_moves_balance(session, seeded):
    out = core.record_expense(
        session,
        RecordExpenseInput(
            payee="Lunch",
            amount=5_000_000,  # 50k COP
            account="Bancolombia",
            category="Groceries",
            date=date(2026, 6, 18),
        ),
    )
    assert "Expense recorded" in out
    assert "Lunch" in out
    assert "50000.00 COP" in out
    # 100k - 50k = 50k, balance shown post-write
    assert accounts.get_account(session, seeded["account"].id).balance == 5_000_000
    assert "new balance: 50000.00 COP" in out


def test_record_expense_resolves_account_case_insensitively(session, seeded):
    out = core.record_expense(
        session,
        RecordExpenseInput(payee="Coffee", amount=800_000, account="bancolombia", category="Groceries"),
    )
    assert "Expense recorded" in out


def test_record_expense_unknown_account_returns_guidance(session, seeded):
    out = core.record_expense(
        session,
        RecordExpenseInput(payee="X", amount=1000, account="Nequi", category="Groceries"),
    )
    assert "Account 'Nequi' not found" in out
    assert "Bancolombia" in out  # lists what exists


def test_record_expense_applies_tags(session, seeded):
    core.record_expense(
        session,
        RecordExpenseInput(
            payee="Trip", amount=2_000_000, account="Bancolombia", tags=["trip", "june"], category="Groceries"
        ),
    )
    # tag filter through the read service proves the link was created
    from quaestor.services import transactions as tx_service

    assert len(tx_service.list_transactions(session, tag="trip")) == 1


def test_record_income_increments_balance(session, seeded):
    a_named_category(session, "Salary", TxType.income)
    out = core.record_income(
        session,
        RecordIncomeInput(
            payee="Salary", amount=3_200_000, account="Bancolombia", date=date(2026, 6, 18), category="Salary"
        ),
    )
    assert "Income recorded" in out
    assert accounts.get_account(session, seeded["account"].id).balance == 13_200_000


def test_transfer_confirms_both_balances(session, seeded):
    accounts.create_account(session, "Savings", "savings", "COP", balance=0)
    out = core.transfer(
        session,
        TransferInput(from_account="Bancolombia", to_account="Savings", amount=4_000_000),
    )
    assert "Transfer" in out
    assert "Bancolombia" in out and "Savings" in out
    assert "60000.00 COP" in out  # source 100k - 40k
    assert "40000.00 COP" in out  # destination 0 + 40k


def test_transfer_same_account_returns_imbalance_text(session, seeded):
    out = core.transfer(
        session,
        TransferInput(from_account="Bancolombia", to_account="Bancolombia", amount=1000),
    )
    assert "Could not record the transfer" in out


def test_set_fx_rate_confirms(session):
    out = core.set_fx_rate(session, SetFxRateInput(usd_cop=4150))
    assert out == "✅ USD→COP rate (TRM) set: 4150"


def test_set_fx_rate_overwrites_previous_trm(session):
    core.set_fx_rate(session, SetFxRateInput(usd_cop=4150))
    core.set_fx_rate(session, SetFxRateInput(usd_cop=4000))
    out = core.get_fx_rate(session, GetFxRateInput())
    assert out == "Current USD→COP rate (TRM): 4000"


def test_record_expense_unknown_category_returns_guidance(session, seeded):
    out = core.record_expense(
        session,
        RecordExpenseInput(payee="X", amount=1000, account="Bancolombia", category="DoesNotExist"),
    )
    assert "Category 'DoesNotExist' not found" in out


def test_usd_expense_without_trm_records_and_omits_equivalent_line(session):
    a_named_category(session, "Groceries", TxType.expense)
    accounts.create_account(session, "Amex", "credit", "USD", balance=0)
    out = core.record_expense(
        session,
        RecordExpenseInput(
            category="Groceries",
            payee="Spotify",
            amount=1200,
            account="Amex",
            currency="USD",
            date=date(2026, 6, 18),
        ),
    )
    assert "Expense recorded" in out
    assert "Spotify" in out
    assert "Equivalent" not in out


def test_usd_expense_with_trm_shows_cop_equivalent(session):
    a_named_category(session, "Groceries", TxType.expense)
    accounts.create_account(session, "Amex", "credit", "USD", balance=0)
    fx.set_trm(session, "4000")
    out = core.record_expense(
        session,
        RecordExpenseInput(
            category="Groceries",
            payee="Spotify",
            amount=1200,
            account="Amex",
            currency="USD",
            date=date(2026, 6, 18),
        ),
    )
    assert "Expense recorded" in out
    assert "Equivalent: 48000.00 COP" in out


def test_cross_currency_transfer_moves_sent_and_received(session, seeded):
    accounts.create_account(session, "Amex", "credit", "USD", balance=0)
    out = core.transfer(
        session,
        TransferInput(
            from_account="Bancolombia",
            to_account="Amex",
            amount=4_000_000,
            amount_received=100_000,
        ),
    )
    assert "Transfer" in out
    assert "(1000.00 USD received)" in out
    assert accounts.get_account(session, seeded["account"].id).balance == 6_000_000
    amex = next(a for a in accounts.list_accounts(session) if a.name == "Amex")
    assert amex.balance == 100_000


def test_cross_currency_transfer_without_amount_received_returns_text(session, seeded):
    accounts.create_account(session, "Amex", "credit", "USD", balance=0)
    out = core.transfer(
        session,
        TransferInput(from_account="Bancolombia", to_account="Amex", amount=4_000_000),
    )
    assert "Invalid input" in out
    assert "amount_received" in out


def test_record_expense_creates_its_category_in_one_call(session, seeded):
    from quaestor.services import categories as categories_service

    out = core.record_expense(
        session,
        RecordExpenseInput(payee="Banco", amount=1_200_000, account="Bancolombia", new_category="4x1000"),
    )
    assert "Expense recorded" in out
    created = next(c for c in categories_service.list_categories(session) if c.name == "4x1000")
    assert created.is_income is False


def test_record_income_creating_its_category_makes_an_income_category(session, seeded):
    from quaestor.services import categories as categories_service

    out = core.record_income(
        session,
        RecordIncomeInput(payee="Banco", amount=30_000_000, account="Bancolombia", new_category="Rendimientos"),
    )
    assert "Income recorded" in out
    assert [c.name for c in categories_service.list_categories(session, is_income=True)] == ["Rendimientos"]


def test_record_expense_with_no_category_is_refused_as_text(session, seeded):
    out = core.record_expense(
        session,
        RecordExpenseInput(payee="Exito", amount=2_000_000, account="Bancolombia"),
    )
    assert "category" in out
    assert accounts.get_account(session, seeded["account"].id).balance == 10_000_000


def test_record_expense_under_an_income_category_is_refused_as_text(session, seeded):
    a_named_category(session, "Salary", TxType.income)
    out = core.record_expense(
        session,
        RecordExpenseInput(payee="Exito", amount=2_000_000, account="Bancolombia", category="Salary"),
    )
    assert "direction" in out
    assert accounts.get_account(session, seeded["account"].id).balance == 10_000_000

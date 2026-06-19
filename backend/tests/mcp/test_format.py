from datetime import date
from decimal import Decimal

from quaestor.domain.errors import (
    MissingRate,
    NotFound,
    TransferImbalance,
    ValidationError,
)
from quaestor.domain.models import (
    Account,
    AccountType,
    Category,
    CategoryGroup,
    FxRate,
    Tag,
    Transaction,
    TxType,
)
from quaestor.mcp import format


def _expense(currency="COP", amount=4_000_000, to_base=4_000_000):
    return Transaction(
        date=date(2026, 6, 18),
        payee="Mercado",
        type=TxType.expense,
        amount=amount,
        currency=currency,
        fx_rate=Decimal("1"),
        to_base=to_base,
        account_id=1,
    )


def test_money_renders_major_units_and_currency():
    assert format.money(4_000_000, "COP") == "40000.00 COP"


def test_missing_rate_uses_canonical_sentence():
    text = format.domain_error_text(MissingRate("set usd_cop rate for 2026-06-18"))
    assert "USD→COP" in text
    assert "fijar_tasa_fx" in text


def test_not_found_passes_message_through():
    assert format.domain_error_text(NotFound("Account 'X' not found.")) == (
        "Account 'X' not found."
    )


def test_validation_error_is_framed():
    assert format.domain_error_text(ValidationError("amount must be > 0")).startswith(
        "Invalid input:"
    )


def test_transfer_imbalance_is_framed():
    assert format.domain_error_text(
        TransferImbalance("source and destination cannot be the same account")
    ).startswith("Could not record the transfer:")


def test_expense_confirmation_cop_omits_equivalent():
    acc = Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=6_000_000)
    text = format.expense_confirmation(_expense(), acc)
    assert "Expense recorded" in text
    assert "Mercado" in text
    assert "Bancolombia" in text
    assert "60000.00 COP" in text  # new balance
    assert "Equivalent" not in text  # COP needs no to_base line


def test_expense_confirmation_usd_shows_to_base():
    acc = Account(name="Amex", type=AccountType.credit, currency="USD", balance=-1200)
    tx = _expense(currency="USD", amount=1200, to_base=4_980_000)
    text = format.expense_confirmation(tx, acc)
    assert "Equivalent: 49800.00 COP" in text


def test_transfer_confirmation_lists_both_balances():
    src = Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=2_000_000)
    dst = Account(name="Ahorros", type=AccountType.savings, currency="COP", balance=8_000_000)
    text = format.transfer_confirmation(src, dst, 5_000_000, "COP")
    assert "Bancolombia" in text and "Ahorros" in text
    assert "20000.00 COP" in text and "80000.00 COP" in text


def test_fx_set_and_current():
    fr = FxRate(date=date(2026, 6, 18), usd_cop=Decimal("4150"))
    assert "2026-06-18" in format.fx_set(fr) and "4150" in format.fx_set(fr)
    assert format.fx_current(Decimal("4150"), date(2026, 6, 18)) == (
        "Current USD→COP rate on 2026-06-18: 4150"
    )


def test_accounts_table_and_empty():
    accs = [Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=10_000_000)]
    table = format.accounts_table(accs)
    assert "Bancolombia" in table and "100000.00" in table and "| Account |" in table
    assert format.accounts_table([]) == "No accounts."


def test_categories_table_resolves_group_name():
    groups = [CategoryGroup(id=1, name="Esenciales")]
    cats = [Category(name="Mercado", group_id=1), Category(name="Sueldo", is_income=True)]
    table = format.categories_table(cats, groups)
    assert "Mercado" in table and "Esenciales" in table
    assert "Sueldo" in table and "yes" in table  # is_income


def test_tags_list():
    assert format.tags_list([Tag(name="viaje"), Tag(name="trabajo")]) == (
        "Tags: viaje, trabajo"
    )
    assert format.tags_list([]) == "No tags."


def test_transactions_table_has_total_and_empty():
    txs = [_expense(), _expense(amount=1_000_000, to_base=1_000_000)]
    table = format.transactions_table(txs)
    assert "| Date |" in table
    assert "Total (COP): 50000.00" in table
    assert "2 transaction(s)" in table
    assert format.transactions_table([]) == "No transactions for those filters."

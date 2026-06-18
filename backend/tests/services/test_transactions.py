from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.errors import MissingRate, NotFound, ValidationError
from quaestor.domain.models import AccountType, TxStatus, TxType
from quaestor.services import accounts, categories, fx, transactions


def _make_account(session, currency="COP", balance=0, type=AccountType.debit):
    return accounts.create_account(session, "Cuenta", type, currency, balance=balance)


def test_record_expense_decrements_balance(session):
    acc = _make_account(session, balance=100_000)
    tx = transactions.record_expense(
        session, acc.id, 45_000, "COP", date(2026, 6, 1), "Éxito"
    )
    assert tx.type == TxType.expense
    assert tx.status == TxStatus.posted
    assert tx.amount == 45_000
    assert tx.to_base == 45_000
    assert tx.fx_rate == Decimal("1")
    assert accounts.get_account(session, acc.id).balance == 55_000


def test_record_income_increments_balance(session):
    acc = _make_account(session, balance=0)
    transactions.record_income(
        session, acc.id, 3_200_000, "COP", date(2026, 6, 1), "Sueldo"
    )
    assert accounts.get_account(session, acc.id).balance == 3_200_000


def test_expense_usd_freezes_to_base(session):
    acc = _make_account(session, currency="USD", balance=0)
    fx.set_fx_rate(session, date(2026, 6, 1), "4150")
    tx = transactions.record_expense(
        session, acc.id, 1200, "USD", date(2026, 6, 1), "Spotify"
    )
    assert tx.fx_rate == Decimal("4150")
    assert tx.to_base == 4_980_000  # congelado
    # cambiar la tasa después no mueve el to_base ya guardado
    fx.set_fx_rate(session, date(2026, 6, 2), "5000")
    assert transactions.get_transaction(session, tx.id).to_base == 4_980_000
    assert accounts.get_account(session, acc.id).balance == -1200  # USD cents


def test_expense_usd_without_rate_fails(session):
    acc = _make_account(session, currency="USD")
    with pytest.raises(MissingRate):
        transactions.record_expense(
            session, acc.id, 1200, "USD", date(2026, 6, 1), "Spotify"
        )


def test_currency_must_match_account(session):
    acc = _make_account(session, currency="COP")
    with pytest.raises(ValidationError):
        transactions.record_expense(
            session, acc.id, 1200, "USD", date(2026, 6, 1), "X", fx_rate=Decimal("4150")
        )


def test_non_positive_amount_fails(session):
    acc = _make_account(session)
    with pytest.raises(ValidationError):
        transactions.record_expense(session, acc.id, 0, "COP", date(2026, 6, 1), "X")


def test_nonexistent_account_fails(session):
    with pytest.raises(NotFound):
        transactions.record_expense(session, 999, 1000, "COP", date(2026, 6, 1), "X")


def test_nonexistent_category_fails(session):
    acc = _make_account(session)
    with pytest.raises(ValidationError):
        transactions.record_expense(
            session, acc.id, 1000, "COP", date(2026, 6, 1), "X", category_id=999
        )


def test_transfer_moves_both_balances_and_shares_group(session):
    origen = accounts.create_account(session, "Débito", AccountType.debit, "COP", balance=1_000_000)
    destino = accounts.create_account(session, "Ahorros", AccountType.savings, "COP", balance=0)
    leg_from, leg_to = transactions.transfer(
        session, origen.id, destino.id, 500_000, "COP", date(2026, 6, 1)
    )
    assert leg_from.type == TxType.transfer and leg_to.type == TxType.transfer
    assert leg_from.transfer_group_id == leg_to.transfer_group_id
    assert accounts.get_account(session, origen.id).balance == 500_000
    assert accounts.get_account(session, destino.id).balance == 500_000


def test_transfer_same_account_fails(session):
    acc = accounts.create_account(session, "A", AccountType.debit, "COP", balance=100)
    with pytest.raises(Exception):  # TransferImbalance
        transactions.transfer(session, acc.id, acc.id, 50, "COP", date(2026, 6, 1))


def test_transfer_nonexistent_destination_is_atomic(session):
    origen = accounts.create_account(session, "Débito", AccountType.debit, "COP", balance=1_000_000)
    with pytest.raises(NotFound):
        transactions.transfer(session, origen.id, 999, 500_000, "COP", date(2026, 6, 1))
    # no rows created, balance intact
    assert accounts.get_account(session, origen.id).balance == 1_000_000
    assert transactions.list_transactions(session) == []


def test_credit_card_payment_is_transfer_not_expense(session):
    debito = accounts.create_account(session, "Débito", AccountType.debit, "COP", balance=1_000_000)
    tarjeta = accounts.create_account(session, "Visa", AccountType.credit, "COP", balance=-300_000)
    transactions.transfer(session, debito.id, tarjeta.id, 300_000, "COP", date(2026, 6, 5))
    assert accounts.get_account(session, tarjeta.id).balance == 0  # debt settled
    gastos = transactions.list_transactions(session, type=TxType.expense)
    assert gastos == []  # the payment is NOT an expense


def test_list_filters_by_account_type_and_range(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    b = accounts.create_account(session, "B", AccountType.debit, "COP", balance=0)
    transactions.record_expense(session, a.id, 1000, "COP", date(2026, 6, 1), "x")
    transactions.record_income(session, a.id, 2000, "COP", date(2026, 6, 15), "y")
    transactions.record_expense(session, b.id, 3000, "COP", date(2026, 7, 1), "z")
    de_a = transactions.list_transactions(session, account_id=a.id)
    assert len(de_a) == 2
    gastos_junio = transactions.list_transactions(
        session, type=TxType.expense, date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)
    )
    assert len(gastos_junio) == 1
    assert gastos_junio[0].account_id == a.id


def test_list_filters_by_tag(session):
    from quaestor.services import tags
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    tx = transactions.record_expense(session, a.id, 1000, "COP", date(2026, 6, 1), "x")
    transactions.record_expense(session, a.id, 2000, "COP", date(2026, 6, 2), "y")
    tags.tag_transaction(session, tx.id, ["viaje"])
    con_tag = transactions.list_transactions(session, tag="viaje")
    assert len(con_tag) == 1 and con_tag[0].id == tx.id


def test_update_transaction_edits_safe_fields(session):
    from datetime import date

    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, categories, transactions

    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    cat = categories.create_category(session, "Comida")
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 17), "Tienda")
    updated = transactions.update_transaction(
        session, tx.id, payee="Supermercado", notes="ofertas", category_id=cat.id
    )
    assert updated.payee == "Supermercado"
    assert updated.notes == "ofertas"
    assert updated.category_id == cat.id
    # balance untouched by an edit
    assert accounts.get_account(session, acc.id).balance == -1000


def test_delete_expense_reverses_balance(session):
    from datetime import date

    from quaestor.domain.errors import NotFound
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, transactions
    import pytest

    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 17), "Tienda")
    assert accounts.get_account(session, acc.id).balance == -1000
    transactions.delete_transaction(session, tx.id)
    assert accounts.get_account(session, acc.id).balance == 0
    with pytest.raises(NotFound):
        transactions.get_transaction(session, tx.id)


def test_delete_transfer_leg_is_rejected(session):
    from datetime import date

    from quaestor.domain.errors import ValidationError
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, transactions
    import pytest

    a = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    b = accounts.create_account(session, "Bank", AccountType.debit, "COP")
    leg_from, _ = transactions.transfer(session, a.id, b.id, 500, "COP", date(2026, 6, 17))
    with pytest.raises(ValidationError):
        transactions.delete_transaction(session, leg_from.id)

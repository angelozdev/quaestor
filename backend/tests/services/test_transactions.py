from datetime import date

import pytest
from quaestor.domain.errors import NotFound, TransferImbalance, ValidationError
from quaestor.domain.models import AccountType, TransferDirection, TxStatus, TxType
from quaestor.domain.money import to_cop_cents
from quaestor.services import accounts, categories, fx, planned, transactions


def _make_account(session, currency="COP", balance=0, type=AccountType.debit):
    return accounts.create_account(session, "Account", type, currency, balance=balance)


def test_record_expense_decrements_balance(session):
    acc = _make_account(session, balance=100_000)
    tx = transactions.record_expense(
        session, acc.id, 45_000, "COP", date(2026, 6, 1), "Store"
    )
    assert tx.type == TxType.expense
    assert tx.status == TxStatus.posted
    assert tx.amount == 45_000
    assert accounts.get_account(session, acc.id).balance == 55_000


def test_record_income_increments_balance(session):
    acc = _make_account(session, balance=0)
    transactions.record_income(
        session, acc.id, 3_200_000, "COP", date(2026, 6, 1), "Salary"
    )
    assert accounts.get_account(session, acc.id).balance == 3_200_000


def test_expense_usd_records_without_any_trm(session):
    acc = _make_account(session, currency="USD", balance=0)
    tx = transactions.record_expense(
        session, acc.id, 1200, "USD", date(2026, 6, 1), "Spotify"
    )
    assert tx.amount == 1200
    assert tx.currency == "USD"
    assert getattr(tx, "fx_rate", None) is None
    assert getattr(tx, "to_base", None) is None
    assert accounts.get_account(session, acc.id).balance == -1200


def test_usd_cop_equivalent_follows_the_current_trm(session):
    acc = _make_account(session, currency="USD", balance=0)
    tx = transactions.record_expense(
        session, acc.id, 1200, "USD", date(2026, 6, 1), "Spotify"
    )
    fx.set_trm(session, "4150")
    stored = transactions.get_transaction(session, tx.id)
    assert to_cop_cents(stored.amount, stored.currency, fx.get_trm(session)) == 4_980_000
    fx.set_trm(session, "5000")
    assert to_cop_cents(stored.amount, stored.currency, fx.get_trm(session)) == 6_000_000


def test_currency_must_match_account(session):
    acc = _make_account(session, currency="COP")
    with pytest.raises(ValidationError):
        transactions.record_expense(
            session, acc.id, 1200, "USD", date(2026, 6, 1), "X"
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
    source = accounts.create_account(session, "Debit", AccountType.debit, "COP", balance=1_000_000)
    destination = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    leg_from, leg_to = transactions.transfer(
        session, source.id, destination.id, 500_000, "COP", date(2026, 6, 1)
    )
    assert leg_from.type == TxType.transfer and leg_to.type == TxType.transfer
    assert leg_from.transfer_group_id == leg_to.transfer_group_id
    assert accounts.get_account(session, source.id).balance == 500_000
    assert accounts.get_account(session, destination.id).balance == 500_000


def test_transfer_same_account_fails(session):
    acc = accounts.create_account(session, "A", AccountType.debit, "COP", balance=100)
    with pytest.raises(TransferImbalance):
        transactions.transfer(session, acc.id, acc.id, 50, "COP", date(2026, 6, 1))


def _cross_currency_pair(session):
    wise = accounts.create_account(session, "Wise", AccountType.debit, "USD", balance=50_000)
    banco = accounts.create_account(
        session, "Bancolombia", AccountType.debit, "COP", balance=100_000_000
    )
    return wise, banco


def test_cross_currency_transfer_moves_each_physical_amount(session):
    wise, banco = _cross_currency_pair(session)
    leg_from, leg_to = transactions.transfer(
        session, wise.id, banco.id, 10_000, "USD", date(2026, 6, 1),
        amount_received=40_000_000,
    )
    assert leg_from.amount == 10_000 and leg_from.currency == "USD"
    assert leg_to.amount == 40_000_000 and leg_to.currency == "COP"
    assert leg_from.transfer_group_id == leg_to.transfer_group_id
    assert accounts.get_account(session, wise.id).balance == 40_000
    assert accounts.get_account(session, banco.id).balance == 140_000_000


def test_cross_currency_transfer_stores_no_rate(session):
    wise, banco = _cross_currency_pair(session)
    legs = transactions.transfer(
        session, wise.id, banco.id, 10_000, "USD", date(2026, 6, 1),
        amount_received=1_000,
    )
    for leg in legs:
        assert getattr(leg, "fx_rate", None) is None
        assert getattr(leg, "to_base", None) is None


def test_cross_currency_transfer_requires_received_amount(session):
    wise, banco = _cross_currency_pair(session)
    with pytest.raises(ValidationError):
        transactions.transfer(session, wise.id, banco.id, 10_000, "USD", date(2026, 6, 1))
    assert accounts.get_account(session, wise.id).balance == 50_000
    assert accounts.get_account(session, banco.id).balance == 100_000_000
    assert transactions.list_transactions(session) == []


def test_transfer_rejects_non_positive_amounts(session):
    wise, banco = _cross_currency_pair(session)
    with pytest.raises(ValidationError):
        transactions.transfer(
            session, wise.id, banco.id, 0, "USD", date(2026, 6, 1),
            amount_received=40_000_000,
        )
    with pytest.raises(ValidationError):
        transactions.transfer(
            session, wise.id, banco.id, 10_000, "USD", date(2026, 6, 1),
            amount_received=-40_000_000,
        )
    assert accounts.get_account(session, wise.id).balance == 50_000
    assert accounts.get_account(session, banco.id).balance == 100_000_000


def test_transfer_currency_defaults_to_source_account(session):
    wise, banco = _cross_currency_pair(session)
    leg_from, _ = transactions.transfer(
        session, wise.id, banco.id, 10_000, None, date(2026, 6, 1),
        amount_received=40_000_000,
    )
    assert leg_from.currency == "USD"


def test_transfer_accepts_one_cent_legs(session):
    wise, banco = _cross_currency_pair(session)
    leg_from, leg_to = transactions.transfer(
        session, wise.id, banco.id, 1, "USD", date(2026, 6, 1),
        amount_received=1,
    )
    assert leg_from.amount == 1 and leg_to.amount == 1
    assert accounts.get_account(session, wise.id).balance == 49_999
    assert accounts.get_account(session, banco.id).balance == 100_000_001


def test_list_filters_by_category(session):
    acc = _make_account(session, balance=100_000)
    cat = categories.create_category(session, "Food")
    transactions.record_expense(session, acc.id, 1_000, "COP", date(2026, 6, 1), "Store")
    tx = transactions.record_expense(
        session, acc.id, 2_000, "COP", date(2026, 6, 2), "Market", category_id=cat.id
    )
    rows = transactions.list_transactions(session, category_id=cat.id)
    assert [r.id for r in rows] == [tx.id]


def test_list_includes_transactions_on_the_date_to_boundary(session):
    acc = _make_account(session, balance=100_000)
    tx = transactions.record_expense(
        session, acc.id, 1_000, "COP", date(2026, 6, 15), "Store"
    )
    rows = transactions.list_transactions(session, date_to=date(2026, 6, 15))
    assert [r.id for r in rows] == [tx.id]


def test_update_transaction_rejects_missing_category(session):
    acc = _make_account(session, balance=100_000)
    tx = transactions.record_expense(
        session, acc.id, 1_000, "COP", date(2026, 6, 1), "Store"
    )
    with pytest.raises(ValidationError):
        transactions.update_transaction(session, tx.id, category_id=9999)


def test_delete_transaction_keeps_other_transactions_tags(session):
    from quaestor.services import tags
    acc = _make_account(session, balance=100_000)
    tx_a = transactions.record_expense(
        session, acc.id, 1_000, "COP", date(2026, 6, 1), "Store"
    )
    tx_b = transactions.record_expense(
        session, acc.id, 2_000, "COP", date(2026, 6, 2), "Market"
    )
    tags.tag_transaction(session, tx_a.id, ["trip"])
    tags.tag_transaction(session, tx_b.id, ["work"])
    transactions.delete_transaction(session, tx_a.id)
    remaining = transactions.list_transactions(session, tag="work")
    assert [r.id for r in remaining] == [tx_b.id]


def test_record_without_a_payee_stores_an_empty_string(session):
    acc = _make_account(session, balance=100_000)
    tx = transactions.record_expense(
        session, acc.id, 1_000, "COP", date(2026, 6, 1), None
    )
    assert tx.payee == ""


def test_transfer_without_notes_is_labelled_transfer(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=100_000)
    b = accounts.create_account(session, "B", AccountType.debit, "COP", balance=0)
    leg_from, leg_to = transactions.transfer(session, a.id, b.id, 1_000, "COP", date(2026, 6, 1))
    assert leg_from.payee == "transfer"
    assert leg_to.payee == "transfer"


def test_transfer_notes_become_the_leg_payee(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=100_000)
    b = accounts.create_account(session, "B", AccountType.debit, "COP", balance=0)
    leg_from, leg_to = transactions.transfer(
        session, a.id, b.id, 1_000, "COP", date(2026, 6, 1), notes="ahorro mensual"
    )
    assert leg_from.payee == "ahorro mensual"
    assert leg_to.payee == "ahorro mensual"


def test_list_filters_to_the_legs_of_one_transfer(session):
    a, _b, (leg_from, leg_to) = _same_currency_transfer(session)
    transactions.record_expense(session, a.id, 1_000, "COP", date(2026, 6, 1), "Store")
    _, _, (other_from, _) = _same_currency_transfer(session)
    rows = transactions.list_transactions(
        session, transfer_group_id=leg_from.transfer_group_id
    )
    assert sorted(r.id for r in rows) == sorted([leg_from.id, leg_to.id])
    assert other_from.id not in [r.id for r in rows]


def test_deleting_an_expense_that_shares_a_transfer_group_spares_the_pair(session):
    a, b, (leg_from, leg_to) = _same_currency_transfer(session)
    intruder = transactions.record_expense(
        session, a.id, 1_000, "COP", date(2026, 6, 1), "Store"
    )
    intruder.transfer_group_id = leg_from.transfer_group_id
    session.add(intruder)
    session.commit()
    transactions.delete_transaction(session, intruder.id)
    assert transactions.get_transaction(session, leg_from.id).id == leg_from.id
    assert transactions.get_transaction(session, leg_to.id).id == leg_to.id
    assert accounts.get_account(session, a.id).balance == 900_000
    assert accounts.get_account(session, b.id).balance == 300_000
    with pytest.raises(NotFound):
        transactions.get_transaction(session, intruder.id)


def test_transfer_currency_must_match_source_account(session):
    wise, banco = _cross_currency_pair(session)
    with pytest.raises(ValidationError):
        transactions.transfer(
            session, wise.id, banco.id, 10_000, "COP", date(2026, 6, 1),
            amount_received=40_000_000,
        )


def test_transfer_nonexistent_destination_is_atomic(session):
    source = accounts.create_account(session, "Debit", AccountType.debit, "COP", balance=1_000_000)
    with pytest.raises(NotFound):
        transactions.transfer(session, source.id, 999, 500_000, "COP", date(2026, 6, 1))
    # no rows created, balance intact
    assert accounts.get_account(session, source.id).balance == 1_000_000
    assert transactions.list_transactions(session) == []


def test_credit_card_payment_is_transfer_not_expense(session):
    debit = accounts.create_account(session, "Debit", AccountType.debit, "COP", balance=1_000_000)
    card = accounts.create_account(session, "Visa", AccountType.credit, "COP", balance=-300_000)
    transactions.transfer(session, debit.id, card.id, 300_000, "COP", date(2026, 6, 5))
    assert accounts.get_account(session, card.id).balance == 0  # debt settled
    expenses = transactions.list_transactions(session, type=TxType.expense)
    assert expenses == []  # the payment is NOT an expense


def test_list_filters_by_account_type_and_range(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    b = accounts.create_account(session, "B", AccountType.debit, "COP", balance=0)
    transactions.record_expense(session, a.id, 1000, "COP", date(2026, 6, 1), "x")
    transactions.record_income(session, a.id, 2000, "COP", date(2026, 6, 15), "y")
    transactions.record_expense(session, b.id, 3000, "COP", date(2026, 7, 1), "z")
    from_a = transactions.list_transactions(session, account_id=a.id)
    assert len(from_a) == 2
    june_expenses = transactions.list_transactions(
        session, type=TxType.expense, date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)
    )
    assert len(june_expenses) == 1
    assert june_expenses[0].account_id == a.id


def test_list_filters_by_tag(session):
    from quaestor.services import tags
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    tx = transactions.record_expense(session, a.id, 1000, "COP", date(2026, 6, 1), "x")
    transactions.record_expense(session, a.id, 2000, "COP", date(2026, 6, 2), "y")
    tags.tag_transaction(session, tx.id, ["trip"])
    tagged = transactions.list_transactions(session, tag="trip")
    assert len(tagged) == 1 and tagged[0].id == tx.id


def test_update_transaction_edits_safe_fields(session):
    from datetime import date

    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, categories, transactions

    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    cat = categories.create_category(session, "Food")
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 17), "Store")
    updated = transactions.update_transaction(
        session, tx.id, payee="Supermarket", notes="deals", category_id=cat.id
    )
    assert updated.payee == "Supermarket"
    assert updated.notes == "deals"
    assert updated.category_id == cat.id
    # balance untouched by an edit
    assert accounts.get_account(session, acc.id).balance == -1000


def test_delete_expense_reverses_balance(session):
    from datetime import date

    import pytest
    from quaestor.domain.errors import NotFound
    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, transactions

    acc = accounts.create_account(session, "Cash", AccountType.cash, "COP")
    tx = transactions.record_expense(session, acc.id, 1000, "COP", date(2026, 6, 17), "Store")
    assert accounts.get_account(session, acc.id).balance == -1000
    transactions.delete_transaction(session, tx.id)
    assert accounts.get_account(session, acc.id).balance == 0
    with pytest.raises(NotFound):
        transactions.get_transaction(session, tx.id)


def test_transfer_sets_direction_on_each_leg(session):
    a = accounts.create_account(session, "Cash", AccountType.cash, "COP", balance=1_000)
    b = accounts.create_account(session, "Bank", AccountType.debit, "COP")
    leg_from, leg_to = transactions.transfer(session, a.id, b.id, 500, "COP", date(2026, 6, 17))
    assert leg_from.transfer_direction == TransferDirection.out
    assert leg_to.transfer_direction == TransferDirection.in_


def test_expense_and_income_carry_no_transfer_direction(session):
    acc = _make_account(session, balance=10_000)
    expense = transactions.record_expense(session, acc.id, 1_000, "COP", date(2026, 6, 1), "X")
    income = transactions.record_income(session, acc.id, 2_000, "COP", date(2026, 6, 1), "Y")
    assert expense.transfer_direction is None
    assert income.transfer_direction is None


def _same_currency_transfer(session):
    a = accounts.create_account(session, "Cash", AccountType.cash, "COP", balance=1_000_000)
    b = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=200_000)
    legs = transactions.transfer(session, a.id, b.id, 100_000, "COP", date(2026, 6, 17))
    return a, b, legs


def test_delete_outgoing_leg_deletes_pair_and_restores_balances(session):
    a, b, (leg_from, leg_to) = _same_currency_transfer(session)
    transactions.delete_transaction(session, leg_from.id)
    assert accounts.get_account(session, a.id).balance == 1_000_000
    assert accounts.get_account(session, b.id).balance == 200_000
    with pytest.raises(NotFound):
        transactions.get_transaction(session, leg_from.id)
    with pytest.raises(NotFound):
        transactions.get_transaction(session, leg_to.id)


def test_delete_receiving_leg_deletes_pair_and_restores_balances(session):
    a, b, (leg_from, leg_to) = _same_currency_transfer(session)
    transactions.delete_transaction(session, leg_to.id)
    assert accounts.get_account(session, a.id).balance == 1_000_000
    assert accounts.get_account(session, b.id).balance == 200_000
    with pytest.raises(NotFound):
        transactions.get_transaction(session, leg_from.id)
    with pytest.raises(NotFound):
        transactions.get_transaction(session, leg_to.id)


def test_delete_cross_currency_pair_restores_each_physical_amount(session):
    wise, banco = _cross_currency_pair(session)
    leg_from, _ = transactions.transfer(
        session, wise.id, banco.id, 10_000, "USD", date(2026, 6, 1),
        amount_received=40_000_000,
    )
    transactions.delete_transaction(session, leg_from.id)
    assert accounts.get_account(session, wise.id).balance == 50_000
    assert accounts.get_account(session, banco.id).balance == 100_000_000


def test_delete_transfer_pair_removes_only_its_tag_links(session):
    from quaestor.services import tags

    a, _b, (leg_from, leg_to) = _same_currency_transfer(session)
    other = transactions.record_expense(
        session, a.id, 1_000, "COP", date(2026, 6, 1), "Store"
    )
    tags.tag_transaction(session, leg_from.id, ["viaje"])
    tags.tag_transaction(session, leg_to.id, ["viaje"])
    tags.tag_transaction(session, other.id, ["viaje"])
    transactions.delete_transaction(session, leg_from.id)
    from quaestor.domain.models import TransactionTag
    from sqlmodel import select

    remaining = session.exec(select(TransactionTag)).all()
    assert [link.transaction_id for link in remaining] == [other.id]


def _group_less_transfer(session, status):
    from quaestor.domain.models import Transaction

    acc = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=500_000)
    tx = Transaction(
        date=date(2026, 6, 30), payee="Goal: Korea", type=TxType.transfer,
        status=status, amount=300_000, currency="COP", account_id=acc.id,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return acc, tx


@pytest.mark.parametrize("status", [TxStatus.planned, TxStatus.skipped])
def test_delete_group_less_transfer_removes_the_row_and_keeps_the_balance(session, status):
    acc, tx = _group_less_transfer(session, status)
    transactions.delete_transaction(session, tx.id)
    assert accounts.get_account(session, acc.id).balance == 500_000
    with pytest.raises(NotFound):
        transactions.get_transaction(session, tx.id)


def test_delete_group_less_transfer_removes_its_tag_links(session):
    from quaestor.domain.models import TransactionTag
    from quaestor.services import tags
    from sqlmodel import select

    acc, tx = _group_less_transfer(session, TxStatus.planned)
    other = transactions.record_expense(session, acc.id, 1_000, "COP", date(2026, 6, 1), "Store")
    tags.tag_transaction(session, tx.id, ["ahorro"])
    tags.tag_transaction(session, other.id, ["ahorro"])
    transactions.delete_transaction(session, tx.id)
    remaining = session.exec(select(TransactionTag)).all()
    assert [link.transaction_id for link in remaining] == [other.id]


def test_delete_grouped_transfer_without_direction_still_fails_loud(session):
    from quaestor.domain.models import Transaction

    a = accounts.create_account(session, "Cash", AccountType.cash, "COP", balance=1_000_000)
    b = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=200_000)
    legs = [
        Transaction(
            date=date(2026, 6, 17), payee="transfer", type=TxType.transfer,
            status=TxStatus.posted, amount=100_000, currency="COP",
            account_id=account.id, transfer_group_id="orphaned",
        )
        for account in (a, b)
    ]
    session.add_all(legs)
    session.commit()
    with pytest.raises(ValidationError):
        transactions.delete_transaction(session, legs[0].id)
    assert accounts.get_account(session, a.id).balance == 1_000_000
    assert accounts.get_account(session, b.id).balance == 200_000


def test_delete_transfer_pair_is_atomic_on_failure(session, monkeypatch):
    a, b, (leg_from, leg_to) = _same_currency_transfer(session)

    def boom():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(session, "commit", boom)
    with pytest.raises(RuntimeError):
        transactions.delete_transaction(session, leg_from.id)
    monkeypatch.undo()
    assert accounts.get_account(session, a.id).balance == 900_000
    assert accounts.get_account(session, b.id).balance == 300_000
    survivors = [
        transactions.get_transaction(session, leg_from.id),
        transactions.get_transaction(session, leg_to.id),
    ]
    assert {tx.transfer_group_id for tx in survivors} == {leg_from.transfer_group_id}


# --- sort / order behaviour (ADR-0021) ---


def test_list_transactions_default_orders_by_date_desc(session):
    """Default: newest logical-date first, regardless of creation order."""
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    # Insert in misleading order: mid (oldest created) first.
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 15), "mid")
    transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    txs = transactions.list_transactions(session)
    # Date desc: new (1-jul) > mid (15-jun) > old (1-jun).
    assert [t.payee for t in txs] == ["new", "mid", "old"]


def test_list_transactions_sort_date_asc_orders_chronologically(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 15), "mid")
    transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    txs = transactions.list_transactions(session, sort="date", order="asc")
    assert [t.payee for t in txs] == ["old", "mid", "new"]


def test_list_transactions_sort_date_desc_orders_reverse_chronologically(session):
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 15), "mid")
    transactions.record_expense(session, a.id, 200, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    txs = transactions.list_transactions(session, sort="date", order="desc")
    assert [t.payee for t in txs] == ["new", "mid", "old"]


def test_list_transactions_default_includes_planned_at_due_date(session):
    """No status filter = both posted and planned, in date-DESC order.

    Planned tx with due-date 15-jun surfaces between a 1-jun posted and a
    1-jul posted — proves both (a) the default includes planned and
    (b) the sort respects the planned tx's logical date.
    """
    a = accounts.create_account(session, "A", AccountType.debit, "COP", balance=1_000_000)
    transactions.record_expense(session, a.id, 100, "COP", date(2026, 6, 1), "old")
    transactions.record_expense(session, a.id, 300, "COP", date(2026, 7, 1), "new")
    planned.plan_payment(session, "Rent", 500_000, "COP", due_date=date(2026, 6, 15), account_id=a.id)
    txs = transactions.list_transactions(session)
    assert [t.payee for t in txs] == ["new", "Rent", "old"]

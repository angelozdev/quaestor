"""Step handlers — feature 012 movement-corrections.

Bound to the services layer (``quaestor.services.transactions``), where a
correction reverses a movement's balance effect and applies it again to the
same row (ADR-0051).

The subject of a correction — *that expense*, *that income*, *that charge* — is
the most recent movement of that kind in the scenario, resolved by query rather
than by a shared counter, so this module keeps no state in ``World`` and no
other feature's bookkeeping has to know about it.

Three steps make a balance misbehave on purpose. They exist for AC-23, whose
whole subject is what happens when the arithmetic does not prove out, and they
tamper through a session event rather than through the service — a check that
could only be exercised by the code it checks would prove nothing.
"""

from __future__ import annotations

from quaestor.domain.errors import (
    CorrectionNotApplied,
    NotFound,
    TransferImbalance,
    ValidationError,
)
from quaestor.domain.models import Account, OccurrenceStatus, RecurringItem, Transaction, TxStatus, TxType
from quaestor.domain.money import major_to_cents
from quaestor.services import accounts, occurrences, planned, transactions
from sqlalchemy import event
from sqlmodel import select

from . import step
from .fx_read_time import _DEC
from .world import MISSING_ID, World

_SIGNED = r"-?\d+(?:\.\d+)?"
_KIND = r"expense|income|charge|movement"
_TYPE_OF = {"expense": TxType.expense, "income": TxType.income, "charge": TxType.expense, "movement": None}


def _waiting_payment(world: World, payee: str | None = None) -> Transaction:
    """The payment still waiting to be confirmed — by payee when one is named."""
    stmt = select(Transaction).where(Transaction.status == TxStatus.planned)
    if payee is not None:
        stmt = stmt.where(Transaction.payee == payee)
    rows = world.session.exec(stmt.order_by(Transaction.id)).all()
    if not rows:
        named = f" to {payee!r}" if payee else ""
        raise AssertionError(f"no payment{named} is waiting in this scenario")
    return rows[0]


def _subject(world: World, kind: str) -> Transaction:
    """The most recent movement of this kind — what *that expense* refers to."""
    stmt = select(Transaction).order_by(Transaction.id.desc())
    wanted = _TYPE_OF[kind]
    if wanted is not None:
        stmt = stmt.where(Transaction.type == wanted)
    rows = world.session.exec(stmt).all()
    if not rows:
        raise AssertionError(f"no {kind} was recorded earlier in the scenario")
    return rows[0]


def _leg(world: World, side: str) -> Transaction:
    rows = world.session.exec(select(Transaction).where(Transaction.type == TxType.transfer)).all()
    wanted = "out" if side == "sending" else "in"
    for row in rows:
        if row.transfer_direction is not None and row.transfer_direction.value.rstrip("_") == wanted:
            return row
    raise AssertionError(f"no {side} side of a transfer was recorded earlier in the scenario")


def _tamper(world: World, name: str, adjust) -> None:
    account_id = world.accounts[name]
    original = accounts.get_account(world.session, account_id).balance

    def before_flush(session, flush_context, instances) -> None:
        for obj in session.dirty:
            if isinstance(obj, Account) and obj.id == account_id:
                obj.balance = adjust(original, obj.balance)

    event.listen(world.session, "before_flush", before_flush)
    world.cleanups.append(lambda: event.remove(world.session, "before_flush", before_flush))


@step(r'the balance of "(?P<name>[^"]+)" refuses to move')
def given_balance_refuses(world: World, name: str) -> None:
    _tamper(world, name, lambda original, _current: original)


@step(r'the balance of "(?P<name>[^"]+)" moves by more than it is told to')
def given_balance_overshoots(world: World, name: str) -> None:
    _tamper(world, name, lambda _original, current: current + 1)


@step(r'"(?P<name>[^"]+)" was adjusted by hand to (?P<amount>' + _DEC + r") (?P<currency>[A-Z]{3})")
def given_balance_adjusted_by_hand(world: World, name: str, amount: str, currency: str) -> None:
    account = accounts.get_account(world.session, world.accounts[name])
    account.balance = major_to_cents(amount)
    world.session.add(account)
    world.session.commit()


@step(
    r"the user (?:moves|tries to move) that (?P<kind>" + _KIND + r') to "(?P<account>[^"]+)"'
    r"(?: for (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}))?"
)
def when_move_movement(world: World, kind: str, account: str, amount: str | None, currency: str | None) -> None:
    tx = _subject(world, kind)
    world.attempt(
        transactions.move_to_account,
        world.session,
        tx.id,
        account_id=world.account_id_or_missing(account),
        amount=major_to_cents(amount) if amount else None,
    )


@step(r"the user tries to move that expense to an account that does not exist")
def when_move_to_missing_account(world: World) -> None:
    tx = _subject(world, "expense")
    world.attempt(transactions.move_to_account, world.session, tx.id, account_id=MISSING_ID)


@step(
    r"the user (?:moves|tries to move) the (?P<side>sending|receiving) side of the transfer"
    r' to "(?P<account>[^"]+)"(?: for (?P<amount>' + _DEC + r") (?P<currency>[A-Z]{3}))?"
)
def when_move_transfer_side(world: World, side: str, account: str, amount: str | None, currency: str | None) -> None:
    leg = _leg(world, side)
    world.attempt(
        transactions.move_to_account,
        world.session,
        leg.id,
        account_id=world.account_id_or_missing(account),
        amount=major_to_cents(amount) if amount else None,
    )


@step(
    r"the user (?:corrects|tries to correct) that (?P<kind>" + _KIND + r")"
    r" to (?P<amount>" + _SIGNED + r") (?P<currency>[A-Z]{3})"
)
def when_correct_amount(world: World, kind: str, amount: str, currency: str) -> None:
    tx = _subject(world, kind)
    world.attempt(transactions.correct_amount, world.session, tx.id, amount=major_to_cents(amount))


@step(
    r'the user (?:confirms|tries to confirm) the payment to "(?P<payee>[^"]+)" from "(?P<account>[^"]+)"'
    r"(?: for (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}))?"
)
def when_confirm_from_account(world: World, payee: str, account: str, amount: str | None, currency: str | None) -> None:
    tx = _waiting_payment(world, payee)
    world.attempt(
        planned.confirm_payment,
        world.session,
        tx.id,
        amount=major_to_cents(amount) if amount else None,
        account_id=world.account_id_or_missing(account),
    )


@step(r'the user moves the payment still waiting to "(?P<account>[^"]+)"')
def when_move_waiting_payment(world: World, account: str) -> None:
    tx = _waiting_payment(world)
    world.attempt(
        transactions.move_to_account,
        world.session,
        tx.id,
        account_id=world.account_id_or_missing(account),
    )


@step(r'the payment still waiting to "(?P<payee>[^"]+)" is against "(?P<account>[^"]+)"')
def then_waiting_payment_account(world: World, payee: str, account: str) -> None:
    world.require_clean(f"reading which account the payment to {payee!r} is against")
    tx = _waiting_payment(world, payee)
    expected = world.accounts[account]
    assert tx.account_id == expected, f"expected account {expected}, got {tx.account_id}"


@step(r'"(?P<name>[^"]+)" is still declared against "(?P<account>[^"]+)"')
def then_obligation_account_unchanged(world: World, name: str, account: str) -> None:
    world.require_clean(f"reading the account {name!r} is declared against")
    item = world.session.exec(select(RecurringItem).where(RecurringItem.payee == name)).first()
    assert item is not None, f"no repeating obligation to {name!r} exists in this scenario"
    expected = world.accounts[account]
    assert item.account_id == expected, f"expected account {expected}, got {item.account_id}"


@step(r"that (?P<kind>" + _KIND + r') came out of "(?P<account>[^"]+)"')
def then_movement_account(world: World, kind: str, account: str) -> None:
    world.require_clean(f"reading which account that {kind} came out of")
    tx = _subject(world, kind)
    expected = world.accounts[account]
    assert tx.account_id == expected, f"expected account {expected}, got {tx.account_id}"


@step(r"that (?P<kind>" + _KIND + r") is for (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})")
def then_movement_amount(world: World, kind: str, amount: str, currency: str) -> None:
    world.require_clean(f"reading what that {kind} is worth")
    tx = _subject(world, kind)
    expected = major_to_cents(amount)
    assert tx.amount == expected, f"expected {expected}, got {tx.amount}"
    assert tx.currency == currency, f"expected {currency}, got {tx.currency}"


@step(r"that expense is still the same movement")
def then_same_movement(world: World) -> None:
    world.require_clean("checking the movement survived its correction")
    tx = _subject(world, "expense")
    assert world.expense_ids, "no expense was recorded earlier in the scenario"
    assert tx.id == world.expense_ids[-1], (
        f"the movement was replaced: recorded as {world.expense_ids[-1]}, now {tx.id}"
    )


@step(r'that expense is still in category "(?P<name>[^"]+)"')
def then_still_in_category(world: World, name: str) -> None:
    world.require_clean("reading the category of that expense")
    tx = _subject(world, "expense")
    expected = world.categories[name]
    assert tx.category_id == expected, f"expected category {expected}, got {tx.category_id}"


@step(r"that transfer carries no category")
def then_transfer_has_no_category(world: World) -> None:
    world.require_clean("reading the category of that transfer")
    legs = world.session.exec(select(Transaction).where(Transaction.type == TxType.transfer)).all()
    assert legs, "no transfer was recorded earlier in the scenario"
    for leg in legs:
        assert leg.category_id is None, f"transfer leg {leg.id} carries category {leg.category_id}"


@step(r'the due date behind "(?P<payee>[^"]+)" is still charged')
def then_due_date_still_charged(world: World, payee: str) -> None:
    """Deleting an engine-made charge settles its date as skipped and unlinks it
    (ADR-0038). Correcting keeps the row, so neither may happen."""
    world.require_clean(f"reading the due date behind {payee!r}")
    charge = _subject(world, "charge")
    occurrence = occurrences.occurrence_of(world.session, charge)
    assert occurrence is not None, f"the charge to {payee!r} hangs off no due date"
    assert occurrence.status == OccurrenceStatus.posted, (
        f"the due date behind {payee!r} reads {occurrence.status.value}, not charged"
    )
    assert occurrence.transaction_id == charge.id, (
        f"the due date behind {payee!r} points at {occurrence.transaction_id}, not {charge.id}"
    )


@step(r"the correction is rejected")
def then_correction_rejected(world: World) -> None:
    world.consume_rejection(
        (ValidationError, TransferImbalance, CorrectionNotApplied, NotFound), "correcting the movement"
    )


@step(r"the user is told the correction did not go through")
def then_told_not_applied(world: World) -> None:
    err = world.last_error
    assert isinstance(err, CorrectionNotApplied), f"expected CorrectionNotApplied, got {err!r}"


@step(r"the user is told a retired account takes nothing new")
def then_told_archived(world: World) -> None:
    err = world.last_error
    assert isinstance(err, ValidationError), f"expected ValidationError, got {err!r}"
    assert "archived" in str(err), f"the refusal does not mention the account being archived: {err}"


@step(r"the user is told the two sides of a transfer cannot be the same account")
def then_told_same_account(world: World) -> None:
    err = world.last_error
    assert isinstance(err, TransferImbalance), f"expected TransferImbalance, got {err!r}"

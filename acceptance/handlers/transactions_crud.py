"""Step handlers — feature 002 transactions-crud.

Bound to the services layer (``quaestor.services.transactions/tags/planned/
categories/accounts``); the AC-15 assistant steps go through the MCP tools
layer and the AC-15/AC-16 app steps through the FastAPI TestClient (reusing
005's ``_rest_client``).

The two red-phase intended bindings are now implemented and bound to the
real API (never faked, never skipped):

- Transfer-pair deletion (AC-5): ``transactions.delete_transaction`` on a
  leg deletes the pair per stored direction (ADR-0032).
- Per-transaction tag removal (AC-6/AC-15): ``tags.untag_transaction`` and
  the MCP ``update_transaction`` tool's ``remove_tags``.

Ordering/filter list steps ("the list shows ...") bind to the services list
contract, which is TRM-independent; the read-time COP surface contract
("the user views the transaction list" / "the list is not shown") fetches
the TRM first and fails loud, mirroring the REST list endpoint (AC-9).
"""
from __future__ import annotations

import re as _re
from datetime import date as Date

from sqlmodel import select

from quaestor.domain import money as money_mod
from quaestor.domain.errors import MissingRate, NotFound, QuaestorError
from quaestor.domain.models import Source, Transaction, TxType
from quaestor.domain.money import major_to_cents
from quaestor.services import (
    accounts,
    categories,
    fx,
    planned,
    reports,
    tags,
    transactions,
)

from . import step
from .fx_read_time import _DEC, _default_account_id, _month_str, _rest_client
from .world import MISSING_ID, World

_DATE = r"\d{4}-\d{2}-\d{2}"


def _scenario_account_id(world: World, currency: str) -> int:
    for acc_id in world.accounts.values():
        if accounts.get_account(world.session, acc_id).currency == currency:
            return acc_id
    return _default_account_id(world, currency)


def _last_expense(world: World) -> Transaction:
    if world.last_expense_id is None:
        raise AssertionError("no expense was recorded earlier in the scenario")
    return transactions.get_transaction(world.session, world.last_expense_id)


def _transfer_leg(world: World, index: int) -> Transaction:
    if world.transfer_legs is None:
        raise AssertionError("no transfer was recorded earlier in the scenario")
    return world.transfer_legs[index]


def _tag_names(world: World, tx_id: int) -> list[str]:
    return tags.tag_names_by_transaction(world.session, [tx_id])[tx_id]


@step(r'a category "(?P<name>[^"]+)"')
def given_category(world: World, name: str) -> None:
    cat = categories.create_category(world.session, name)
    world.categories[name] = cat.id


@step(r'an archived category "(?P<name>[^"]+)"')
def given_archived_category(world: World, name: str) -> None:
    cat = categories.create_category(world.session, name)
    categories.archive_category(world.session, cat.id)
    world.categories[name] = cat.id


@step(r'an archived account "(?P<name>[^"]+)" in (?P<currency>[A-Z]{3})')
def given_archived_account(world: World, name: str, currency: str) -> None:
    acc = accounts.create_account(world.session, name, "debit", currency, balance=0)
    accounts.archive_account(world.session, acc.id)
    world.accounts[name] = acc.id


@step(
    r"a recorded expense of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' tagged "(?P<tag>[^"]+)"'
)
def given_recorded_tagged_expense(
    world: World, amount: str, currency: str, tag: str
) -> None:
    payee = f"Payee {len(world.expense_ids) + 1}"
    tx = transactions.record_expense(
        world.session,
        _scenario_account_id(world, currency),
        major_to_cents(amount),
        currency,
        world.today,
        payee,
    )
    tags.tag_transaction(world.session, tx.id, [tag])
    world.last_expense_id = tx.id
    world.expense_ids.append(tx.id)


@step(
    r"a planned payment of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
    r' to "(?P<payee>[^"]+)" due (?P<due>' + _DATE + r")"
)
def given_planned_payment(
    world: World, amount: str, currency: str, payee: str, due: str
) -> None:
    planned.plan_payment(
        world.session,
        payee,
        major_to_cents(amount),
        currency,
        Date.fromisoformat(due),
        _scenario_account_id(world, currency),
    )


@step(r"the user has no session")
def given_no_session(world: World) -> None:
    pass


@step(
    r"the user registers an expense of (?P<amount>" + _DEC + r") "
    r'(?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)" paying "(?P<payee>[^"]+)"'
    r'(?: in category "(?P<category>[^"]+)")?'
    r"(?: dated (?P<date>" + _DATE + r"))?"
    r'(?: with notes "(?P<notes>[^"]+)")?'
    r'(?: tagged "(?P<tag1>[^"]+)"(?: and "(?P<tag2>[^"]+)")?)?'
)
def when_register_expense_detailed(
    world: World,
    amount: str,
    currency: str,
    account: str,
    payee: str,
    category: str | None,
    date: str | None,
    notes: str | None,
    tag1: str | None,
    tag2: str | None,
) -> None:
    def action():
        tx = transactions.record_expense(
            world.session,
            world.accounts[account],
            major_to_cents(amount),
            currency,
            Date.fromisoformat(date) if date else world.today,
            payee,
            category_id=world.categories[category] if category else None,
            notes=notes,
        )
        world.last_expense_id = tx.id
        world.expense_ids.append(tx.id)
        names = [t for t in (tag1, tag2) if t]
        if names:
            tags.tag_transaction(world.session, tx.id, names)

    world.attempt(action)


@step(
    r"the user registers an income of (?P<amount>" + _DEC + r") "
    r'(?P<currency>[A-Z]{3}) into "(?P<account>[^"]+)" from "(?P<payee>[^"]+)"'
)
def when_register_income(
    world: World, amount: str, currency: str, account: str, payee: str
) -> None:
    world.attempt(
        transactions.record_income,
        world.session,
        world.accounts[account],
        major_to_cents(amount),
        currency,
        world.today,
        payee,
    )


@step(
    r'the user edits the expense changing payee to "(?P<payee>[^"]+)", '
    r'category to "(?P<category>[^"]+)", date to (?P<date>' + _DATE + r") "
    r'and notes to "(?P<notes>[^"]+)"'
)
def when_edit_expense(
    world: World, payee: str, category: str, date: str, notes: str
) -> None:
    def action():
        transactions.update_transaction(
            world.session,
            _last_expense(world).id,
            payee=payee,
            notes=notes,
            category_id=world.categories[category],
            date=Date.fromisoformat(date),
        )

    world.attempt(action)


@step(r"the user clears the expense's category")
def when_clear_category(world: World) -> None:
    def action():
        transactions.update_transaction(
            world.session, _last_expense(world).id, category_id=None
        )

    world.attempt(action)


@step(r"the user deletes the expense")
def when_delete_expense(world: World) -> None:
    def action():
        transactions.delete_transaction(world.session, _last_expense(world).id)

    world.attempt(action)


@step(r"the user deletes the first expense")
def when_delete_first_expense(world: World) -> None:
    def action():
        transactions.delete_transaction(world.session, world.expense_ids[0])

    world.attempt(action)


@step(r"the user deletes the transfer")
def when_delete_transfer(world: World) -> None:
    def action():
        transactions.delete_transaction(world.session, _transfer_leg(world, 0).id)

    world.attempt(action)


@step(r"the user deletes the receiving side of the transfer")
def when_delete_receiving_side(world: World) -> None:
    def action():
        transactions.delete_transaction(world.session, _transfer_leg(world, 1).id)

    world.attempt(action)


@step(r'the user adds the tag "(?P<name>[^"]+)" to the expense')
def when_add_tag(world: World, name: str) -> None:
    def action():
        tags.tag_transaction(world.session, _last_expense(world).id, [name])

    world.attempt(action)


@step(r'the user removes the tag "(?P<name>[^"]+)" from the expense')
def when_remove_tag(world: World, name: str) -> None:
    def action():
        tags.untag_transaction(world.session, _last_expense(world).id, [name])

    world.attempt(action)


@step(r'the assistant removes the tag "(?P<name>[^"]+)" from the expense')
def when_assistant_removes_tag(world: World, name: str) -> None:
    def action():
        from quaestor.mcp.tools import transactions as mcp_transactions

        mcp_transactions.update_transaction(
            world.session,
            mcp_transactions.UpdateTransactionInput(
                tx_id=_last_expense(world).id, remove_tags=[name]
            ),
        )

    world.attempt(action)


@step(
    r"the user transfers (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3}) "
    r'from "(?P<src>[^"]+)" to "(?P<dst>[^"]+)" dated (?P<date>' + _DATE + r")"
)
def when_transfer_dated(
    world: World, amount: str, currency: str, src: str, dst: str, date: str
) -> None:
    def action():
        world.transfer_legs = transactions.transfer(
            world.session,
            world.account_id_or_missing(src),
            world.account_id_or_missing(dst),
            major_to_cents(amount),
            currency,
            Date.fromisoformat(date),
        )

    world.attempt(action)


@step(r"the user changes the date of the sending side to (?P<date>" + _DATE + r")")
def when_change_sending_side_date(world: World, date: str) -> None:
    def action():
        transactions.update_transaction(
            world.session, _transfer_leg(world, 0).id, date=Date.fromisoformat(date)
        )

    world.attempt(action)


@step(r"the user views the sending side of the transfer")
def when_view_sending_side(world: World) -> None:
    def action():
        world.viewed_leg = transactions.get_transaction(
            world.session, _transfer_leg(world, 0).id
        )

    world.attempt(action)


@step(r"the user views the transaction list")
def when_view_transaction_list(world: World) -> None:
    """The read-time COP list surface: the TRM is read first and missing-TRM
    fails loud (AC-9), mirroring GET /api/transactions."""
    world.tx_view = None

    def action():
        trm = fx.get_trm(world.session)
        rows = transactions.list_transactions(world.session)
        world.tx_view = [
            (tx, money_mod.to_cop_cents(tx.amount, tx.currency, trm)) for tx in rows
        ]

    world.attempt(action)


@step(
    r'the user lists transactions in category "(?P<category>[^"]+)" '
    r"between (?P<start>" + _DATE + r") and (?P<end>" + _DATE + r")"
)
def when_list_by_category_and_dates(
    world: World, category: str, start: str, end: str
) -> None:
    world.filtered_rows = None

    def action():
        world.filtered_rows = transactions.list_transactions(
            world.session,
            category_id=world.categories[category],
            date_from=Date.fromisoformat(start),
            date_to=Date.fromisoformat(end),
        )

    world.attempt(action)


@step(
    r"the user lists transactions between (?P<start>" + _DATE + r") "
    r"and (?P<end>" + _DATE + r")"
)
def when_list_by_dates(world: World, start: str, end: str) -> None:
    world.filtered_rows = None

    def action():
        world.filtered_rows = transactions.list_transactions(
            world.session,
            date_from=Date.fromisoformat(start),
            date_to=Date.fromisoformat(end),
        )

    world.attempt(action)


@step(r"the user tries to (?P<action>view|edit|delete) a transaction that does not exist")
def when_act_on_missing_transaction(world: World, action: str) -> None:
    operations = {
        "view": lambda: transactions.get_transaction(world.session, MISSING_ID),
        "edit": lambda: transactions.update_transaction(
            world.session, MISSING_ID, payee="Nadie"
        ),
        "delete": lambda: transactions.delete_transaction(
            world.session, MISSING_ID
        ),
    }
    world.attempt(operations[action])


@step(
    r"the assistant records an expense of (?P<amount>" + _DEC + r") "
    r'(?P<currency>[A-Z]{3}) from "(?P<account>[^"]+)" paying "(?P<payee>[^"]+)" '
    r'tagged "(?P<tag>[^"]+)"'
)
def when_assistant_records_expense(
    world: World, amount: str, currency: str, account: str, payee: str, tag: str
) -> None:
    def action():
        from quaestor.mcp.tools import core as mcp_core

        reply = mcp_core.record_expense(
            world.session,
            mcp_core.RecordExpenseInput(
                payee=payee,
                amount=major_to_cents(amount),
                account=account,
                currency=currency,
                tags=[tag],
                date=world.today,
            ),
        )
        recorded = [
            t
            for t in transactions.list_transactions(world.session)
            if t.payee == payee and t.type == TxType.expense
        ]
        if not recorded:
            raise AssertionError(f"the assistant did not record the expense: {reply}")
        tx = max(recorded, key=lambda t: t.id)
        world.last_expense_id = tx.id
        world.expense_ids.append(tx.id)

    world.attempt(action)


@step(r'the user lists transactions tagged "(?P<tag>[^"]+)" in the app')
def when_app_lists_tagged(world: World, tag: str) -> None:
    def action():
        client, auth = _rest_client(world)
        resp = client.get("/api/transactions", params={"tag": tag}, headers=auth)
        if resp.status_code != 200:
            raise AssertionError(
                f"GET /api/transactions?tag={tag} -> {resp.status_code}: {resp.text}"
            )
        world.app_payees = sorted(row["payee"] for row in resp.json())

    world.attempt(action)


_MCP_TABLE_ROW = _re.compile(r"^\| (?P<date>[^|]+) \| (?P<type>[^|]+) \| (?P<payee>[^|]+) \| ")


@step(r'the assistant lists transactions tagged "(?P<tag>[^"]+)"')
def when_assistant_lists_tagged(world: World, tag: str) -> None:
    def action():
        from quaestor.mcp.tools import core as mcp_core

        text = mcp_core.list_transactions(
            world.session, mcp_core.ListTransactionsInput(tag=tag)
        )
        matches = [
            m
            for m in (_MCP_TABLE_ROW.match(line) for line in text.splitlines())
            if m is not None
        ]
        world.assistant_payees = sorted(
            m.group("payee").strip()
            for m in matches
            if m.group("type").strip() != "Type"
        )

    world.attempt(action)


@step(r"they request the transaction list")
def when_request_list_without_session(world: World) -> None:
    def action():
        client, _ = _rest_client(world)
        world.denied_status = client.get("/api/transactions").status_code

    world.attempt(action)


@step(
    r'viewing the expense shows payee "(?P<payee>[^"]+)", category '
    r'"(?P<category>[^"]+)", date (?P<date>' + _DATE + r") "
    r'and notes "(?P<notes>[^"]+)"'
)
def then_expense_details(
    world: World, payee: str, category: str, date: str, notes: str
) -> None:
    world.require_clean("the registration or edit should have succeeded")
    tx = _last_expense(world)
    assert tx.payee == payee, f"expected payee {payee!r}, got {tx.payee!r}"
    expected_category = world.categories[category]
    assert tx.category_id == expected_category, (
        f"expected category {category!r} (id {expected_category}), "
        f"got category_id={tx.category_id}"
    )
    expected_date = Date.fromisoformat(date)
    assert tx.date == expected_date, f"expected date {expected_date}, got {tx.date}"
    assert tx.notes == notes, f"expected notes {notes!r}, got {tx.notes!r}"


@step(r"viewing the expense shows no category")
def then_expense_no_category(world: World) -> None:
    world.require_clean("clearing the category should have succeeded")
    tx = _last_expense(world)
    assert tx.category_id is None, (
        f"expected no category, got category_id={tx.category_id}"
    )


@step(r"the transfer is recorded as two movements linked as one transfer")
def then_transfer_pair_recorded(world: World) -> None:
    world.require_clean("the transfer should have succeeded")
    assert world.transfer_legs is not None, "no transfer was recorded"
    leg_from, leg_to = world.transfer_legs
    assert leg_from.id != leg_to.id, "the transfer produced a single movement"
    for leg in (leg_from, leg_to):
        assert leg.type == TxType.transfer, (
            f"leg {leg.id} has type {leg.type}, expected transfer"
        )
    assert leg_from.transfer_group_id, "the legs carry no transfer group id"
    assert leg_from.transfer_group_id == leg_to.transfer_group_id, (
        "the two movements are not linked as one transfer "
        f"({leg_from.transfer_group_id} != {leg_to.transfer_group_id})"
    )


@step(r'the list shows "(?P<upper>[^"]+)" above "(?P<lower>[^"]+)"')
def then_list_order(world: World, upper: str, lower: str) -> None:
    """Combined read+assert on the services list contract: ordering is
    date-desc and TRM-independent (AC-7)."""
    payees = [tx.payee for tx in transactions.list_transactions(world.session)]
    assert upper in payees, f"{upper!r} is not in the list: {payees}"
    assert lower in payees, f"{lower!r} is not in the list: {payees}"
    assert payees.index(upper) < payees.index(lower), (
        f"expected {upper!r} above {lower!r}, got {payees}"
    )


@step(r'the list shows only "(?P<payee>[^"]+)"')
def then_list_shows_only(world: World, payee: str) -> None:
    world.require_clean("listing should have succeeded")
    assert world.filtered_rows is not None, "no filtered list was produced"
    payees = [tx.payee for tx in world.filtered_rows]
    assert payees == [payee], f"expected only {payee!r}, got {payees}"


@step(
    r'the list shows "(?P<first>[^"]+)" and "(?P<second>[^"]+)" '
    r'but not "(?P<excluded>[^"]+)"'
)
def then_list_includes_and_excludes(
    world: World, first: str, second: str, excluded: str
) -> None:
    world.require_clean("listing should have succeeded")
    assert world.filtered_rows is not None, "no filtered list was produced"
    payees = [tx.payee for tx in world.filtered_rows]
    assert first in payees, f"{first!r} missing from the list: {payees}"
    assert second in payees, f"{second!r} missing from the list: {payees}"
    assert excluded not in payees, f"{excluded!r} should not be in the list: {payees}"


@step(r"the list is not shown")
def then_list_not_shown(world: World) -> None:
    assert world.tx_view is None, (
        "the transaction list was shown although no TRM is set "
        "(AC-9: reads fail loud, never assume rate 1)"
    )
    world.consume_rejection((MissingRate,), "viewing the list without a TRM")


@step(r"the transaction list does not show the expense")
def then_list_without_expense(world: World) -> None:
    world.require_clean("the deletion should have succeeded")
    ids = [tx.id for tx in transactions.list_transactions(world.session)]
    assert world.last_expense_id not in ids, (
        f"deleted expense {world.last_expense_id} still appears in the list"
    )


@step(r"the transaction list shows no transfer")
def then_list_shows_no_transfer(world: World) -> None:
    leftovers = [
        tx.id
        for tx in transactions.list_transactions(world.session)
        if tx.type == TxType.transfer
    ]
    context = ""
    if world.errors:
        details = "; ".join(f"{type(e).__name__}: {e}" for e in world.errors)
        context = f" (a preceding action failed — {details})"
    assert not leftovers, (
        f"transfer legs still present in the list (ids {leftovers}){context}"
    )


@step(r"the transaction list shows the expense")
def then_list_shows_expense(world: World) -> None:
    world.require_clean("the recording should have succeeded")
    tx = _last_expense(world)
    ids = [t.id for t in transactions.list_transactions(world.session)]
    assert tx.id in ids, f"expense {tx.id} does not appear in the list ({ids})"


@step(r'the remaining expense still carries the tag "(?P<name>[^"]+)"')
def then_remaining_expense_keeps_tag(world: World, name: str) -> None:
    world.require_clean("the deletion should have succeeded")
    assert len(world.expense_ids) >= 2, "the scenario recorded fewer than two expenses"
    remaining = world.expense_ids[1]
    names = _tag_names(world, remaining)
    assert name in names, (
        f"expected tag {name!r} on the remaining expense {remaining}, got {names}"
    )


@step(r'viewing the expense shows the tags "(?P<first>[^"]+)" and "(?P<second>[^"]+)"')
def then_expense_shows_tags(world: World, first: str, second: str) -> None:
    world.require_clean("tagging should have succeeded")
    names = _tag_names(world, _last_expense(world).id)
    expected = sorted([first, second])
    assert names == expected, f"expected tags {expected}, got {names}"


@step(r"viewing the expense shows no tags")
def then_expense_shows_no_tags(world: World) -> None:
    world.require_clean("removing the tag should have succeeded")
    names = _tag_names(world, _last_expense(world).id)
    assert names == [], f"expected no tags, got {names}"


@step(r'viewing the expense shows the tag "(?P<name>[^"]+)" exactly once')
def then_expense_shows_tag_once(world: World, name: str) -> None:
    world.require_clean("re-applying the tag should have succeeded")
    names = _tag_names(world, _last_expense(world).id)
    assert names == [name], f"expected exactly one {name!r} tag, got {names}"


@step(r'viewing the expense shows the tag "(?P<name>[^"]+)"')
def then_expense_shows_tag(world: World, name: str) -> None:
    world.require_clean("the recording should have succeeded")
    names = _tag_names(world, _last_expense(world).id)
    assert name in names, f"expected tag {name!r}, got {names}"


@step(r"the (?P<side>sending|receiving) side shows date (?P<date>" + _DATE + r")")
def then_transfer_side_date(world: World, side: str, date: str) -> None:
    world.require_clean("the edit should have succeeded")
    index = 0 if side == "sending" else 1
    leg = transactions.get_transaction(world.session, _transfer_leg(world, index).id)
    expected = Date.fromisoformat(date)
    assert leg.date == expected, (
        f"{side} side: expected date {expected}, got {leg.date}"
    )


@step(r"it is identified as part of a transfer")
def then_identified_as_transfer(world: World) -> None:
    world.require_clean("viewing the transfer side should have succeeded")
    leg = world.viewed_leg
    assert leg is not None, "no transfer side was viewed"
    assert leg.type == TxType.transfer, f"expected a transfer leg, got {leg.type}"
    assert leg.transfer_group_id, "the leg carries no transfer group id"


@step(r'its counterpart in "(?P<account>[^"]+)" is reachable from it')
def then_counterpart_reachable(world: World, account: str) -> None:
    world.require_clean("viewing the transfer side should have succeeded")
    leg = world.viewed_leg
    assert leg is not None, "no transfer side was viewed"
    counterparts = list(
        world.session.exec(
            select(Transaction).where(
                Transaction.transfer_group_id == leg.transfer_group_id,
                Transaction.id != leg.id,
            )
        ).all()
    )
    assert len(counterparts) == 1, (
        f"expected exactly one counterpart, got {len(counterparts)}"
    )
    counterpart = counterparts[0]
    assert counterpart.account_id == world.accounts[account], (
        f"counterpart is in account {counterpart.account_id}, "
        f"expected {account!r} ({world.accounts[account]})"
    )


@step(r"the registration is rejected")
def then_registration_rejected(world: World) -> None:
    world.consume_rejection((QuaestorError,), "the invalid registration")


@step(r"the user is told it does not exist")
def then_told_it_does_not_exist(world: World) -> None:
    err = world.consume_rejection((NotFound,), "acting on a missing transaction")
    assert "not found" in str(err).lower(), (
        f"the answer does not say the transaction is missing: {err}"
    )


@step(r"the expense records the assistant as its origin")
def then_expense_origin_is_assistant(world: World) -> None:
    world.require_clean("the recording should have succeeded")
    tx = _last_expense(world)
    assert tx.source == Source.agent, f"expected source 'agent', got {tx.source}"


@step(r"both show the same movements")
def then_both_surfaces_list_same_movements(world: World) -> None:
    world.require_clean("both list reads should have succeeded")
    assert world.app_payees is not None, "the app produced no list"
    assert world.assistant_payees is not None, "the assistant produced no list"
    assert world.app_payees, "the app list is empty"
    assert world.app_payees == world.assistant_payees, (
        f"app shows {world.app_payees}, assistant shows {world.assistant_payees}"
    )


@step(r"access is denied")
def then_access_denied(world: World) -> None:
    world.require_clean("the request should have reached the API")
    assert world.denied_status in (401, 403), (
        f"expected 401/403 without a session, got {world.denied_status}"
    )


@step(
    r"the current month's report shows an income total of "
    r"(?P<amount>" + _DEC + r") COP"
)
def then_current_month_income_total(world: World, amount: str) -> None:
    world.require_clean("reading the report should be possible")
    report = reports.monthly_report(
        world.session, _month_str(world.today), today=world.today
    )
    expected = major_to_cents(amount)
    assert report.income == expected, (
        f"expected income total {expected} cents ({amount} COP), got {report.income}"
    )

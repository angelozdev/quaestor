from datetime import date

from quaestor.domain.models import TxType
from quaestor.mcp.tools import core
from quaestor.mcp.tools.core import GetFxRateInput, ListTransactionsInput
from quaestor.services import accounts, fx, tags

from tests.support.categories import a_category


def test_list_accounts(session, seeded):
    out = core.list_accounts(session)
    assert "Bancolombia" in out and "100000.00" in out and "COP" in out


def test_list_categories(session, seeded):
    out = core.list_categories(session)
    assert "Groceries" in out


def test_list_tags(session, seeded):
    tags.create_tag(session, "trip")
    assert "trip" in core.list_tags(session)


def test_get_fx_rate_returns_current_trm(session):
    fx.set_trm(session, "4150")
    out = core.get_fx_rate(session, GetFxRateInput())
    assert out == "Current USD→COP rate (TRM): 4150"


def test_get_fx_rate_without_trm_returns_missing_rate_text(session):
    out = core.get_fx_rate(session, GetFxRateInput())
    assert "No TRM is set" in out
    assert "set_fx_rate" in out


def test_list_transactions_empty(session, seeded):
    fx.set_trm(session, "4000")
    out = core.list_transactions(session, ListTransactionsInput())
    assert out == "No transactions for those filters."


def test_list_transactions_without_trm_returns_missing_rate_text(session, seeded):
    out = core.list_transactions(session, ListTransactionsInput())
    assert "No TRM is set" in out
    assert "set_fx_rate" in out


def test_list_transactions_lists_and_totals(session, seeded):
    from quaestor.services import transactions as tx_service

    fx.set_trm(session, "4000")
    acc = seeded["account"]
    tx_service.record_expense(
        session, acc.id, 5_000_000, "COP", date(2026, 6, 18), "Lunch", category_id=a_category(session, TxType.expense)
    )
    tx_service.record_expense(
        session, acc.id, 3_000_000, "COP", date(2026, 6, 18), "Coffee", category_id=a_category(session, TxType.expense)
    )
    out = core.list_transactions(session, ListTransactionsInput(type="expense"))
    assert "Lunch" in out and "Coffee" in out
    assert "Total (COP): 80000.00" in out


def test_list_transactions_filters_by_account_name(session, seeded):
    from quaestor.services import transactions as tx_service

    fx.set_trm(session, "4000")
    other = accounts.create_account(session, "Savings", "savings", "COP", balance=0)
    tx_service.record_expense(
        session,
        seeded["account"].id,
        1_000_000,
        "COP",
        date(2026, 6, 18),
        "Here",
        category_id=a_category(session, TxType.expense),
    )
    out = core.list_transactions(session, ListTransactionsInput(account="Savings"))
    assert "Here" not in out  # filtered to the empty account
    assert other.id is not None


def test_list_transactions_unknown_account_returns_text(session, seeded):
    out = core.list_transactions(session, ListTransactionsInput(account="Nequi"))
    assert "Account 'Nequi' not found" in out


# --- ADR-0021: sort/order on MCP list_transactions ---


def _row_of(out: str, payee: str) -> int:
    """Return the line index of the markdown-table row whose Payee cell
    equals `payee`. Format is `| ... | <payee> | ...` per
    `mcp.format.transactions_table`."""
    needle = f"| {payee} |"
    for i, line in enumerate(out.splitlines()):
        if needle in line:
            return i
    raise AssertionError(f"payee {payee!r} not found in transactions_table output:\n{out}")


def test_mcp_list_transactions_default_orders_by_date_desc(session, seeded):
    from quaestor.services import transactions as tx_service

    fx.set_trm(session, "4000")
    acc = seeded["account"]
    tx_service.record_expense(
        session, acc.id, 100, "COP", date(2026, 6, 15), "mid", category_id=a_category(session, TxType.expense)
    )
    tx_service.record_expense(
        session, acc.id, 200, "COP", date(2026, 6, 1), "old", category_id=a_category(session, TxType.expense)
    )
    tx_service.record_expense(
        session, acc.id, 300, "COP", date(2026, 7, 1), "new", category_id=a_category(session, TxType.expense)
    )
    out = core.list_transactions(session, ListTransactionsInput())
    # Default = date DESC. Newest date ("new" 1-jul) above "mid" 15-jun above "old" 1-jun.
    new_row = _row_of(out, "new")
    mid_row = _row_of(out, "mid")
    old_row = _row_of(out, "old")
    assert new_row < mid_row < old_row, (
        f"expected order new < mid < old; got rows new={new_row}, mid={mid_row}, old={old_row}\n{out}"
    )


def test_mcp_list_transactions_explicit_sort_date_asc(session, seeded):
    from quaestor.services import transactions as tx_service

    fx.set_trm(session, "4000")
    acc = seeded["account"]
    tx_service.record_expense(
        session, acc.id, 100, "COP", date(2026, 6, 15), "mid", category_id=a_category(session, TxType.expense)
    )
    tx_service.record_expense(
        session, acc.id, 200, "COP", date(2026, 6, 1), "old", category_id=a_category(session, TxType.expense)
    )
    tx_service.record_expense(
        session, acc.id, 300, "COP", date(2026, 7, 1), "new", category_id=a_category(session, TxType.expense)
    )
    out = core.list_transactions(session, ListTransactionsInput(sort="date", order="asc"))
    old_row = _row_of(out, "old")
    mid_row = _row_of(out, "mid")
    new_row = _row_of(out, "new")
    assert old_row < mid_row < new_row, (
        f"expected order old < mid < new; got rows old={old_row}, mid={mid_row}, new={new_row}\n{out}"
    )

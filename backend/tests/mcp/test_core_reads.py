from datetime import date

from quaestor.mcp.tools import core
from quaestor.mcp.tools.core import GetFxRateInput, ListTransactionsInput
from quaestor.services import accounts, fx, tags


def test_list_accounts(session, seeded):
    out = core.list_accounts(session)
    assert "Bancolombia" in out and "100000.00" in out and "COP" in out


def test_list_categories(session, seeded):
    out = core.list_categories(session)
    assert "Groceries" in out


def test_list_tags(session, seeded):
    tags.create_tag(session, "trip")
    assert "trip" in core.list_tags(session)


def test_get_fx_rate_returns_rate(session):
    fx.set_fx_rate(session, date(2026, 6, 18), "4150")
    out = core.get_fx_rate(session, GetFxRateInput(date=date(2026, 6, 18)))
    assert "4150" in out and "Thu, 18 Jun 2026" in out


def test_get_fx_rate_missing_returns_text(session):
    out = core.get_fx_rate(session, GetFxRateInput(date=date(2026, 6, 18)))
    assert "USD→COP" in out


def test_list_transactions_empty(session, seeded):
    out = core.list_transactions(session, ListTransactionsInput())
    assert out == "No transactions for those filters."


def test_list_transactions_lists_and_totals(session, seeded):
    from quaestor.services import transactions as tx_service

    acc = seeded["account"]
    tx_service.record_expense(session, acc.id, 5_000_000, "COP", date(2026, 6, 18), "Lunch")
    tx_service.record_expense(session, acc.id, 3_000_000, "COP", date(2026, 6, 18), "Coffee")
    out = core.list_transactions(session, ListTransactionsInput(type="expense"))
    assert "Lunch" in out and "Coffee" in out
    assert "Total (COP): 80000.00" in out


def test_list_transactions_filters_by_account_name(session, seeded):
    from quaestor.services import transactions as tx_service

    other = accounts.create_account(session, "Savings", "savings", "COP", balance=0)
    tx_service.record_expense(
        session, seeded["account"].id, 1_000_000, "COP", date(2026, 6, 18), "Here"
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
    raise AssertionError(
        f"payee {payee!r} not found in transactions_table output:\n{out}"
    )


def test_mcp_list_transactions_default_orders_by_date_desc(session, seeded):
    from quaestor.services import transactions as tx_service

    acc = seeded["account"]
    tx_service.record_expense(session, acc.id, 100, "COP", date(2026, 6, 15), "mid")
    tx_service.record_expense(session, acc.id, 200, "COP", date(2026, 6, 1), "old")
    tx_service.record_expense(session, acc.id, 300, "COP", date(2026, 7, 1), "new")
    out = core.list_transactions(session, ListTransactionsInput())
    # Default = date DESC. Newest date ("new" 1-jul) above "mid" 15-jun above "old" 1-jun.
    new_row = _row_of(out, "new")
    mid_row = _row_of(out, "mid")
    old_row = _row_of(out, "old")
    assert new_row < mid_row < old_row, (
        f"expected order new < mid < old; got rows new={new_row}, "
        f"mid={mid_row}, old={old_row}\n{out}"
    )


def test_mcp_list_transactions_explicit_sort_date_asc(session, seeded):
    from quaestor.services import transactions as tx_service

    acc = seeded["account"]
    tx_service.record_expense(session, acc.id, 100, "COP", date(2026, 6, 15), "mid")
    tx_service.record_expense(session, acc.id, 200, "COP", date(2026, 6, 1), "old")
    tx_service.record_expense(session, acc.id, 300, "COP", date(2026, 7, 1), "new")
    out = core.list_transactions(
        session, ListTransactionsInput(sort="date", order="asc")
    )
    old_row = _row_of(out, "old")
    mid_row = _row_of(out, "mid")
    new_row = _row_of(out, "new")
    assert old_row < mid_row < new_row, (
        f"expected order old < mid < new; got rows old={old_row}, "
        f"mid={mid_row}, new={new_row}\n{out}"
    )

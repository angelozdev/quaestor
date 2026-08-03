
import pytest
from quaestor.mcp.tools import budgets_reads
from quaestor.mcp.tools.budgets_reads import (
    ListBudgetsInput,
    SafeToSpendInput,
)
from quaestor.services import accounts, budgets, categories, fx


@pytest.fixture
def seeded_month(session):
    fx.set_trm(session, "4000")
    acc = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    categories.create_category(session, "Groceries")
    budgets.set_budget(session, category_id=1, year_month="2026-06", amount_assigned=200_000)
    return acc


def test_list_budgets_table_with_one_line(session, seeded_month):
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-06"))
    assert "Groceries" in out and "| Category |" in out
    assert "2000.00" in out


def test_list_budgets_empty_month(session):
    fx.set_trm(session, "4000")
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-06"))
    assert out == "No budgets for that month."


def test_list_budgets_without_trm_returns_missing_rate_text(session):
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-06"))
    assert "No TRM is set" in out
    assert "set_fx_rate" in out


def test_list_budgets_rejects_malformed_month(session):
    out = budgets_reads.list_budgets(session, ListBudgetsInput(month="2026-6"))
    assert "Invalid input" in out


def test_safe_to_spend_card(session):
    fx.set_trm(session, "4000")
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    out = budgets_reads.safe_to_spend(session, SafeToSpendInput(month="2026-06"))
    assert "2026-06" in out and "free to spend" in out.lower()
    assert "Income forecast" in out


def test_safe_to_spend_without_trm_returns_missing_rate_text(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    out = budgets_reads.safe_to_spend(session, SafeToSpendInput(month="2026-06"))
    assert "No TRM is set" in out
    assert "set_fx_rate" in out

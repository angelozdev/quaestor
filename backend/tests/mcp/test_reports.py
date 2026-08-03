from datetime import date

from quaestor.mcp.tools import reports
from quaestor.services import accounts, categories, fx, transactions


def test_monthly_report_card_returns_headline(session):
    fx.set_trm(session, "4000")
    acc = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    categories.create_category(session, "Groceries")
    transactions.record_expense(
        session,
        account_id=acc.id,
        amount=5_000_000,
        currency="COP",
        date=date(2026, 6, 18),
        payee="Lunch",
        category_id=1,
    )
    out = reports.monthly_report(session, reports.MonthlyReportInput(month="2026-06"))
    assert "# Monthly report — 2026-06" in out
    assert "Income:" in out and "Expense:" in out and "Net:" in out


def test_monthly_report_without_trm_returns_missing_rate_text(session):
    accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    out = reports.monthly_report(session, reports.MonthlyReportInput(month="2026-06"))
    assert "No TRM is set" in out
    assert "set_fx_rate" in out


def test_monthly_report_rejects_malformed_month(session):
    out = reports.monthly_report(session, reports.MonthlyReportInput(month="2026-6"))
    assert "Invalid input" in out

from datetime import date
from decimal import Decimal

import pytest
from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType, Transaction, TxStatus, TxType
from quaestor.domain.rules import month_bounds
from quaestor.services import accounts, categories, fx, reports, transactions
from quaestor.services.month_aggregate import load_month_aggregate

from tests.support.categories import a_category

TRM = Decimal("4000")


def _acc(session, currency="COP", balance=100_000_000):
    return accounts.create_account(session, f"Acc {currency}", AccountType.debit, currency, balance=balance)


def _cat(session, name="Food", **kw):
    return categories.create_category(session, name=name, **kw)


def test_validate_month_rejects_malformed(session):
    with pytest.raises(ValidationError):
        reports._validate_month("2026-13")
    with pytest.raises(ValidationError):
        reports._validate_month("June")
    reports._validate_month("2026-06")  # no raise


def test_totals_posted_only_excludes_planned_and_transfer(session):
    from quaestor.services import planned

    acc = _acc(session)
    acc2 = _acc(session, currency="COP")
    cat = _cat(session)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "groceries", category_id=cat.id)
    transactions.record_income(
        session, acc.id, 80_000, "COP", date(2026, 6, 1), "salary", category_id=a_category(session, TxType.income)
    )
    transactions.transfer(session, acc.id, acc2.id, 10_000, "COP", date(2026, 6, 6))  # excluded
    planned.plan_payment(
        session,
        payee="rent",
        amount=50_000,
        currency="COP",
        account_id=acc.id,
        due_date=date(2026, 6, 10),
        category_id=cat.id,
    )  # planned, excluded
    agg = load_month_aggregate(session, "2026-06", TRM)
    income, expense, net = agg.totals_for("2026-06")
    assert income == 80_000
    assert expense == 30_000
    assert net == 50_000


def test_totals_respect_exclude_from_totals(session):
    acc = _acc(session)
    normal = _cat(session, name="Food")
    excluded = _cat(session, name="Reimbursable", exclude_from_totals=True)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=normal.id)
    transactions.record_expense(session, acc.id, 99_000, "COP", date(2026, 6, 7), "reimb", category_id=excluded.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    _, expense, _ = agg.totals_for("2026-06")
    assert expense == 30_000


def test_usd_share(session):
    acc_cop = _acc(session, currency="COP")
    acc_usd = _acc(session, currency="USD")
    cat = _cat(session)
    transactions.record_expense(session, acc_cop.id, 300_000, "COP", date(2026, 6, 5), "cop", category_id=cat.id)
    transactions.record_expense(session, acc_usd.id, 25, "USD", date(2026, 6, 6), "usd", category_id=cat.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    expenses = agg.month_expense()
    expense_total = sum(agg.to_cop_cents(t) for t in expenses)
    assert expense_total == 400_000
    assert reports._usd_share(agg, expenses, expense_total) == pytest.approx(0.25)


def test_usd_share_zero_when_no_expense(session):
    agg = load_month_aggregate(session, "2026-06", TRM)
    assert reports._usd_share(agg, [], 0) == 0.0


def test_category_sections_sorted_with_pct_and_ungrouped(session):
    acc = _acc(session)
    grp = categories.create_group(session, name="Essentials")
    food = _cat(session, name="Food", group_id=grp.id)
    fun = _cat(session, name="Fun", group_id=grp.id)
    loose = _cat(session, name="Zapatos")
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 5), "f", category_id=food.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 6), "u", category_id=fun.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 7), "z", category_id=loose.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    expenses = agg.month_expense()
    total = sum(agg.to_cop_cents(t) for t in expenses)
    sections = reports._category_sections(agg, expenses, total)
    assert [s.category for s in sections] == ["Food", "Fun", "Zapatos"]
    assert sections[0].group == "Essentials"
    assert sections[-1].group is None
    assert sections[0].total == 200_000
    assert sections[0].pct == pytest.approx(50.0)


def test_group_sections_rollup(session):
    acc = _acc(session)
    essentials = categories.create_group(session, name="Essentials")
    food = _cat(session, name="Food", group_id=essentials.id)
    rent = _cat(session, name="Rent", group_id=essentials.id)
    loose = _cat(session, name="Loose")  # no group
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 5), "a", category_id=food.id)
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 6), "b", category_id=rent.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 7), "c", category_id=loose.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    expenses = agg.month_expense()
    total = sum(agg.to_cop_cents(t) for t in expenses)
    groups = reports._group_sections(agg, expenses, total)
    assert [g.group for g in groups] == ["Essentials", "Ungrouped"]
    assert groups[0].total == 300_000
    assert groups[0].pct == pytest.approx(75.0)
    assert groups[1].group == "Ungrouped" and groups[1].total == 100_000


def test_drift_none_on_cold_start(session):
    acc = _acc(session)
    cat = _cat(session)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=cat.id)
    # no May activity -> cold start
    agg = load_month_aggregate(session, "2026-06", TRM)
    income, expense, net = agg.totals_for("2026-06")
    assert reports._drift(agg, income, expense, net) is None


def test_drift_abs_and_pct(session):
    acc = _acc(session)
    cat = _cat(session)
    # May: income 100_000, expense 40_000, net 60_000
    transactions.record_income(
        session, acc.id, 100_000, "COP", date(2026, 5, 10), "s", category_id=a_category(session, TxType.income)
    )
    transactions.record_expense(session, acc.id, 40_000, "COP", date(2026, 5, 11), "x", category_id=cat.id)
    # June: income 150_000, expense 60_000, net 90_000
    transactions.record_income(
        session, acc.id, 150_000, "COP", date(2026, 6, 10), "s", category_id=a_category(session, TxType.income)
    )
    transactions.record_expense(session, acc.id, 60_000, "COP", date(2026, 6, 11), "x", category_id=cat.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    income, expense, net = agg.totals_for("2026-06")
    d = reports._drift(agg, income, expense, net)
    assert d is not None and d.prev_month == "2026-05"
    assert d.income_abs == 50_000 and d.income_pct == pytest.approx(50.0)
    assert d.expense_abs == 20_000 and d.expense_pct == pytest.approx(50.0)
    assert d.net_abs == 30_000 and d.net_pct == pytest.approx(50.0)


def test_drift_pct_none_when_previous_zero(session):
    acc = _acc(session)
    cat = _cat(session)
    # May has expense only (income 0); June has income
    transactions.record_expense(session, acc.id, 10_000, "COP", date(2026, 5, 5), "x", category_id=cat.id)
    transactions.record_income(
        session, acc.id, 50_000, "COP", date(2026, 6, 5), "s", category_id=a_category(session, TxType.income)
    )
    transactions.record_expense(session, acc.id, 10_000, "COP", date(2026, 6, 6), "x", category_id=cat.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    income, expense, net = agg.totals_for("2026-06")
    d = reports._drift(agg, income, expense, net)
    assert d is not None
    assert d.income_abs == 50_000 and d.income_pct is None  # previous income was 0
    assert d.expense_pct == pytest.approx(0.0)  # 10_000 -> 10_000


def test_fund_lines_and_summary(session):
    from quaestor.services import funds

    acc = _acc(session)
    food = _cat(session, name="Food")
    fun = _cat(session, name="Fun")
    funds.create_fund(session, food.id, rule="fixed", amount=100_000, start_month="2026-06")
    funds.create_fund(
        session,
        fun.id,
        rule="target-by-date",
        target_amount=300_000,
        target_month="2026-12",
        start_month="2026-06",
        opening_balance=150_000,
    )
    transactions.record_expense(session, acc.id, 40_000, "COP", date(2026, 6, 5), "f", category_id=food.id)
    transactions.record_expense(session, acc.id, 70_000, "COP", date(2026, 6, 6), "u", category_id=fun.id)
    agg = load_month_aggregate(session, "2026-06", TRM)
    lines, summary = reports._fund_lines(agg, funds.month_available(agg).funds)
    assert [row.category_name for row in lines] == ["Food", "Fun"]
    food_line = lines[0]
    assert food_line.asks == 100_000 and food_line.spent == 40_000
    assert food_line.holds == 0 and food_line.on_track is True
    fun_line = lines[1]
    assert fun_line.holds == 80_000 and fun_line.spent == 70_000
    assert fun_line.asks == 36_667 and fun_line.on_track is False  # drained, so it asks more
    assert summary.n_on_track == 1 and summary.n_behind == 1
    assert summary.set_aside == 80_000


def test_fund_lines_empty_when_no_funds(session):
    agg = load_month_aggregate(session, "2026-06", TRM)
    lines, summary = reports._fund_lines(agg, [])
    assert lines == []
    assert summary.n_on_track == 0 and summary.n_behind == 0 and summary.set_aside == 0


def test_balance_lines_exclude_archived_sorted(session):
    accounts.create_account(session, "Zeta", AccountType.debit, "COP", balance=500)
    accounts.create_account(session, "Alpha", AccountType.debit, "USD", balance=999)
    archived = accounts.create_account(session, "Old", AccountType.debit, "COP", balance=1)
    accounts.archive_account(session, archived.id)
    balances = reports._balance_lines(session)
    assert [b.account for b in balances] == ["Alpha", "Zeta"]
    assert balances[0].currency == "USD" and balances[0].balance == 999


def test_pending_lines_group_by_account(session):
    from quaestor.services import planned

    acc = _acc(session)
    cat = _cat(session)
    planned.plan_payment(
        session,
        payee="rent",
        amount=4_000_000,
        currency="COP",
        account_id=acc.id,
        due_date=date(2026, 6, 10),
        category_id=cat.id,
    )
    lines = reports._pending_lines(session, *month_bounds("2026-06"), TRM)
    assert len(lines) == 1
    assert "Acc COP" in lines[0] and "40,000.00" in lines[0]


def test_pending_lines_empty_when_nothing_planned(session):
    assert reports._pending_lines(session, *month_bounds("2026-06"), TRM) == []


def test_pending_lines_exclude_planned_income(session):
    """Pending means what is owed — expected money in is not pending (AC-15)."""
    from decimal import Decimal

    from quaestor.domain.models import TxType

    acc = _acc(session)
    session.add(
        Transaction(
            date=date(2026, 6, 10),
            payee="Empleador",
            type=TxType.income,
            status=TxStatus.planned,
            amount=5_000_000,
            currency="COP",
            fx_rate=Decimal("1"),
            to_base=5_000_000,
            account_id=acc.id,
            source="manual",
            category_id=a_category(session, TxType.income),
        )
    )
    session.commit()
    assert reports._pending_lines(session, *month_bounds("2026-06"), TRM) == []


def test_monthly_report_pending_lines_exclude_prior_overdue(session):
    """Retrospective monthly report excludes items overdue from a prior month."""
    from datetime import date as Date

    from quaestor.domain.models import AccountType
    from quaestor.services import accounts, planned
    from quaestor.services.reports import monthly_report

    fx.set_trm(session, "4000")
    a = accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    planned.plan_payment(
        session,
        payee="PriorOverdue",
        amount=100_000,
        currency="COP",
        account_id=a.id,
        due_date=Date(2026, 5, 15),
        category_id=a_category(session),
    )
    planned.plan_payment(
        session,
        payee="InMonth",
        amount=200_000,
        currency="COP",
        account_id=a.id,
        due_date=Date(2026, 7, 5),
        category_id=a_category(session),
    )
    rep = monthly_report(session, "2026-07", today=Date(2026, 7, 15))
    pending_text = "\n".join(rep.pending)
    assert "$2,000.00" in pending_text
    assert "$1,000.00" not in pending_text


def test_monthly_report_end_to_end(session):
    from quaestor.services import funds

    fx.set_trm(session, "4000")
    acc = _acc(session)
    food = _cat(session, name="Food")
    funds.create_fund(session, food.id, rule="fixed", amount=100_000, start_month="2026-06")
    transactions.record_income(
        session, acc.id, 500_000, "COP", date(2026, 6, 1), "salary", category_id=a_category(session, TxType.income)
    )
    transactions.record_expense(session, acc.id, 80_000, "COP", date(2026, 6, 5), "groceries", category_id=food.id)

    report = reports.monthly_report(session, "2026-06", today=date(2026, 6, 15))

    assert report.month == "2026-06"
    assert report.income == 500_000 and report.expense == 80_000 and report.net == 420_000
    assert report.funds_summary.n_on_track == 1
    assert [c.category for c in report.by_category] == ["Food"]
    assert report.drift_mom is None  # cold start
    assert report.usd_share == 0.0
    assert report.available.year_month == "2026-06"
    assert report.available.free == report.available.income - 100_000 - report.available.uncovered
    # markdown is rendered from the same data
    assert report.markdown.startswith("# Monthly report — 2026-06")
    assert "**Net:** $4,200.00 COP" in report.markdown


def test_monthly_report_rejects_malformed_month(session):
    with pytest.raises(ValidationError):
        reports.monthly_report(session, "2026-13")

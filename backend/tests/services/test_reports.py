from datetime import date

import pytest

from quaestor.domain.errors import ValidationError
from quaestor.domain.models import AccountType, TxType
from quaestor.domain.rules import month_bounds
from quaestor.services import accounts, categories, reports, transactions


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
    transactions.record_income(session, acc.id, 80_000, "COP", date(2026, 6, 1), "salary", category_id=cat.id)
    transactions.transfer(session, acc.id, acc2.id, 10_000, "COP", date(2026, 6, 6))  # excluded
    planned.plan_payment(session, payee="rent", amount=50_000, currency="COP",
                         account_id=acc.id, due_date=date(2026, 6, 10), category_id=cat.id)  # planned, excluded
    start, end = month_bounds("2026-06")
    income, expense, net = reports._totals(session, start, end)
    assert income == 80_000
    assert expense == 30_000
    assert net == 50_000


def test_totals_respect_exclude_from_totals(session):
    acc = _acc(session)
    normal = _cat(session, name="Food")
    excluded = _cat(session, name="Reimbursable", exclude_from_totals=True)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=normal.id)
    transactions.record_expense(session, acc.id, 99_000, "COP", date(2026, 6, 7), "reimb", category_id=excluded.id)
    start, end = month_bounds("2026-06")
    _, expense, _ = reports._totals(session, start, end)
    assert expense == 30_000


def test_usd_share(session):
    acc_cop = _acc(session, currency="COP")
    acc_usd = _acc(session, currency="USD")
    from quaestor.services import fx
    fx.set_fx_rate(session, date(2026, 6, 1), 4000)
    cat = _cat(session)
    transactions.record_expense(session, acc_cop.id, 300_000, "COP", date(2026, 6, 5), "cop", category_id=cat.id)
    # 25 USD * 4000 = 100_000 COP cents to_base
    transactions.record_expense(session, acc_usd.id, 25, "USD", date(2026, 6, 6), "usd", category_id=cat.id)
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    expense_total = sum(t.to_base for t in expenses)
    assert expense_total == 400_000
    assert reports._usd_share(expenses, expense_total) == pytest.approx(0.25)


def test_usd_share_zero_when_no_expense(session):
    assert reports._usd_share([], 0) == 0.0


def test_category_sections_sorted_with_pct_and_uncategorized(session):
    acc = _acc(session)
    grp = categories.create_group(session, name="Essentials")
    food = _cat(session, name="Food", group_id=grp.id)
    fun = _cat(session, name="Fun", group_id=grp.id)
    transactions.record_expense(session, acc.id, 200_000, "COP", date(2026, 6, 5), "f", category_id=food.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 6), "u", category_id=fun.id)
    transactions.record_expense(session, acc.id, 100_000, "COP", date(2026, 6, 7), "none")  # uncategorized
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    total = sum(t.to_base for t in expenses)
    sections = reports._category_sections(session, expenses, total)
    assert [s.category for s in sections] == ["Food", "Fun", "Uncategorized"]
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
    start, end = month_bounds("2026-06")
    expenses = reports._posted_for_totals(session, TxType.expense, start, end)
    total = sum(t.to_base for t in expenses)
    groups = reports._group_sections(session, expenses, total)
    assert [g.group for g in groups] == ["Essentials", "Ungrouped"]
    assert groups[0].total == 300_000
    assert groups[0].pct == pytest.approx(75.0)
    assert groups[1].group == "Ungrouped" and groups[1].total == 100_000


def test_drift_none_on_cold_start(session):
    acc = _acc(session)
    cat = _cat(session)
    transactions.record_expense(session, acc.id, 30_000, "COP", date(2026, 6, 5), "x", category_id=cat.id)
    # no May activity -> cold start
    income, expense, net = reports._totals(session, *month_bounds("2026-06"))
    assert reports._drift(session, "2026-06", income, expense, net) is None


def test_drift_abs_and_pct(session):
    acc = _acc(session)
    cat = _cat(session)
    # May: income 100_000, expense 40_000, net 60_000
    transactions.record_income(session, acc.id, 100_000, "COP", date(2026, 5, 10), "s", category_id=cat.id)
    transactions.record_expense(session, acc.id, 40_000, "COP", date(2026, 5, 11), "x", category_id=cat.id)
    # June: income 150_000, expense 60_000, net 90_000
    transactions.record_income(session, acc.id, 150_000, "COP", date(2026, 6, 10), "s", category_id=cat.id)
    transactions.record_expense(session, acc.id, 60_000, "COP", date(2026, 6, 11), "x", category_id=cat.id)
    income, expense, net = reports._totals(session, *month_bounds("2026-06"))
    d = reports._drift(session, "2026-06", income, expense, net)
    assert d is not None and d.prev_month == "2026-05"
    assert d.income_abs == 50_000 and d.income_pct == pytest.approx(50.0)
    assert d.expense_abs == 20_000 and d.expense_pct == pytest.approx(50.0)
    assert d.net_abs == 30_000 and d.net_pct == pytest.approx(50.0)


def test_drift_pct_none_when_previous_zero(session):
    acc = _acc(session)
    cat = _cat(session)
    # May has expense only (income 0); June has income
    transactions.record_expense(session, acc.id, 10_000, "COP", date(2026, 5, 5), "x", category_id=cat.id)
    transactions.record_income(session, acc.id, 50_000, "COP", date(2026, 6, 5), "s", category_id=cat.id)
    transactions.record_expense(session, acc.id, 10_000, "COP", date(2026, 6, 6), "x", category_id=cat.id)
    income, expense, net = reports._totals(session, *month_bounds("2026-06"))
    d = reports._drift(session, "2026-06", income, expense, net)
    assert d is not None
    assert d.income_abs == 50_000 and d.income_pct is None  # previous income was 0
    assert d.expense_pct == pytest.approx(0.0)  # 10_000 -> 10_000


def test_envelope_lines_and_summary(session):
    from quaestor.services import budgets
    acc = _acc(session)
    food = _cat(session, name="Food")
    fun = _cat(session, name="Fun")
    budgets.set_budget(session, food.id, "2026-06", 100_000)
    budgets.set_budget(session, fun.id, "2026-06", 50_000)
    transactions.record_expense(session, acc.id, 40_000, "COP", date(2026, 6, 5), "f", category_id=food.id)
    transactions.record_expense(session, acc.id, 70_000, "COP", date(2026, 6, 6), "u", category_id=fun.id)  # over
    lines, summary = reports._envelope_lines(session, "2026-06")
    assert [l.category for l in lines] == ["Food", "Fun"]
    food_line = lines[0]
    assert food_line.allocated == 100_000 and food_line.spent == 40_000
    assert food_line.available == 60_000 and food_line.status == "under"
    fun_line = lines[1]
    assert fun_line.available == -20_000 and fun_line.status == "over"
    assert summary.n_green == 1 and summary.n_red == 1
    assert summary.rollover_generated == 60_000  # only Food's positive available


def test_envelope_lines_empty_when_no_budgets(session):
    lines, summary = reports._envelope_lines(session, "2026-06")
    assert lines == []
    assert summary.n_green == 0 and summary.n_red == 0 and summary.rollover_generated == 0


def test_goal_lines_defined_and_open_ended(session):
    from quaestor.services import goals
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                      target_amount=1_200_000, deadline=date(2026, 12, 1))
    goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    lines = reports._goal_lines(session, today=date(2026, 6, 1))
    by_name = {l.name: l for l in lines}
    assert by_name["Trip"].target == 1_200_000 and by_name["Trip"].eta is not None
    assert by_name["Trip"].on_track is not None
    assert by_name["Buffer"].target is None and by_name["Buffer"].eta is None
    assert by_name["Buffer"].on_track is None


def test_balance_lines_exclude_archived_sorted(session):
    a = accounts.create_account(session, "Zeta", AccountType.debit, "COP", balance=500)
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
    planned.plan_payment(session, payee="rent", amount=4_000_000, currency="COP",
                         account_id=acc.id, due_date=date(2026, 6, 10), category_id=cat.id)
    lines = reports._pending_lines(session, *month_bounds("2026-06"))
    assert len(lines) == 1
    assert "Acc COP" in lines[0] and "40,000.00" in lines[0]


def test_pending_lines_empty_when_nothing_planned(session):
    assert reports._pending_lines(session, *month_bounds("2026-06")) == []

from datetime import date
from decimal import Decimal

from quaestor.domain.dtos import (
    BudgetLine,
    GoalProgress,
    SafeToSpend,
)
from quaestor.domain.errors import (
    MissingRate,
    NotFound,
    TransferImbalance,
    ValidationError,
)
from quaestor.domain.models import (
    Account,
    AccountType,
    Category,
    CategoryGroup,
    Goal,
    GoalStatus,
    IntervalUnit,
    RecurringItem,
    RecurringMode,
    Settings,
    Tag,
    Transaction,
    TxStatus,
    TxType,
)
from quaestor.mcp import format


def _expense(currency="COP", amount=4_000_000):
    return Transaction(
        date=date(2026, 6, 18),
        payee="Groceries",
        type=TxType.expense,
        amount=amount,
        currency=currency,
        account_id=1,
        category_id=1,
    )


def test_money_renders_major_units_and_currency():
    assert format.money(4_000_000, "COP") == "40000.00 COP"


def test_display_date_renders_app_wide_format():
    # 2026-05-10 is a Sunday
    assert format.display_date(date(2026, 5, 10)) == "Sun, 10 May 2026"
    assert format.display_date(date(2026, 6, 18)) == "Thu, 18 Jun 2026"
    assert format.display_date(date(2026, 1, 1)) == "Thu, 1 Jan 2026"


def test_missing_rate_uses_canonical_sentence():
    text = format.domain_error_text(MissingRate("set usd_cop rate for 2026-06-18"))
    assert "USD→COP" in text
    assert "set_fx_rate" in text


def test_not_found_passes_message_through():
    assert format.domain_error_text(NotFound("Account 'X' not found.")) == ("Account 'X' not found.")


def test_validation_error_is_framed():
    assert format.domain_error_text(ValidationError("amount must be > 0")).startswith("Invalid input:")


def test_transfer_imbalance_is_framed():
    assert format.domain_error_text(TransferImbalance("source and destination cannot be the same account")).startswith(
        "Could not record the transfer:"
    )


def test_expense_confirmation_cop_omits_equivalent():
    acc = Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=6_000_000)
    text = format.expense_confirmation(_expense(), acc, cop_equivalent=4_000_000)
    assert "Expense recorded" in text
    assert "Groceries" in text
    assert "Bancolombia" in text
    assert "60000.00 COP" in text
    assert "Equivalent" not in text


def test_expense_confirmation_usd_shows_read_time_equivalent():
    acc = Account(name="Amex", type=AccountType.credit, currency="USD", balance=-1200)
    tx = _expense(currency="USD", amount=1200)
    text = format.expense_confirmation(tx, acc, cop_equivalent=4_980_000)
    assert "Equivalent: 49800.00 COP" in text


def test_expense_confirmation_usd_without_trm_omits_equivalent():
    acc = Account(name="Amex", type=AccountType.credit, currency="USD", balance=-1200)
    tx = _expense(currency="USD", amount=1200)
    text = format.expense_confirmation(tx, acc, cop_equivalent=None)
    assert "Expense recorded" in text
    assert "Equivalent" not in text


def test_transfer_confirmation_lists_both_balances():
    src = Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=2_000_000)
    dst = Account(name="Savings", type=AccountType.savings, currency="COP", balance=8_000_000)
    text = format.transfer_confirmation(src, dst, 5_000_000, 5_000_000)
    assert "Bancolombia" in text and "Savings" in text
    assert "20000.00 COP" in text and "80000.00 COP" in text
    assert "received" not in text


def test_transfer_confirmation_cross_currency_shows_both_amounts():
    src = Account(name="Wise", type=AccountType.debit, currency="USD", balance=40_000)
    dst = Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=140_000_000)
    text = format.transfer_confirmation(src, dst, 10_000, 40_000_000)
    assert "100.00 USD" in text
    assert "400000.00 COP received" in text


def test_fx_set_and_current_are_scalar():
    assert format.fx_set(Decimal("4150")) == "✅ USD→COP rate (TRM) set: 4150"
    assert format.fx_current(Decimal("4150")) == "Current USD→COP rate (TRM): 4150"
    assert "4100.5" in format.fx_current(Decimal("4100.50"))


def test_accounts_table_and_empty():
    accs = [Account(name="Bancolombia", type=AccountType.debit, currency="COP", balance=10_000_000)]
    table = format.accounts_table(accs)
    assert "Bancolombia" in table and "100000.00" in table and "| Account |" in table
    assert format.accounts_table([]) == "No accounts."


def test_categories_table_resolves_group_name():
    groups = [CategoryGroup(id=1, name="Essentials")]
    cats = [Category(name="Groceries", group_id=1), Category(name="Salary", is_income=True)]
    table = format.categories_table(cats, groups)
    assert "Groceries" in table and "Essentials" in table
    assert "Salary" in table and "yes" in table  # is_income


def test_tags_list():
    assert format.tags_list([Tag(name="trip"), Tag(name="work")]) == ("Tags: trip, work")
    assert format.tags_list([]) == "No tags."


def test_transactions_table_has_total_and_empty():
    txs = [_expense(), _expense(amount=1_000_000)]
    table = format.transactions_table(txs, Decimal("4000"))
    assert "| Date |" in table
    assert "Total (COP): 50000.00" in table
    assert "2 transaction(s)" in table
    assert format.transactions_table([], Decimal("4000")) == "No transactions for those filters."


def test_transactions_table_converts_usd_at_the_trm():
    table = format.transactions_table([_expense(currency="USD", amount=1_000)], Decimal("4000"))
    assert "40000.00" in table
    assert "Total (COP): 40000.00" in table


def test_account_card_basic():
    a = Account(id=7, name="Bancolombia", type=AccountType.debit, currency="COP", balance=4_500_000)
    text = format.account_card(a)
    assert "Bancolombia" in text and "debit" in text
    assert "45000.00 COP" in text
    assert "id=7" in text


def test_category_card_with_group():
    g = CategoryGroup(id=3, name="Essentials")
    c = Category(id=4, name="Groceries", group_id=3, is_income=False)
    text = format.category_card(c, group=g)
    assert "Groceries" in text and "Essentials" in text
    assert "id=4" in text


def test_category_card_without_group():
    c = Category(id=4, name="Groceries", group_id=None, is_income=True)
    text = format.category_card(c, group=None)
    assert "Groceries" in text and "(no group)" in text
    assert "income" in text


def test_category_group_card():
    g = CategoryGroup(id=2, name="Essentials", sort_order=1)
    text = format.category_group_card(g)
    assert "Essentials" in text and "id=2" in text


def test_tag_card():
    t = Tag(id=9, name="travel")
    assert format.tag_card(t) == "Tag 'travel' (id 9)."


def test_transaction_card():
    tx = Transaction(
        id=42,
        date=date(2026, 6, 18),
        payee="Lunch",
        type=TxType.expense,
        status=TxStatus.posted,
        amount=5_000_000,
        currency="COP",
        account_id=1,
        category_id=1,
    )
    text = format.transaction_card(tx, Decimal("4000"))
    assert "Lunch" in text and "50000.00 COP" in text
    assert "Thu, 18 Jun 2026" in text and "id=42" in text


def test_transaction_card_usd_shows_read_time_cop_equivalent():
    tx = Transaction(
        id=7,
        date=date(2026, 6, 18),
        payee="Spotify",
        type=TxType.expense,
        status=TxStatus.posted,
        amount=1_000,
        currency="USD",
        account_id=1,
        category_id=1,
    )
    text = format.transaction_card(tx, Decimal("4000"))
    assert "10.00 USD" in text
    assert "(40000.00 COP)" in text


def test_settings_card():
    s = Settings(id=1, base_currency="COP", default_source_account_id=3)
    text = format.settings_card(s)
    assert "Base currency: COP" in text
    assert "default source account: 3" in text


def test_budgets_table_empty():
    assert format.budgets_table([]) == "No budgets for that month."


def test_budgets_table_renders_lines():
    lines = [
        BudgetLine(
            category_id=1,
            category_name="Groceries",
            assigned=200_000,
            rollover_in=0,
            spent=80_000,
            available=120_000,
            pct_used=40.0,
            status="under",
        )
    ]
    text = format.budgets_table(lines)
    assert "Groceries" in text and "| Category |" in text
    assert "2000.00" in text and "800.00" in text
    assert "1200.00" in text


def test_safe_to_spend_card():
    sts = SafeToSpend(
        year_month="2026-06",
        income_forecast=2_000_000,
        committed=600_000,
        assigned_envelopes=400_000,
        free=1_000_000,
        committed_breakdown=[],
    )
    text = format.safe_to_spend_card(sts)
    assert "2026-06" in text
    assert "10000.00 COP" in text  # free
    assert "20000.00 COP" in text  # income
    assert "free to spend" in text.lower()


def test_goals_table():
    goals = [
        Goal(
            id=1,
            name="Trip",
            monthly_amount=500_000,
            savings_account_id=2,
            target_amount=2_000_000,
            deadline=date(2026, 12, 31),
            status=GoalStatus.active,
        ),
    ]
    text = format.goals_table(goals)
    assert "Trip" in text and "5000.00 COP" in text
    assert "id=1" in text and "defined" in text


def test_goals_table_empty():
    assert format.goals_table([]) == "No goals."


def test_goals_progress_table():
    progress = [
        GoalProgress(
            goal_id=1,
            name="Trip",
            type="defined",
            monthly_amount=500_000,
            saved=600_000,
            target_amount=2_000_000,
            deadline=date(2026, 12, 31),
            eta=None,
            on_track=True,
        )
    ]
    text = format.goals_progress_table(progress)
    assert "Trip" in text and "6000.00" in text and "20000.00" in text
    assert "on-track" in text


def test_monthly_report_card_headline():
    # Minimal MonthlyReport-like object: only fields the renderer reads.
    class _R:
        month = "2026-06"
        income = 5_000_000
        expense = 3_000_000
        net = 2_000_000
        markdown = "# sample"

    text = format.monthly_report_card(_R())
    assert "2026-06" in text
    assert "50000.00 COP" in text  # income
    assert "30000.00 COP" in text  # expense
    assert "20000.00 COP" in text  # net


def test_recurring_restored():
    item = RecurringItem(
        id=5,
        name="Rent",
        payee="Landlord",
        type=TxType.expense,
        mode=RecurringMode.auto,
        amount=2_000_000,
        currency="COP",
        category_id=1,
        account_id=1,
        interval_unit=IntervalUnit.month,
        interval_count=1,
        start_date=date(2026, 1, 1),
        end_date=None,
        active=True,
    )
    text = format.recurring_restored(item)
    assert "Rent" in text and "restored" in text
    assert "id=5" in text

import re
from datetime import date
from decimal import Decimal

from quaestor.domain.dtos import MetaStatus, MonthAvailable
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


def _meta_status(name, **overrides):
    spec = {
        "meta_id": 1,
        "name": name,
        "year_month": "2026-11",
        "amount": 1_000_000,
        "currency": "COP",
        "target_month": "2026-12",
        "asks": 100_000,
        "asks_cop": 100_000,
        "holds": 400_000,
        "progress": 40,
        "complete": False,
        "closed": False,
        "waiting": False,
    }
    return MetaStatus(**{**spec, **overrides})


def _available(metas, **overrides):
    spec = {
        "year_month": "2026-11",
        "income": 5_000_000,
        "funds": [],
        "uncovered": 0,
        "free": 4_900_000,
        "metas": metas,
        "contributed": 0,
        "released": 0,
    }
    return MonthAvailable(**{**spec, **overrides})


def test_the_money_card_leaves_out_a_meta_that_claims_nothing():
    """A finished meta would otherwise sit at −0.00 in every month, forever.

    `available_breakdown.ts` drops it for that reason and the card is the same
    column (AC-32, ADR-0006/0009). The month goes on carrying a closed meta so
    the month it was bought in still charges it, which means every month after
    that one lists it asking nothing.
    """
    card = format.money_available_card(
        _available([_meta_status("Celular", asks=0, asks_cop=0, closed=True, complete=True)])
    )

    assert "Celular" not in card


def test_the_money_card_says_which_meta_was_cancelled():
    """The screen renders "(la cancelaste)" so three metas can be told apart.

    A cancelled meta is named by the month it was cancelled in — it charged its
    instalment and handed back what it held — and a row indistinguishable from
    a running meta's reads as one still saving.
    """
    card = format.money_available_card(
        _available([_meta_status("Celular", cancelled=True), _meta_status("Televisor", meta_id=2)])
    )

    assert "- Meta Celular (you cancelled it): −1000.00 COP" in card
    assert "- Meta Televisor: −1000.00 COP" in card


def test_the_money_card_names_each_give_back_and_says_why():
    """Two metas hand money back for different reasons and the card must say both.

    One line reading "Given back by a cancelled meta" is wrong twice over: it
    does not say which meta, and it calls a lowered amount a cancellation.
    """
    card = format.money_available_card(
        _available(
            [
                _meta_status("Celular", cancelled=True, released=600_000),
                _meta_status("Televisor", meta_id=2, released=260_000),
            ],
            released=860_000,
        )
    )

    assert "- Given back by Celular (you cancelled it): +6000.00 COP" in card
    assert "- Given back by Televisor (you lowered its amount): +2600.00 COP" in card


_FIGURE = re.compile(r"(−|\+)?(\d+\.\d{2}) COP")


def _signed_cents(line: str) -> int:
    sign, figure = _FIGURE.search(line).groups()
    return round(float(figure) * 100) * (-1 if sign == "−" else 1)


def test_the_money_cards_terms_still_reach_the_total_it_prints():
    """`income − Σ claims = free` (AC-10), read off the card the assistant sends.

    A correct total whose terms do not reach it is what product decision 15
    exists to prevent, and naming the give-backs one per meta is exactly the
    kind of change that could drop one.
    """
    view = _available(
        [
            _meta_status("Celular", cancelled=True, released=600_000),
            _meta_status("Televisor", meta_id=2, asks=0, asks_cop=0),
        ],
        contributed=200_000,
        uncovered=300_000,
        released=600_000,
        free=5_000_000,
    )

    rows = format.money_available_card(view).splitlines()

    assert _signed_cents(rows[1]) + sum(_signed_cents(row) for row in rows[2:-1]) == _signed_cents(rows[-1])

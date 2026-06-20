from quaestor.services import importer

HEADER = "date,type,payee,amount,currency,account,category,tags,notes"


def test_empty_csv_is_global_error(session):
    res = importer.import_csv(session, "")
    assert res.ok is False and res.inserted == 0
    assert res.errors and res.errors[0].line == 1


def test_wrong_header_is_global_error(session):
    res = importer.import_csv(session, "date,amount\n2026-06-01,100")
    assert res.ok is False and res.inserted == 0
    assert res.errors[0].line == 1
    assert "header" in res.errors[0].reason.lower()


def test_header_only_is_global_error(session):
    res = importer.import_csv(session, HEADER + "\n")
    assert res.ok is False and res.inserted == 0
    assert res.errors[0].line == 1


def test_dry_run_flag_is_echoed_on_global_error(session):
    res = importer.import_csv(session, "", dry_run=True)
    assert res.dry_run is True and res.ok is False


from datetime import date

from quaestor.domain.models import AccountType
from quaestor.services import accounts, categories, fx, transactions


def _row(date_="2026-06-01", type_="expense", payee="p", amount="100",
         currency="COP", account="Bank", category="Food", tags="", notes=""):
    return ",".join([date_, type_, payee, amount, currency, account, category, tags, notes])


def _csv(*rows):
    return HEADER + "\n" + "\n".join(rows) + "\n"


def _setup_master(session):
    accounts.create_account(session, "Bank", AccountType.debit, "COP", balance=10_000_000)
    categories.create_category(session, name="Food")


def test_valid_dry_run_inserts_nothing(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(amount="250")), dry_run=True)
    assert res.ok is True and res.inserted == 0 and res.dry_run is True
    assert res.errors == []
    assert transactions.list_transactions(session) == []


def test_invalid_date_reports_line_and_reason(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(date_="2026-13-40")), dry_run=True)
    assert res.ok is False
    assert res.errors[0].line == 2 and "date" in res.errors[0].reason


def test_invalid_type_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(type_="bogus")), dry_run=True)
    assert res.errors[0].line == 2 and "type" in res.errors[0].reason


def test_transfer_type_rejected(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(type_="transfer", category="")), dry_run=True)
    assert res.ok is False
    assert "transfer import not supported" in res.errors[0].reason


def test_non_positive_amount_rejected(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(amount="0")), dry_run=True)
    assert any("amount must be > 0" in e.reason for e in res.errors)


def test_non_numeric_amount_rejected(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(amount="abc")), dry_run=True)
    assert any("invalid amount" in e.reason for e in res.errors)


def test_unknown_account_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(account="Nope")), dry_run=True)
    assert any("account 'Nope' does not exist" in e.reason for e in res.errors)


def test_unknown_category_reported(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(category="Nope")), dry_run=True)
    assert any("category 'Nope' does not exist" in e.reason for e in res.errors)


def test_empty_category_allowed_for_expense(session):
    _setup_master(session)
    res = importer.import_csv(session, _csv(_row(category="")), dry_run=True)
    assert res.ok is True and res.errors == []


def test_currency_mismatch_with_account_reported(session):
    _setup_master(session)  # Bank is COP
    res = importer.import_csv(session, _csv(_row(currency="USD")), dry_run=True)
    assert any("does not match account" in e.reason for e in res.errors)


def test_usd_without_rate_reports_missing_rate(session):
    accounts.create_account(session, "Wallet", AccountType.debit, "USD", balance=0)
    categories.create_category(session, name="Food")
    res = importer.import_csv(session, _csv(_row(currency="USD", account="Wallet")), dry_run=True)
    assert any("no usd_cop rate" in e.reason for e in res.errors)


def test_usd_with_rate_validates(session):
    accounts.create_account(session, "Wallet", AccountType.debit, "USD", balance=0)
    categories.create_category(session, name="Food")
    fx.set_fx_rate(session, date(2026, 6, 1), 4000)
    res = importer.import_csv(session, _csv(_row(currency="USD", account="Wallet")), dry_run=True)
    assert res.ok is True and res.errors == []


def test_all_errors_accumulated_across_rows(session):
    _setup_master(session)
    bad_date = _row(date_="nope")
    bad_acct = _row(account="Ghost")
    res = importer.import_csv(session, _csv(bad_date, bad_acct), dry_run=True)
    lines = sorted(e.line for e in res.errors)
    assert lines == [2, 3]

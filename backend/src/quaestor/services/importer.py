"""Atomic bulk CSV importer (P5). Custom documented format, all-or-nothing.

Validate-first: every row is parsed/validated in memory; only when there are zero
errors does it insert (via P0 record_expense/record_income, source="import"). A
single bad row => nothing inserted. transfer rows are rejected in v1.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date as Date
from decimal import InvalidOperation

from sqlmodel import Session

from ..domain.errors import MissingRate
from ..domain.money import major_to_cents
from ..domain.report_types import ImportResult, RowError
from . import accounts as _accounts
from . import categories as _categories
from . import fx as _fx
from . import tags as _tags
from . import transactions as _tx

HEADER = ["date", "type", "payee", "amount", "currency", "account", "category", "tags", "notes"]
_VALID_TYPES = {"expense", "income", "transfer"}
_VALID_CURRENCIES = {"COP", "USD"}


def _global_error(reason: str, dry_run: bool) -> ImportResult:
    return ImportResult(
        ok=False, inserted=0, tags_created=[],
        errors=[RowError(line=1, reason=reason)], dry_run=dry_run,
    )


@dataclass
class _ValidRow:
    tx_type: str  # "expense" | "income" (transfer is rejected upstream)
    account_id: int
    amount_cents: int
    currency: str
    date: Date
    payee: str
    category_id: int | None
    tags: list[str]
    notes: str | None


def _validate_row(session, raw, line, acc_by_name, cat_by_name):
    """Accumulate every problem in a row. Returns ([], _ValidRow) only when valid."""
    if len(raw) != len(HEADER):
        return [RowError(line, f"expected {len(HEADER)} columns, got {len(raw)}")], None

    date_s, type_s, payee, amount_s, currency, account_s, category_s, tags_s, notes = (
        c.strip() for c in raw
    )
    errors: list[RowError] = []

    tx_type = type_s.lower()
    if tx_type not in _VALID_TYPES:
        errors.append(RowError(line, f"invalid type {type_s!r} (expected expense/income/transfer)"))
    elif tx_type == "transfer":
        errors.append(RowError(line, "transfer import not supported in v1"))

    date = None
    try:
        date = Date.fromisoformat(date_s)
    except ValueError:
        errors.append(RowError(line, f"invalid date {date_s!r} (expected YYYY-MM-DD)"))

    amount_cents = None
    try:
        amount_cents = major_to_cents(amount_s)
        if amount_cents <= 0:
            errors.append(RowError(line, "amount must be > 0"))
            amount_cents = None
    except (InvalidOperation, ValueError):
        errors.append(RowError(line, f"invalid amount {amount_s!r}"))

    if currency not in _VALID_CURRENCIES:
        errors.append(RowError(line, f"invalid currency {currency!r} (expected COP/USD)"))

    account = acc_by_name.get(account_s)
    if account is None:
        errors.append(RowError(line, f"account {account_s!r} does not exist"))
    elif currency in _VALID_CURRENCIES and currency != account.currency:
        errors.append(
            RowError(line, f"currency {currency} does not match account {account_s!r} ({account.currency})")
        )

    category_id = None
    if category_s:
        cat = cat_by_name.get(category_s)
        if cat is None:
            errors.append(RowError(line, f"category {category_s!r} does not exist"))
        else:
            category_id = cat.id

    if date is not None and currency == "USD":
        try:
            _fx.get_current_rate(session, date)
        except MissingRate:
            errors.append(RowError(line, f"no usd_cop rate for {date_s}"))

    tags = [t.strip() for t in tags_s.split(";") if t.strip()]

    if errors:
        return errors, None
    return [], _ValidRow(
        tx_type=tx_type, account_id=account.id, amount_cents=amount_cents,
        currency=currency, date=date, payee=payee, category_id=category_id,
        tags=tags, notes=notes or None,
    )


def import_csv(session: Session, content: str, *, dry_run: bool = False) -> ImportResult:
    """Import a custom-format CSV atomically. See module docstring for the contract.

    Returns an ImportResult; row problems are accumulated (never raised) so the
    caller sees every line at once.
    """
    try:
        rows = list(csv.reader(io.StringIO(content)))
    except csv.Error:
        return _global_error("malformed CSV", dry_run)
    if not rows:
        return _global_error("empty CSV", dry_run)
    header = [c.strip() for c in rows[0]]
    if header != HEADER:
        return _global_error(f"invalid header; expected: {','.join(HEADER)}", dry_run)
    data_rows = rows[1:]
    if not data_rows:
        return _global_error("no data rows", dry_run)

    acc_by_name = {a.name: a for a in _accounts.list_accounts(session)}  # excludes archived
    cat_by_name = {c.name: c for c in _categories.list_categories(session)}

    errors: list[RowError] = []
    valid: list[_ValidRow] = []
    for i, raw in enumerate(data_rows):
        line = i + 2  # header is line 1
        row_errors, vrow = _validate_row(session, raw, line, acc_by_name, cat_by_name)
        errors.extend(row_errors)
        if vrow is not None:
            valid.append(vrow)

    if errors:
        return ImportResult(ok=False, inserted=0, tags_created=[], errors=errors, dry_run=dry_run)

    if dry_run:
        return ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=True)

    existing = {t.name for t in _tags.list_tags(session)}
    new_tags = sorted({t for v in valid for t in v.tags if t not in existing})

    inserted_ids: list[int] = []
    try:
        for v in valid:
            if v.tx_type == "income":
                tx = _tx.record_income(
                    session, v.account_id, v.amount_cents, v.currency, v.date,
                    v.payee, category_id=v.category_id, notes=v.notes, source="import",
                )
            else:  # expense
                tx = _tx.record_expense(
                    session, v.account_id, v.amount_cents, v.currency, v.date,
                    v.payee, category_id=v.category_id, notes=v.notes, source="import",
                )
            inserted_ids.append(tx.id)
            if v.tags:
                _tags.tag_transaction(session, tx.id, v.tags)
    except Exception:
        # Unlikely (rows were pre-validated): compensate to keep all-or-nothing.
        for tx_id in reversed(inserted_ids):
            try:
                _tx.delete_transaction(session, tx_id)
            except Exception:
                pass
        return ImportResult(
            ok=False, inserted=0, tags_created=[],
            errors=[RowError(line=0, reason="commit failed; rolled back")], dry_run=False,
        )

    return ImportResult(
        ok=True, inserted=len(valid), tags_created=new_tags, errors=[], dry_run=False,
    )

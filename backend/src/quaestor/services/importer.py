"""Atomic bulk CSV importer (P5). Custom documented format, all-or-nothing.

Validate-first: every row is parsed/validated in memory; only when there are zero
errors does it insert (via P0 record_expense/record_income, source="import"). A
single bad row => nothing inserted. transfer rows are rejected in v1.
"""
from __future__ import annotations

import csv
import io

from sqlmodel import Session

from ..domain.report_types import ImportResult, RowError

HEADER = ["date", "type", "payee", "amount", "currency", "account", "category", "tags", "notes"]


def _global_error(reason: str, dry_run: bool) -> ImportResult:
    return ImportResult(
        ok=False, inserted=0, tags_created=[],
        errors=[RowError(line=1, reason=reason)], dry_run=dry_run,
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

    # Row validation + insertion arrive in Task 10/11.
    return ImportResult(ok=True, inserted=0, tags_created=[], errors=[], dry_run=dry_run)

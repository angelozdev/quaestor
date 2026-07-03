"""One-off cleanup script for stale planned transactions.

Purpose:
    The new outstanding-queue fix (ADR-0023) surfaces ALL planned transactions
    with date < today in the "overdue" bucket. Recurring occurrences that
    accumulated without confirmation can leave dozens of stale planned rows
    from past months. This script finds and optionally skips them.

Safety model:
    - Default mode = dry-run. Lists affected transactions. NO destructive action.
    - --apply flag = actually mark them as skipped. Requires explicit opt-in via
      an interactive confirmation prompt ("apply").

Database:
    - Always reads from QUAESTOR_DB environment variable (defaults to the dev DB
      at .dev-data/quaestor.db when running locally).
    - NEVER automatically points at production. To run against production you
      must explicitly set QUAESTOR_DB before invoking the script (see below).

How to run against production:
    Option A — via the API container (Tailscale-only per ADR-0011):
        1. SSH into the prod API container via Tailscale.
        2. Copy this script to the container (or pipe it in).
        3. Set QUAESTOR_DB to the prod DB path and run:
           QUAESTOR_DB=sqlite:///<prod-db-path> python scripts/cleanup_stale_planned.py --days 30 --apply

    Option B — direct production DB path (NOT recommended; prefer the container):
        1. Temporarily set QUAESTOR_DB to the prod SQLite path:
           QUAESTOR_DB=sqlite:///<prod-db-path> python scripts/cleanup_stale_planned.py --days 30 --apply

    Option C — copy the script into the container and run it there:
        1. docker cp scripts/cleanup_stale_planned.py <container>:/app/scripts/
        2. docker exec <container> sh -c 'QUAESTOR_DB=sqlite:///quaestor.db python scripts/cleanup_stale_planned.py --days 30 --apply'

CLI args:
    --days N   Number of days threshold. Transactions with date < today - N days
               are considered stale. Default: 30.
    --apply    Must be passed to actually skip the transactions. Without this flag
               the script runs in dry-run mode and prints the list only.
    --help     Show this help message.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from quaestor.db import engine
from quaestor.domain.models import Transaction, TxStatus
from quaestor.mcp.format import money
from quaestor.services import planned
from sqlmodel import Session, select


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List and optionally skip stale planned transactions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Dry-run, list planned transactions older than 30 days:\n"
            "  uv run python scripts/cleanup_stale_planned.py --days 30\n\n"
            "  # Dry-run, list planned transactions older than 7 days:\n"
            "  uv run python scripts/cleanup_stale_planned.py --days 7\n\n"
            "  # Actually skip them (prompts for confirmation first):\n"
            "  uv run python scripts/cleanup_stale_planned.py --days 30 --apply\n"
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        metavar="N",
        help="Transactions with date < today - N days are considered stale. Default: 30.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually skip the transactions. Without this flag the script runs in dry-run mode.",
    )
    return parser


def _stale_planned_query(session: Session, threshold_date: date) -> list[Transaction]:
    return list(
        session.exec(
            select(Transaction)
            .where(Transaction.status == TxStatus.planned)
            .where(Transaction.date < threshold_date)
            .order_by(Transaction.date.asc())
        )
    )


def _print_table(transactions: list[Transaction], today: date) -> None:
    if not transactions:
        print("No stale planned transactions found.")
        return
    header = f"{'ID':>4} | {'Payee':<25} | {'Due Date':>10} | {'Days Overdue':>12} | {'Amount':>15}"
    separator = "-" * len(header)
    print(header)
    print(separator)
    total = 0
    for tx in transactions:
        days_overdue = (today - tx.date).days
        total += tx.to_base
        print(
            f"{tx.id:>4} | {tx.payee[:25]:<25} | {tx.date.isoformat():>10} | "
            f"{days_overdue:>12} | {money(tx.amount, tx.currency):>15}"
        )
    print(separator)
    print(f"Would skip {len(transactions)} transaction(s) totaling {money(total, 'COP')}")


def _confirm_apply(count: int) -> bool:
    try:
        response = input(f"\nType 'apply' to confirm skipping {count} transaction(s): ")
        return response.strip().lower() == "apply"
    except (EOFError, KeyboardInterrupt):
        return False


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.days < 0:
        print("Error: --days must be a non-negative integer.", file=sys.stderr)
        sys.exit(1)

    threshold_date = date.today() - timedelta(days=args.days)
    today = date.today()

    if not args.apply:
        print(f"[DRY-RUN] threshold date: {threshold_date.isoformat()} (today - {args.days} days)\n")

    with Session(engine) as session:
        transactions = _stale_planned_query(session, threshold_date)

        if not args.apply:
            _print_table(transactions, today)
            print("\nDry-run complete. Re-run with --apply to skip these transactions.")
            return

        if not transactions:
            print("No stale planned transactions found. Nothing to do.")
            return

        _print_table(transactions, today)

        if not _confirm_apply(len(transactions)):
            print("\nAborted. No changes were made.")
            sys.exit(0)

        succeeded = 0
        failed = 0
        for tx in transactions:
            try:
                planned.skip_payment(session, tx.id)
                succeeded += 1
                print(f"Skipped tx {tx.id} ({tx.payee}, {tx.date.isoformat()})")
            except Exception as e:
                failed += 1
                print(f"ERROR skipping tx {tx.id}: {e}", file=sys.stderr)

        print(f"\nSkipped {succeeded} transaction(s) ({failed} failed).")


if __name__ == "__main__":
    dev_db_path = Path(__file__).parent.parent / ".dev-data" / "quaestor.db"
    if not os.environ.get("QUAESTOR_DB") and dev_db_path.exists():
        os.environ["QUAESTOR_DB"] = f"sqlite:///{dev_db_path}"

    main()

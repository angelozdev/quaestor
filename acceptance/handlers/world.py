"""Per-scenario state for acceptance runs.

Every scenario gets a fresh in-memory SQLite database migrated to head via
``quaestor.db.init_db`` — full state isolation between scenarios. All step
handlers read/write only through this object.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

from sqlmodel import Session

from quaestor.db import init_db, make_engine

MISSING_ID = 999_999_321


class World:
    """Scenario-scoped state: one engine, one session, and step scratchpad."""

    def __init__(self) -> None:
        self.engine = make_engine(memory=True)
        init_db(self.engine)
        self.session: Session = Session(self.engine)

        self.today: date = date.today()
        # Any day safely inside the previous calendar month.
        self.previous_month_day: date = (
            self.today.replace(day=1) - timedelta(days=1)
        ).replace(day=15)

        # name -> account id (accounts created by Given steps)
        self.accounts: dict[str, int] = {}
        # currency -> account id (implicit accounts for "a recorded expense of ...")
        self.default_accounts: dict[str, int] = {}
        # category name -> id
        self.categories: dict[str, int] = {}

        self.last_expense_id: int | None = None
        self.viewed_cop_cents: int | None = None
        self.report = None            # MonthlyReport | None
        self.report_month: str | None = None
        self.budget_lines = None      # list[BudgetLine] | None
        self.transfer_legs = None     # (leg_from, leg_to) | None
        self.implied_rate = None      # Decimal | None
        self.implied_rate_error: Exception | None = None
        self.app_cop_cents: int | None = None   # REST surface (AC-13)
        self.mcp_cop_major = None                # Decimal from MCP text (AC-13)

        self.expense_ids: list[int] = []
        self.tx_view = None
        self.filtered_rows = None
        self.viewed_leg = None
        self.app_payees: list[str] | None = None
        self.assistant_payees: list[str] | None = None
        self.denied_status: int | None = None

        # Migration scenario (AC-12)
        self.alembic_cfg = None
        self.migration_expected: list[tuple[str, int, str]] = []

        # Error stream: When-steps capture domain failures here so Then-steps
        # can either consume them ("is rejected") or fail loudly with them.
        self.errors: list[Exception] = []
        self.last_error: Exception | None = None

    def account_id_or_missing(self, name: str) -> int:
        """Id of a named account, or a nonexistent id when it was never created."""
        return self.accounts.get(name, MISSING_ID)

    # ------------------------------------------------------------- errors

    def attempt(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run an action, capturing any exception into the error stream."""
        self.last_error = None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — inspected by Then-steps
            self.errors.append(exc)
            self.last_error = exc
            return None

    def require_clean(self, what: str) -> None:
        """Fail if any earlier action error was never consumed by a Then."""
        if self.errors:
            details = "; ".join(
                f"{type(e).__name__}: {e}" for e in self.errors
            )
            raise AssertionError(
                f"{what}: a preceding action failed — {details}"
            )

    def consume_rejection(self, expected: tuple[type, ...], what: str) -> Exception:
        """Assert the last action was rejected with an expected error type."""
        err = self.last_error
        if err is None:
            raise AssertionError(
                f"{what}: expected the action to be rejected, but it succeeded"
            )
        if not isinstance(err, expected):
            names = " | ".join(t.__name__ for t in expected)
            raise AssertionError(
                f"{what}: expected {names}, got {type(err).__name__}: {err}"
            )
        self.errors.remove(err)
        return err

    # -------------------------------------------------------------- engine

    def replace_engine(self, engine) -> None:
        """Swap the scenario's database (used by the migration scenario)."""
        self.session.close()
        self.engine.dispose()
        self.engine = engine
        self.session = Session(engine)

    def reopen_session(self) -> None:
        self.session.close()
        self.session = Session(self.engine)

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()

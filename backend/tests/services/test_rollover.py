from datetime import date

import pytest
from quaestor.services import rollover


def test_close_month_runs_hooks_in_registration_order(session):
    calls = []
    def h1(period, s):
        return calls.append(("h1", period))
    def h2(period, s):
        return calls.append(("h2", period))
    rollover.register_rollover_hook(h1)
    rollover.register_rollover_hook(h2)
    try:
        rollover.close_month(session, "2026-06")
    finally:
        rollover.ROLLOVER_HOOKS.remove(h1)
        rollover.ROLLOVER_HOOKS.remove(h2)
    assert calls == [("h1", "2026-06"), ("h2", "2026-06")]


def test_close_month_with_no_hooks_is_a_noop(session):
    rollover.close_month(session, "2026-06")  # must not raise


def test_close_month_atomicity_rolls_back_on_hook_failure(session):
    # Hooks must write DIRECTLY to the session (never call committing services),
    # so a later hook's failure rolls back the whole close.
    from quaestor.domain.models import Account, AccountType
    from quaestor.services import accounts

    def good(period, s):
        s.add(Account(name="Created by hook", type=AccountType.debit, currency="COP", balance=0))
        s.flush()  # visible within the transaction, not committed

    def bad(period, s):
        raise RuntimeError("hook blew up")

    rollover.register_rollover_hook(good)
    rollover.register_rollover_hook(bad)
    try:
        with pytest.raises(RuntimeError):
            rollover.close_month(session, "2026-06")
    finally:
        rollover.ROLLOVER_HOOKS.remove(good)
        rollover.ROLLOVER_HOOKS.remove(bad)
    # full rollback: the account added by `good` is gone
    assert accounts.list_accounts(session) == []


def test_close_month_idempotent_with_self_keyed_hook(session):
    # a hook idempotent by its own (key, period) must not duplicate on re-run
    state = {"created": set()}

    def once_per_period(period, s):
        if period in state["created"]:
            return
        state["created"].add(period)

    rollover.register_rollover_hook(once_per_period)
    try:
        rollover.close_month(session, "2026-06")
        rollover.close_month(session, "2026-06")
        rollover.close_month(session, "2026-06")
    finally:
        rollover.ROLLOVER_HOOKS.remove(once_per_period)
    assert state["created"] == {"2026-06"}


def test_ensure_month_closed_uses_current_calendar_month(session):
    seen = []
    rollover.register_rollover_hook(lambda period, s: seen.append(period))
    try:
        rollover.ensure_month_closed(session, date(2026, 6, 19))
    finally:
        rollover.ROLLOVER_HOOKS.pop()
    assert seen == ["2026-06"]

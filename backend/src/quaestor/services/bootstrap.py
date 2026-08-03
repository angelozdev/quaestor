"""Seam registration: wire cross-feature hooks in one place.

Called by db.init_db so the API (lifespan) and the MCP server share one wiring.
Idempotent: re-running init_db (e.g. once per test) never duplicates a hook.

Keeping the wiring here is what lets each service stay unaware of the others:
`transactions.py` never learns what a recurring item is, and `occurrences.py`
never imports the transaction service.
"""

from __future__ import annotations


def register_goal_hooks() -> None:
    from .goals import propose_goal_contributions, record_confirmed_contribution
    from .planned import POST_CONFIRM_HOOKS, register_post_confirm_hook
    from .rollover import ROLLOVER_HOOKS, register_rollover_hook

    if propose_goal_contributions not in ROLLOVER_HOOKS:
        register_rollover_hook(propose_goal_contributions)
    if record_confirmed_contribution not in POST_CONFIRM_HOOKS:
        register_post_confirm_hook(record_confirmed_contribution)


def register_recurring_hooks() -> None:
    from .occurrences import close_date_of_deleted_charge
    from .transactions import PRE_DELETE_HOOKS, register_pre_delete_hook

    if close_date_of_deleted_charge not in PRE_DELETE_HOOKS:
        register_pre_delete_hook(close_date_of_deleted_charge)

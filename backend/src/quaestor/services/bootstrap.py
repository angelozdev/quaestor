"""Seam registration: wire cross-feature hooks in one place.

Called by db.init_db so the API (lifespan) and the MCP server share one wiring.
Idempotent: re-running init_db (e.g. once per test) never duplicates a hook.

Keeping the wiring here is what lets each service stay unaware of the others:
`transactions.py` never learns what a recurring item is, and `occurrences.py`
never imports the transaction service.
"""

from __future__ import annotations


def register_recurring_hooks() -> None:
    from .occurrences import close_date_of_deleted_charge
    from .transactions import PRE_DELETE_HOOKS, register_pre_delete_hook

    if close_date_of_deleted_charge not in PRE_DELETE_HOOKS:
        register_pre_delete_hook(close_date_of_deleted_charge)

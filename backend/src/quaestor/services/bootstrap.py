"""Seam registration: wire cross-feature hooks in one place.

Called by db.init_db so the API (lifespan) and the MCP server share one wiring.
Idempotent: re-running init_db (e.g. once per test) never duplicates a hook.

Keeping the wiring here is what keeps the dependency one-way: `occurrences.py`
never imports the transaction service, so deletion reaches it through a hook
rather than an import. The reverse edge is a plain one — since a movement may
name the charge and the turn it settled (ADR-0057, ADR-0058), `transactions.py`
does know what a recurring item is and calls `occurrences` directly.
"""

from __future__ import annotations


def register_recurring_hooks() -> None:
    from .occurrences import close_date_of_deleted_charge
    from .transactions import PRE_DELETE_HOOKS, register_pre_delete_hook

    if close_date_of_deleted_charge not in PRE_DELETE_HOOKS:
        register_pre_delete_hook(close_date_of_deleted_charge)

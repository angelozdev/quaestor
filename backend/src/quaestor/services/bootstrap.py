"""P4 seam registration: wire goal hooks into P3's rollover/post-confirm seams.

Called by db.init_db so the API (lifespan) and the MCP server share one wiring.
Idempotent: re-running init_db (e.g. once per test) never duplicates a hook.
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

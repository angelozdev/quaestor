"""Tool tier policy (QUA-LLM06-01).

Every registered MCP tool must be classified into exactly one tier, and
the LLM-facing tool list must never include a `WRITE_DESTRUCTIVE` tool.
Unknown names default to `WRITE_DESTRUCTIVE` (deny by default) so a new
tool added without an entry in the registry is unreachable by the LLM
until explicitly classified.
"""
from __future__ import annotations

from collections import Counter

import pytest

from quaestor.chat.mcp.schema import filter_for_llm
from quaestor.mcp.registry import (
    LLM_ALLOWED_TOOLS,
    ToolTier,
    tool_tier,
)


_KNOWN_TOOL_NAMES: list[str] = (
    [
        "record_expense",
        "record_income",
        "transfer",
        "set_fx_rate",
        "list_transactions",
        "get_fx_rate",
        "list_accounts",
        "list_categories",
        "list_tags",
        "create_recurring",
        "list_recurring",
        "plan_payment",
        "confirm_payment",
        "skip_payment",
        "skip_recurring",
        "to_pay",
        "update_recurring",
        "archive_recurring",
        "assign_budget",
        "create_goal",
        "update_goal",
        "contribute_goal",
        "pause_goal",
        "restore_goal",
        "create_account",
        "update_account",
        "archive_account",
        "restore_account",
        "get_account",
        "create_category",
        "update_category",
        "archive_category",
        "restore_category",
        "get_category",
        "create_category_group",
        "update_category_group",
        "archive_category_group",
        "restore_category_group",
        "create_tag",
        "update_tag",
        "delete_tag",
        "get_transaction",
        "update_transaction",
        "delete_transaction",
        "get_settings",
        "update_settings",
        "list_budgets",
        "safe_to_spend",
        "list_goals",
        "goals_progress",
        "monthly_report",
        "restore_recurring",
    ]
)


def test_every_known_tool_classified_with_no_duplicates():
    classifications = [tool_tier(n) for n in _KNOWN_TOOL_NAMES]
    counts = Counter(c.value for c in classifications)
    assert counts["read"] >= 15
    assert counts["write_safe"] >= 10
    assert counts["write_destructive"] >= 20


def test_destructive_tools_are_not_in_llm_allowed():
    for name in [
        "transfer",
        "delete_transaction",
        "delete_tag",
        "update_settings",
        "archive_account",
        "archive_category",
        "archive_category_group",
        "archive_recurring",
        "update_transaction",
        "pause_goal",
        "skip_payment",
        "confirm_payment",
    ]:
        assert name not in LLM_ALLOWED_TOOLS, f"{name} must be hidden from LLM"
        assert tool_tier(name) == ToolTier.WRITE_DESTRUCTIVE


def test_read_only_tools_are_in_llm_allowed():
    for name in [
        "list_transactions",
        "list_accounts",
        "list_categories",
        "list_tags",
        "monthly_report",
        "goals_progress",
        "safe_to_spend",
        "list_budgets",
    ]:
        assert name in LLM_ALLOWED_TOOLS, f"{name} must be reachable by LLM"
        assert tool_tier(name) == ToolTier.READ


def test_write_safe_tools_are_in_llm_allowed():
    for name in [
        "record_expense",
        "record_income",
        "create_account",
        "create_category",
        "create_tag",
        "create_goal",
    ]:
        assert name in LLM_ALLOWED_TOOLS, f"{name} must be reachable by LLM"
        assert tool_tier(name) == ToolTier.WRITE_SAFE


def test_unknown_tool_defaults_to_destructive():
    assert tool_tier("never_registered") == ToolTier.WRITE_DESTRUCTIVE
    assert tool_tier("") == ToolTier.WRITE_DESTRUCTIVE


def test_filter_for_llm_keeps_only_allowed_tools():
    tools = [
        {"function": {"name": "list_transactions"}},
        {"function": {"name": "transfer"}},
        {"function": {"name": "delete_transaction"}},
        {"function": {"name": "record_expense"}},
        {"function": {"name": "monthly_report"}},
    ]
    out = filter_for_llm(tools, LLM_ALLOWED_TOOLS)
    names = {t["function"]["name"] for t in out}
    assert names == {"list_transactions", "record_expense", "monthly_report"}


def test_filter_for_llm_with_empty_allowed_drops_everything():
    tools = [
        {"function": {"name": "list_transactions"}},
        {"function": {"name": "record_expense"}},
    ]
    assert filter_for_llm(tools, frozenset()) == []


def test_filter_for_llm_handles_malformed_entries_safely():
    """If a tool entry is missing the `function` block (defensive), the
    filter must not raise — it should drop the entry."""
    tools = [
        {"function": {"name": "list_transactions"}},
        {"description": "missing function block"},
        {},
        {"function": {}},
    ]
    assert filter_for_llm(tools, frozenset({"list_transactions"})) == [
        {"function": {"name": "list_transactions"}}
    ]


def test_tier_sets_are_disjoint():
    from quaestor.mcp.registry import (
        _READ_ONLY_TOOLS,
        _WRITE_SAFE_TOOLS,
        _WRITE_DESTRUCTIVE_TOOLS,
    )

    assert _READ_ONLY_TOOLS.isdisjoint(_WRITE_SAFE_TOOLS)
    assert _READ_ONLY_TOOLS.isdisjoint(_WRITE_DESTRUCTIVE_TOOLS)
    assert _WRITE_SAFE_TOOLS.isdisjoint(_WRITE_DESTRUCTIVE_TOOLS)


def test_every_known_tool_is_in_some_tier_set():
    """Catches the failure mode where someone adds a new tool to the
    registry without classifying it (the registry would then forget it
    from the tier sets, silently leaving it unreachable)."""
    from quaestor.mcp.registry import (
        _READ_ONLY_TOOLS,
        _WRITE_SAFE_TOOLS,
        _WRITE_DESTRUCTIVE_TOOLS,
    )

    union = _READ_ONLY_TOOLS | _WRITE_SAFE_TOOLS | _WRITE_DESTRUCTIVE_TOOLS
    missing = set(_KNOWN_TOOL_NAMES) - union
    assert not missing, f"tools without a tier: {sorted(missing)}"

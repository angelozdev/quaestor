"""Sanity tests for the extracted build_mcp() factory."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from quaestor.mcp.builder import build_mcp


def test_build_mcp_returns_fastmcp_instance():
    mcp = build_mcp()
    assert isinstance(mcp, FastMCP)


def test_build_mcp_registers_all_expected_tools():
    mcp = build_mcp()
    expected_names = {
        # core
        "record_expense",
        "record_income",
        "transfer",
        "set_fx_rate",
        "list_transactions",
        "get_fx_rate",
        "list_accounts",
        "list_categories",
        "list_tags",
        # temporal
        "create_recurring",
        "list_recurring",
        "plan_payment",
        "confirm_payment",
        "skip_payment",
        "restore_payment",
        "skip_recurring",
        "pending_recurring_dates",
        "accept_recurring_dates",
        "decline_recurring_dates",
        "to_pay",
        "update_recurring",
        "archive_recurring",
        # planning
        "assign_budget",
        "create_goal",
        "update_goal",
        "contribute_goal",
        "pause_goal",
        "restore_goal",
        # masters/accounts
        "create_account",
        "update_account",
        "archive_account",
        "restore_account",
        "get_account",
        # masters/categories
        "create_category",
        "update_category",
        "archive_category",
        "restore_category",
        "get_category",
        # masters/category_groups
        "create_category_group",
        "update_category_group",
        "archive_category_group",
        "restore_category_group",
        # masters/tags
        "create_tag",
        "update_tag",
        "delete_tag",
        # masters/transactions
        "get_transaction",
        "update_transaction",
        "delete_transaction",
        # settings
        "get_settings",
        "update_settings",
        # budgets_reads
        "list_budgets",
        "safe_to_spend",
        # goals_reads
        "list_goals",
        "goals_progress",
        # reports
        "monthly_report",
        # recurring_restore
        "restore_recurring",
    }
    registered = {t.name for t in mcp._tool_manager._tools.values()}
    missing = expected_names - registered
    extra = registered - expected_names
    assert not missing, f"missing tools after build_mcp(): {sorted(missing)}"
    assert not extra, f"extra tools not in expected_names (update expected_names): {sorted(extra)}"

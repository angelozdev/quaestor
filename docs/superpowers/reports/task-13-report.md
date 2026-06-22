# Task 13 Report — Wire all parity-gap tools into the MCP registry

## Status
DONE

## Files modified
- `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/registry.py` — added 10 new tool-name tuples, 10 new `register_*_tools(mcp)` functions, swapped `DeleteRecurringInput` for `ArchiveRecurringInput`, renamed `delete_recurring` decorator to `archive_recurring`.
- `/Users/angelozdev/me/quaestor/backend/src/quaestor/mcp/server.py` — extended `from .registry import (...)` and called all 10 new register functions in `build_mcp()`.
- `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_registry.py` — added 10 new `test_register_*` functions plus `test_build_mcp_registers_every_new_group`; imported `server` module.
- `/Users/angelozdev/me/quaestor/backend/tests/mcp/test_server.py` — appended `test_build_mcp_exposes_all_fifty_two_tools` smoke test.

## Commit
- SHA: `430c36c`
- Subject: `feat(backend): wire all parity-gap tools into mcp registry (ADR-0009)`

## Test Evidence
- MCP suite (`uv run python -m pytest tests/mcp/ -v`): **138 passed, 1 warning in 0.71s** — all green.
- Full backend suite (`uv run python -m pytest -v`): **490 passed, 1 warning in 3.48s** — all green (API + domain + MCP).
- 52-tool count (`test_build_mcp_exposes_all_fifty_two_tools`): PASSED.
- Independent sanity `len({t.name for t in asyncio.run(build_mcp().list_tools())})` = **52**.

## Self-Review Findings
- All imports resolved cleanly — no `DeleteRecurringInput` references remain in registry/server.
- `archive_recurring` is exposed, `delete_recurring` is not (asserted by `test_build_mcp_registers_every_new_group`).
- 10 new tool-name tuples + 10 register functions line up 1:1 with the spec.
- `test_registered_tool_runs_against_db_engine` continues to work (uses `monkeypatch` + `engine` fixtures, both available from `tests/mcp/conftest.py`).
- The 52-tool count was independently verified via a CLI smoke before writing the assertion.

## Concerns
None. Total tool count matches ADR-0009 spec exactly; no duplicates detected.
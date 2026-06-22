# MCP Parity Gap Closure — Design

**Date:** 2026-06-21
**Status:** Draft (awaiting user review)
**Related ADRs:** [0006-goals-and-budgets-write-api-with-mcp-parity](../adr/0006-goals-and-budgets-write-api-with-mcp-parity.md), [0005-soft-delete-and-restore-as-the-uniform-lifecycle](../adr/0005-soft-delete-and-restore-as-the-uniform-lifecycle-for-goals-recurring-and-masters.md)
**Related specs:** [2026-06-16-P2-mcp-design](./2026-06-16-P2-mcp-design.md), [2026-06-21-P6-phase2-management-crud-design](./2026-06-21-P6-phase2-management-crud-design.md)

## Goal

Close the existing parity gap between the FastAPI backend and the MCP server. The backend exposes ~52 HTTP endpoints; the MCP server exposes 24 tools. This design adds the missing 28 tools so that any capability reachable via the HTTP API is also reachable via MCP, honoring ADR-0006's "every new HTTP write ships a sibling MCP tool."

Two HTTP endpoints are deliberately excluded (see [Exclusions](#exclusions)).

## Non-Goals

- Codegen from OpenAPI (deferred to a follow-up ADR).
- Vertical-slice rollout (one entity per iteration). This change ships all 28 tools together.
- HTTP-side changes (no new routes, no schema changes).
- Frontend changes.
- New auth mechanisms (bearer token unchanged).

## Exclusions

| Endpoint | Reason |
|---|---|
| `POST /api/rollover` | Scheduler-only trigger per ADR-017. Not exposed to agents. |
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` | MCP authenticates via bearer token; password login lives behind the frontend cookie session. By design. |

## Scope

28 new MCP tools + 1 rename (`delete_recurring` → `archive_recurring`, no deprecation shim).

### Masters CRUD (17 tools)

Per-entity shape (mirrors what the backend exposes):

| Entity | Tools | Count |
|---|---|---|
| accounts | `create_account`, `update_account`, `archive_account`, `restore_account`, `get_account` | 5 |
| categories | `create_category`, `update_category`, `archive_category`, `restore_category`, `get_category` | 5 |
| category-groups | `create_category_group`, `update_category_group`, `archive_category_group`, `restore_category_group` | 4 |
| tags | `create_tag`, `update_tag`, `delete_tag` | 3 |

Notes:
- `archive_*` performs soft-delete (`archived=true`); reversible via `restore_*` (idempotent no-op on already-archived).
- `delete_tag` is hard-delete (no archive per ADR-0005); the verb stays `delete` because the lifecycle differs from masters.
- `category-groups` has no `get_*` because the backend has no `GET /api/category-groups/{id}` route. MCP mirrors that gap.
- `tags` has no `archive_tag` / `restore_tag` because tags are hard-deleted (no `archived` field).

### Transactions writes (3 tools)

- `get_transaction(tx_id)` — read by id.
- `update_transaction(tx_id, ...)` — partial update of payee/notes/category_id/date (mirrors `PATCH /api/transactions/{tx_id}`).
- `delete_transaction(tx_id)` — hard-delete per API (`DELETE` returns 204 with no archive).

### Settings (2 tools)

- `get_settings()` — returns full `SettingsOut`.
- `update_settings(...)` — partial update. Notably enables the agent to set `default_source_account_id`, which is required by `contribute_goal`.

### Budgets reads (2 tools)

- `list_budgets(month=YYYY-MM)` — mirrors `GET /api/budgets?month=`.
- `safe_to_spend(month=YYYY-MM)` — mirrors `GET /api/budgets/safe-to-spend?month=`.

### Recurring restore + rename (1 new tool, 1 rename)

- `restore_recurring(recurring_id)` — mirrors `POST /api/recurring/{id}/restore`.
- `delete_recurring` → `archive_recurring` rename. No deprecation shim — direct rename, per user instruction (no other consumers exist).

### Goals reads (2 tools)

- `list_goals()` — mirrors `GET /api/goals`.
- `goals_progress()` — mirrors `GET /api/goals/progress`.

### Reports (1 tool)

- `monthly_report(month=YYYY-MM)` — mirrors `GET /api/reports?month=`.

## Architecture

### Module layout

New files under `backend/src/quaestor/mcp/tools/`:

```
mcp/tools/
├── core.py              (existing — no changes)
├── temporal.py          (modify: rename delete_recurring → archive_recurring)
├── planning.py          (existing — no changes)
├── masters.py           (NEW)
├── transactions.py      (NEW)
├── settings.py          (NEW)
├── budgets_reads.py     (NEW)
├── goals_reads.py       (NEW)
├── reports.py           (NEW)
└── recurring_restore.py (NEW)
```

Each new module exports one `register_<feature>_tools(mcp)` function plus the Pydantic input models. Convention matches existing modules.

### Server registry

`backend/src/quaestor/mcp/server.py` gains:

- 7 new tool-name tuples: `MASTERS_TOOL_NAMES`, `TRANSACTIONS_TOOL_NAMES`, `SETTINGS_TOOL_NAMES`, `BUDGETS_READS_TOOL_NAMES`, `GOALS_READS_TOOL_NAMES`, `REPORTS_TOOL_NAMES`, `RECURRING_RESTORE_TOOL_NAMES`.
- 7 new `register_*_tools(mcp)` functions wired into `build_mcp()`.

The existing `test_server.py:assert CORE_TOOL_NAMES ⊂ registered_tools` invariant is preserved by appending new names to the same set; `test_registry.py` is extended to assert each new tuple is also a subset.

### Formatter additions

`backend/src/quaestor/mcp/format.py` gains:

- `account_card`, `category_card`, `category_group_card`, `tag_card`, `transaction_card`, `settings_card` — single-entity markdown blocks.
- `budgets_table`, `goals_table`, `goal_progress_table` — list-rendering tables (one new each; share `transactions_table` styling).
- `safe_to_spend_card`, `monthly_report_card` — composite cards with money breakdowns.
- `recurring_restored` — single-line confirmation.

All renderers use existing helpers (`money`, `cents_to_major`, `format.date_iso`).

## Components

### Tool shape (uniform)

```python
class CreateAccountInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["debit", "credit", "cash", "savings"]
    currency: str = "COP"
    initial_balance_cents: int = Field(0, ge=0)

@mcp.tool(name="create_account", description="Create a new account.")
def create_account(inp: CreateAccountInput) -> str:
    return _as_text(inp, lambda s: services.accounts.create(
        session=s,
        name=inp.name,
        type=inp.type,
        currency=inp.currency,
        initial_balance_cents=inp.initial_balance_cents,
    ))
```

Every tool follows this shape:

1. Pydantic input model named `<Verb><Noun>Input`.
2. `@mcp.tool(name=..., description="...")` decorator.
3. `_as_text` wrapper handles name resolution, session opening (inherited from registry), error mapping, and markdown rendering.
4. Calls exactly one service function. No DB access from the tool.

### Name resolution

Inputs accept readable names (`account="Bancolombia"`, `category="Groceries"`, `tag="travel"`) and resolve them via the existing helpers in `backend/src/quaestor/mcp/tools/core.py:101-118` (`_resolve_account`, `_resolve_category`). For tag-based filters (`list_transactions(tag=...)`) the existing `tag` resolver is reused. For masters updates/deletes/gets, a new helper `_resolve_account_by_name` (or equivalent) is added next to the existing helpers.

Resolution failure raises `NotFound` → `_as_text` renders "Account 'Bancolombia' not found. List accounts to see available names."

### Idempotency

- `archive_*` on already-archived → no-op success (mirrors API).
- `restore_*` on already-active → no-op success.
- `assign_budget(amount=0)` → unassign (existing behavior preserved).
- `delete_tag` is hard-delete; second call returns `NotFound`.

### State transitions

Per ADR-0005 and ADR-0006:

- Lifecycle state (`archived`, `active`, `status`) lives on the entity, never in PATCH payloads.
- MCP tools map cleanly:
  - `archive_*` → `DELETE /api/<entity>/{id}`.
  - `restore_*` → `POST /api/<entity>/{id}/restore`.
  - `pause_goal` → `DELETE /api/goals/{goal_id}` (already exists).
  - `restore_recurring` → `POST /api/recurring/{recurring_id}/restore`.

## Data Flow

```
JSON-RPC POST /mcp
  ↓
BearerAuthMiddleware  (mcp/auth.py — unchanged)
  ↓
FastMCP dispatcher     (mcp/server.py)
  ↓
@mcp.tool wrapper     (FastMCP parses inp against Pydantic model)
  ↓
mcp/tools/<file>.py::<tool_fn>(inp)
  ├─ name resolution:    _resolve_account/category (existing)
  ├─ session:            Session(db.engine)  — opened by registry wrapper
  ├─ service call:       services.<entity>.<verb>(session, **kwargs)
  ├─ format result:      format.<renderer>(result)
  └─ return str (markdown)
  ↓
JSON-RPC response { content: [{ type: "text", text: "..." }] }
```

## Error Handling

No new error machinery. `_as_text` (`tools/core.py:85-95`) and `format.domain_error_text` (`format.py:37-52`) already cover every error type the new tools can raise, because every new tool calls existing services that already raise typed `QuaestorError` subclasses.

### Mapping reference

| Service error | MCP text |
|---|---|
| `ValidationError` | "Invalid input: <reason>. <field>=<value> violates <rule>." |
| `MissingRate` | "No FX rate for <date>. Call `set_fx_rate` first." |
| `IllegalTransition` | "Cannot <verb> <entity> in state <state>." |
| `NotFound` | "<Entity> '<name>' not found. List <entities> to see available names." |
| `DuplicateName` | "<Entity> '<name>' already exists. Pick a different name." |
| `TransferImbalance` | "Transfer <amount> doesn't balance: <detail>." |
| `Unauthorized` | "Bearer token invalid or missing." |

### Edge cases

- `archive_account` on account with posted transactions → service raises `IllegalTransition`. MCP text explains + suggests transferring out first.
- `delete_tag` on tag in use → service raises `IllegalTransition`. MCP text lists affected transactions count.
- `update_settings(default_source_account_id=<archived>)` → service raises `ValidationError`.

### What does NOT change

- No stack traces surface to the agent.
- No retry logic on the MCP side (the LLM decides).
- Auth middleware untouched.

## Testing

### Pattern

In-memory SQLite (`make_engine(memory=True)` + `init_db`) + real service calls + markdown assertions. Identical to `tests/mcp/test_core_writes.py`.

### New test files

```
tests/mcp/
├── test_masters_writes.py        (happy paths — 1 per tool, ~17 tests)
├── test_masters_writes_errors.py (NotFound, ValidationError, DuplicateName, IllegalTransition)
├── test_transactions_writes.py   (get/update/delete — happy + constraint)
├── test_settings_writes.py       (get/update — happy + validation)
├── test_budgets_reads.py         (list + safe_to_spend — seeded fixtures)
├── test_goals_reads.py           (list + progress — seeded fixtures)
├── test_recurring_restore.py     (restore_recurring + archive_recurring rename)
└── test_reports.py               (monthly_report — seeded month)
```

### Per-tool asserts (minimum)

1. **Happy path** — tool returns markdown with key fields (`✅ Created`, money rendered, table rows present).
2. **NotFound** — input with non-existent name → text contains `"<Entity> '<name>' not found"`.
3. **Validation** — input violating Pydantic constraint (`gt=0`, `ge=0`, `Literal`) → text contains "Invalid input".
4. **State transition** — archive on already-archived returns success no-op; restore on already-active returns success no-op.
5. **Rename** — `test_recurring_restore.py` asserts `archive_recurring` is registered and `delete_recurring` is not (regression guard).

### Fixtures

Reuse `tests/mcp/conftest.py:engine, session, seeded`. Add:

- `seeded_with_tag` — single tag for tag-write tests.
- `seeded_with_budgets` — follows `tests/api/conftest.py` pattern; one category with assigned amount.
- `seeded_with_goal` — one defined goal with target + deadline for progress tests.

### Coverage target

~28 tools × 3 asserts minimum = ~84 tests across 8 files.

### What does NOT change

- `test_server.py` — existing subset assertion still passes.
- `test_auth.py` — unchanged.
- `test_format.py` — extended only for new renderer functions.
- No new E2E integration tests; the MCP↔HTTP parity is enforced by both adapters calling the same service.

## Implementation Plan (outline, not the plan)

The implementation plan will be produced by the `writing-plans` skill after this design is approved. Outline:

1. ADR-0009 written and committed (links this spec, codifies exclusions).
2. `format.py` — add renderers.
3. `mcp/tools/masters.py` + tests.
4. `mcp/tools/transactions.py` + tests.
5. `mcp/tools/settings.py` + tests.
6. `mcp/tools/budgets_reads.py` + tests.
7. `mcp/tools/goals_reads.py` + tests.
8. `mcp/tools/reports.py` + tests.
9. `mcp/tools/recurring_restore.py` + `temporal.py` rename + tests.
10. `server.py` — wire all new register functions; add new tool-name tuples.
11. `test_registry.py` — extend to assert all 7 new tuples ⊂ registered.
12. Update `.mcp.json` consumers / docs if any external listing exists (none known).

## Open Questions

None at design time. All architectural decisions were resolved during brainstorming.

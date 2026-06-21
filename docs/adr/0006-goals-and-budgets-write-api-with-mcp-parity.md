# 0006. Goals and budgets write API with MCP parity

- **Status:** accepted
- **Date:** 2026-06-21
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The goals and budgets domain logic is fully implemented and tested in the service
layer (`services/goals.py`, `services/budgets.py`) but reachable from **no external
write path** — neither HTTP nor MCP — only internally from reports and rollover.
P6 Phase 2 (`docs/superpowers/specs/2026-06-21-P6-phase2-management-crud-design.md`)
needs to expose create/edit/contribute/pause/restore for goals and assign/status
for budgets. What HTTP shape do these writes take, which verb does an idempotent
envelope assign use, and does the agent (MCP) get the same writes?

## Decision drivers

- ADR-008 / ADR-025: the agent stays a **co-equal write path**; the UI must not be
  the only way to do something the agent could reasonably do.
- The repo already has a REST convention (from `accounts`, `planned`,
  `transactions`, `tags`): collection `GET`/`POST`(201); item `GET`/`PATCH`/
  `DELETE`(204); **state transitions = `POST /{id}/<verb>`** (`confirm`, `skip`),
  with lifecycle state kept out of the `PATCH` body.
- Envelope assign is `set_budget(category, month, amount)` — an idempotent upsert
  keyed by `(category, month)`, not a create.
- MCP tools over these services are thin wrappers, so parity is cheap to add now
  and expensive to retrofit later.

## Considered options

1. **`POST /{id}/<verb>` for actions + `PUT /budgets` for assign + MCP parity.**
   `contribute`/`restore` mirror the existing `confirm`/`skip`; assign uses `PUT`
   (set-to-value); every new HTTP write gets a sibling MCP tool.
2. **All-POST, no new verb + MCP parity.** Assign is `POST /budgets` (upsert),
   avoiding `PUT` entirely for maximal sameness with the current repo.
3. **HTTP-only, defer MCP.** Build the routes for the UI now; add MCP tools for
   goals/budgets later as a separate effort.

## Decision outcome

Chosen option: **Option 1**, because it stays consistent with the established
`POST /{id}/<verb>` transition convention while using the semantically correct
verb for an idempotent set-to-value (`PUT`), and it honors the co-equal-agent
principle by shipping HTTP and MCP together over the same services. `PUT /budgets`
is the one deliberate new verb in the API; it is justified because assign is a
true idempotent upsert by composite key, where `PUT` is the textbook choice.

### Pros and cons of the options

**Option 1 — `POST /{id}/<verb>` + `PUT /budgets` + MCP parity**
- Good, because actions reuse the exact `confirm`/`skip` pattern reviewers know.
- Good, because `PUT` correctly signals idempotent assign (re-assign overwrites,
  `0` unassigns) — safe to retry.
- Good, because goals/budgets reach the UI and the agent in the same pass.
- Bad, because it introduces `PUT`, a verb the repo had not used before.

**Option 2 — all-POST, no new verb**
- Good, because maximal uniformity with today's repo (POST-only writes).
- Bad, because `POST` for an idempotent set-to-value is misleading (implies create;
  not safe to blind-retry as the same resource).

**Option 3 — HTTP-only, defer MCP**
- Good, because slightly less work in this phase.
- Bad, because it breaks the co-equal-agent principle (ADR-008/025): goals/budgets
  would be UI-only writes, and retrofitting MCP later duplicates the wiring.

## Consequences

- Good: a small, predictable surface — `contribute`/`restore` as `POST /{id}/<verb>`
  returning the affected Out; `PUT /budgets` returning the recomputed `BudgetLine`;
  `GET /goals` (entity) alongside the existing `GET /goals/progress` (computed).
- Good: the agent and the UI write through the same service functions, so records
  are identical (shared DB), no divergence.
- Bad / cost: one new verb (`PUT`) for future contributors to learn; MCP tools and
  their formatters must be kept in sync with the HTTP routes for each new write.
- `contribute` requires a configured default source account; absent → `422` with
  an actionable message pointing at `/settings`.

## Confirmation

- API tests assert the verbs and status codes: action `POST`s return `200`/`201`,
  `PUT /budgets` is idempotent (re-assign overwrites, returns the recomputed line),
  `GET /goals` returns entities including `status`.
- MCP tests assert each new goals/budgets write tool exists and routes through the
  same service function as its HTTP sibling.
- Code-review checklist: any new goals/budgets/recurring HTTP write lands with its
  MCP counterpart in the same change.

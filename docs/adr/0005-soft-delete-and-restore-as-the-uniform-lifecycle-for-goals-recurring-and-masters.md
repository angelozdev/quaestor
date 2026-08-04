# 0005. Soft-delete and restore as the uniform lifecycle for goals, recurring, and masters

- **Status:** accepted
- **Date:** 2026-06-21
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** [0043 — A fund replaces the envelope and the goal, and its balance is derived](./0043-a-fund-replaces-the-envelope-and-the-goal-and-its-balance-is-derived.md) (the goal clause only — goals no longer exist and a fund is hard-deleted; soft-delete and restore for recurring items, accounts, categories, tags and groups remain in force)

## Context and problem statement

P6 Phase 2 (`docs/superpowers/specs/2026-06-21-P6-phase2-management-crud-design.md`)
graduates goals, recurring items, and the masters to full management UI, which
means the UI now needs a "delete" affordance for each. But goals accrue real
internal transfers (`GoalContribution` → `Transaction`) and recurring items
materialize real planned/posted occurrences (`Transaction`). What should "delete"
do when the entity has ledger history hanging off it, and is that action
reversible?

## Decision drivers

- The ledger is append-mostly: transactions are history and must not silently
  vanish (consistent with transfers already returning 422 on `DELETE`).
- Phase 1 already archives the masters (`archived=true`) but offers no way back;
  Phase 2 explicitly adds re-activation (ADR-025).
- The models already carry the needed state — `Goal.status` has a `paused` value,
  `RecurringItem.active` is a boolean, masters have `archived` — so a soft
  lifecycle needs no migration.
- One predictable mental model across entities is easier to build, test, and use
  than per-entity rules.

## Considered options

1. **Soft-delete + restore, uniform.** "Delete" deactivates (`Goal.status=paused`,
   `RecurringItem.active=false`, master `archived=true`); a dedicated
   `POST /{id}/restore` reverses it. History is always preserved.
2. **Hard delete with a guard.** Real row deletion, but `422` if the entity has
   posted contributions/occurrences; only never-materialized entities delete.
3. **Mixed per-entity semantics.** Recurring soft, masters soft (existing), goals
   hard-if-no-contributions-else-422.

## Decision outcome

Chosen option: **Option 1 — soft-delete + restore, uniform**, because it is the
only option that never rewrites the ledger, reuses columns that already exist
(zero migration), and gives one reversible lifecycle across all four areas. It
matches how budgeting tools (YNAB, Actual, Lunch Money, Monarch) treat scheduled
rules and goals: deleting the template/goal leaves the money it already moved
untouched.

### Pros and cons of the options

**Option 1 — soft-delete + restore, uniform**
- Good, because ledger history (contributions, occurrences) is always preserved.
- Good, because it reuses `status`/`active`/`archived` — no schema change.
- Good, because `restore` makes Phase-1 archiving reversible, closing ADR-025.
- Good, because a single pattern is uniform to implement and reason about.
- Bad, because deactivated rows accumulate; lists must filter by default and offer
  a "show inactive/archived" toggle.

**Option 2 — hard delete with a guard**
- Good, because truly unused entities leave no residue.
- Bad, because it splits behavior by history state (sometimes deletes, sometimes
  422) — confusing and harder to test.
- Bad, because it offers no path to hide a goal/recurring that *does* have history.

**Option 3 — mixed per-entity semantics**
- Good, because each entity gets its "natural" rule.
- Bad, because there is no uniform mental model; every screen behaves differently.

## Consequences

- Good: `DELETE` is reversible everywhere; "delete" confirmations state the soft
  semantics ("se puede restaurar"). No data is ever lost.
- Good: `restore` of an already-active/non-archived resource is an idempotent
  `200` no-op.
- Bad / cost: every list endpoint and table must filter out deactivated rows by
  default and expose a toggle to reveal them; soft-deleted rows grow unbounded.
- Note: tags are out of scope — they are hard-deleted (no `archived` column),
  nothing to restore.

## Confirmation

- Service tests assert delete sets the flag (not row removal) and `restore`
  reverses it, including the idempotent no-op path.
- API tests assert `DELETE` returns `204` and the entity still exists (filtered
  out of the default list, present with the "show inactive/archived" filter), and
  `POST /{id}/restore` returns `200`.
- Code-review checklist: no hard `session.delete(...)` is introduced for Goal,
  RecurringItem, Account, Category, or CategoryGroup.

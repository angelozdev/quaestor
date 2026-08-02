# Consolidation backlog — Quaestor

**Goal: every row all-✅.** A feature is fully ATDD-covered when its
`features/NNN-slug/` folder has `feature.md`, `acs.md`, `spec.md`
(+ `.build/spec.json` IR) and generated acceptance tests passing against the
code. Inventory discovered at onboarding (2026-07-28); triage order = tier
order below. Tracker type is `local`: this file + `features/` folders ARE the
tracker.

Execution mode per task: **local subagent** for now (`remote.ready: false` in
the manifest — flip after the one-time claude.ai setup, then these become
remote-dispatchable).

## Coverage table

Status: `done` = shipped & working; `parked` = dormant. Coverage columns start
all-❌ for every feature (no DAE artifacts existed before onboarding).

### Tier 1 — money path + differentiator (consolidate first)

| # | Feature | Status | feature.md | acs.md | spec.md | IR | acc. tests |
|---|---------|--------|-----------|--------|---------|----|-----------|
| 1 | budgets-envelopes + safe-to-spend | done | 🔜 | ❌ | ❌ | ❌ | ❌ |
| 2 | transactions-crud | done | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | planned-payments-to-pay | done | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | outstanding-queue-buckets | done | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5 | recurring-engine | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 6 | month-close-rollover | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 7 | goals | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 8 | goal-contribution-hooks | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 9 | monthly-report | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 10 | month-aggregate-read-path | done | ❌ | ❌ | ❌ | ❌ | ❌ |

### Tier 2 — agent-native + chat

| # | Feature | Status | feature.md | acs.md | spec.md | IR | acc. tests |
|---|---------|--------|-----------|--------|---------|----|-----------|
| 11 | mcp-tool-surface | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 12 | mcp-tool-tier-policy | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 13 | chat-coach | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 14 | chat-wire-adapter | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 15 | chat-output-sanitization | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 16 | markdown-rendering | done | ❌ | ❌ | ❌ | ❌ | ❌ |

### Tier 3 — security + platform

| # | Feature | Status | feature.md | acs.md | spec.md | IR | acc. tests |
|---|---------|--------|-----------|--------|---------|----|-----------|
| 17 | auth-session | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 18 | csrf-double-submit | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 19 | multi-currency-fx | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 20 | daily-scheduler-job | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 21 | db-migrations-postgres | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 22 | read-path-indexes | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 23 | local-only-deploy-posture | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 24 | bff-api-proxy | done | ❌ | ❌ | ❌ | ❌ | ❌ |

### Tier 4 — masters + UI infrastructure

| # | Feature | Status | feature.md | acs.md | spec.md | IR | acc. tests |
|---|---------|--------|-----------|--------|---------|----|-----------|
| 25 | accounts-masters | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 26 | categories-and-groups | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 27 | tags | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 28 | app-settings | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 29 | dashboard | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 30 | app-shell-navigation | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 31 | url-filter-state | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 32 | query-boundary-async-contract | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 33 | forms-and-validation | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 34 | design-system-ui-module | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 35 | dark-first-theming | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 36 | frontend-toolchain | done | ❌ | ❌ | ❌ | ❌ | ❌ |
| 37 | phase2-management-crud | done | ❌ | ❌ | ❌ | ❌ | ❌ |

### Tier 5 — anomalies / meta

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 38 | csv-importer | **deleted** | Dropped 2026-07-28 (human decision, see discussions.log): unwired, custom format ≠ bank exports. `services/importer.py` + tests + `ImportResult`/`RowError` types removed; recoverable from git history. |
| 39 | backup-restore | **dropped** | Dropped 2026-07-28: no code, stale Litestream/VPS runbooks — archival already queued as cleanup C3. |
| 40 | security-owasp-review | **dropped** | Dropped 2026-07-28: one-off doc, kept in docs/security/ as historical record. |
| 41 | adr-system | done | Meta-tooling (.claude/skills/adr). Low ATDD value. |
| 42 | mcp-http-removal | done | Historic deletion; covered by absence tests if ever needed. |
| 43 | vercel-chat-sse-best-practices | done | Code shipped; ADR-0018 still `proposed` → see cleanup C2. |

## Consolidation tasks (triage-priority order)

Each task = "bring feature X to full ATDD coverage" via the pipeline:
`feature-init` → `discover-acs` (reverse-engineer mode) → `atdd:atdd` →
pipeline generation → tests green. Bounded, one feature per task.

> **Reordered 2026-07-28** (portfolio review, discuss → features/003-sinking-funds):
> budgets-safe-to-spend and goals moved to the bottom — their formulas will be
> replaced by the parked `sinking-funds` redesign; writing acceptance tests for
> them now would be wasted work. Core-in-use features lead: transactions →
> planned → recurring.

1. ~~transactions-crud~~ ← **DONE 2026-07-31.** Full pipeline CP1.5→CP8, merged
   to `main` (merge commit `6ed8211`). 16 ACs, 64 acceptance scenarios,
   mutation 99.5%. Two defects found by the pipeline, not by users: three of
   four transfer creation paths never stored a leg direction (CP6), and
   single-leg goal-contribution proposals were undeletable (CP7). ADR-0032
   accepted, ADR-0033 proposed.
2. ~~planned-payments-to-pay~~ (+ outstanding-queue-buckets as one folder —
   same surface) ← **DONE 2026-08-02.** Full pipeline CP1→CP7, merged to
   `main` (merge commit `22c8303`). 24 ACs, 59 acceptance scenarios / 60
   executions, all green; mutation 87.0% on the changed functions of
   `services/planned.py` + `mcp/format.py` (95.2% excluding 6 documented
   equivalent mutants). Three defects the pipeline found, not users: planned
   income inflated the to-pay total (AC-15), the chat answer never stated the
   combined total (AC-24), and a mistaken skip was unrecoverable (AC-8).
   ADR-0034 accepted.
   - Followup, no ADR needed: three backend tests inventory the MCP tool
     registry by hand (`test_temporal.py` tool count, name lists in
     `test_builder.py` and `test_tool_tiers.py`), and
     `test_every_known_tool_is_in_some_tier_set` is vacuous for the same
     reason. Derive them from the registry constants when rows 11-12 are
     worked — `test_registry.py` already sets the precedent.
   - Latent gap, not reachable today: `data-table.tsx` gates the actions
     column on the declared action count but filters per row on `show`, so a
     row with every action hidden would open an empty dropdown. Trigger to
     fix: the first `show` predicate on `Editar`/`Eliminar`, or a page whose
     whole action set is conditional.
3. recurring-engine
4. month-close-rollover (+ goal-contribution-hooks — the rollover seam; note:
   rollover mechanics survive the sinking-funds redesign, but re-check scope
   when 003 unparks)
5. monthly-report (+ month-aggregate-read-path — shared read path)
6. mcp-tool-surface (+ mcp-tool-tier-policy)
7. chat-coach (+ chat-wire-adapter, chat-output-sanitization)
8. auth-session (+ csrf-double-submit)
9. multi-currency-fx (+ daily-scheduler-job)
10. db-migrations-postgres (+ read-path-indexes)
11. bff-api-proxy
12. markdown-rendering
13. Tier 4 features (masters + UI infra), one folder per row, in table order
14. goals ← **paused pending sinking-funds redesign (features/003-sinking-funds)**
15. budgets-envelopes + safe-to-spend ← **formalized at onboarding; paused pending
    sinking-funds redesign (features/003-sinking-funds)**
    - Open followup from fix `2026-07-31-phantom-budget-assignment`
      (gap: `missing_ac`): when this unpauses, land "archived and
      budget-excluded categories cannot hold an envelope" as an AC in
      `acs.md` and propagate it to `spec.md`. The rule is already enforced
      in `services/budgets.set_budget` and pinned by service-layer
      regression tests — only the AC/spec paper trail is missing.

## Cleanup tasks (doc/code drift — approved at triage)

- ~~C1. README: stop describing SQLite as default / Postgres as "future" — align with ADR-0024/0026.~~
  **Done 2026-07-29** — covered by the C6 README rewrite: SQLite now described
  as dev sandbox, Postgres is production (not "future"), obsolete
  SQLite→Postgres migration section removed.
- C2. Flip ADR-0018 status `proposed` → `accepted` (code shipped).
- C3. Re-scope or archive stale runbooks `restore-from-backup.md` and `deploy.md` (Litestream/VPS era).
- C4. Delete dead `frontend/components/phase2-banner.tsx`.
- C5. Remove stale `.pyc` files in `backend/tests/mcp/__pycache__` (deleted test modules).
- ~~C6. Align CHARTER.md §2, README and `.engineer/manifest.yml` prose with
  ADR-0030 (production DB is now the local Postgres container; Render = frozen
  standby; `.dev-data` SQLite is sandbox only). Charter edit needs human sign-off.~~
  **Done 2026-07-29** — charter §2 amendment signed off by Angelo; README
  rewritten (profiles, env files, backups section, obsolete SQLite→Postgres
  migration section removed); manifest path-override comments fixed. Note:
  README changes cover most of C1's surface too — re-check C1 scope
  (SQLite-as-default prose per ADR-0024) before working it.

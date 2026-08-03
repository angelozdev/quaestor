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
| 5 | recurring-engine | done | ✅ | ✅ | ✅ | ✅ | ✅ |
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
3. recurring-engine ← **in progress.** `features/007-recurring-engine`, branch
   `recurring-engine`, CP1.5 done 2026-08-02. Method fixed at intake by user
   decision: design the ACs clean-room (product-first, without reading
   `services/recurring.py`), then diff against shipped behaviour and resolve
   every divergence explicitly as fix-or-accept.
   - CP2 done 2026-08-02: 28 ACs, 18 high. Ten divergences, all resolved as fix
     (AC-6, 12, 13, 17, 20, 21, 22, 24, 25, 28). Costliest: the daily run rolls
     the whole batch back on one failure, so a single unchargeable obligation
     silently costs every other one its day (AC-24). Runner-up: deleting an
     engine-made charge returns the money but leaves that due date recorded as
     charged and pointing at a deleted row — consumed forever, invisible
     everywhere (AC-28).
   - `consistency-check` 2026-08-02: 0 errors, 8 warnings. W6/W7 closed by an
     AC edit pass (AC-27, AC-28). Still open: W1 + I3 (`feature-edit` — 007
     cites ADR-0013, superseded by 0026; the pre-DAE `ADR-020` pointer resolves
     to `docs/decisions/product-decisions.md`, not the P3 spec), W2/W3/W4/W5
     (ADR work at plan time), W8 (count existing manual recurring incomes in
     the production DB before implementing AC-6 — human-gated).
   - CP3 done 2026-08-02: `spec.md` with 70 scenarios / 77 executions, new
     handler module `acceptance/handlers/recurring_engine.py`. Red phase is
     exactly the target set — 24 failed / 53 passed on 007, 24 failed / 177
     passed across the whole suite (002, 005, 006 unaffected). Five bindings
     name service APIs that do not exist yet (`recurring.pending_dates`,
     `accept_pending_dates`, `decline_pending_dates`, a `failures` report on
     `materialize_due`, an engine value on `Source`) — CP4 owns their shape.
   - Project-level drift found on the way: `docs/decisions/product-decisions.md`
     had no entry since 2026-07-03. Feature 006's five product decisions and
     007's eight (this note said "nine" until 2026-08-02; `acs.md` lists eight)
     lived only in their `acs.md`. **Resolved 2026-08-02** — the user chose to
     backfill; `product-decisions.md` stays the home. ADR-026 already covered
     two of 007's, so eleven were outstanding and became nine new ADRs:
     006's five as 027–030 (AC-15 and the one-off-income scope call share 027),
     007's six as 031–035 (AC-20 and AC-28 share 034). File now holds 35.
   - Follow-up to open with `discuss`: a **Por cobrar** view for expected
     incoming money. Surfaced at AC discovery; the user wants it, but it is a
     new surface and feature 006 already ruled one-off planned incomes out.
     AC-6 (recurring incomes are always automatic) removes the urgency.
   - Follow-up, likely an ADR at plan time: `Source` has `manual`, `agent` and
     `import` but no value for the engine, so engine-created movements record
     themselves as hand-entered — blocks AC-25.
4. month-close-rollover ← **scope resolved 2026-08-02.** `goal-contribution-hooks`
   is dropped from this task: the discuss that promoted 003 decided goals
   collapse into funds, so the month-close hook that proposes one planned
   transfer per active goal is deleted rather than covered. Do not write
   acceptance tests for it. Rollover mechanics themselves survive the redesign,
   so the remainder of this task is safe to work now — it no longer waits on 003.
5. monthly-report (+ month-aggregate-read-path — shared read path)
6. mcp-tool-surface (+ mcp-tool-tier-policy)
7. chat-coach (+ chat-wire-adapter, chat-output-sanitization)
8. auth-session (+ csrf-double-submit)
9. multi-currency-fx (+ daily-scheduler-job)
10. db-migrations-postgres (+ read-path-indexes)
11. bff-api-proxy
12. markdown-rendering
13. Tier 4 features (masters + UI infra), one folder per row, in table order
14. goals ← **cancelled 2026-08-02.** The discuss that promoted 003 decided goals
    are not a feature: a goal becomes a fund with a `target-by-date` funding
    rule, and the `Goal` / `GoalContribution` tables plus the goals screen are
    deleted. There is nothing left to cover — 003's own acceptance suite owns
    the behaviour. Delete this row once 003 ships; keep it until then so the
    cancellation is not mistaken for an oversight.
15. budgets-envelopes + safe-to-spend ← **formalized at onboarding; paused pending
    sinking-funds redesign (features/003-sinking-funds, now `ready`)**
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
- C7. `tests/jobs/test_daily.py` set `QUAESTOR_DB` in a fixture, but `db.engine`
  is built at import time, so the patch arrived too late — those four tests had
  been running against the developer's on-disk `backend/quaestor.db` instead of
  the `tmp_path` they asked for. Fixed in feature 008 (F2) by building the
  engine from the intended URL. **The pattern may repeat**: audit every test
  that monkeypatches `QUAESTOR_DB` or touches `db.engine` directly. Found only
  because revision 0010's pre-flight guard counted 1383 uncategorised expenses
  in a file no test should have been reading.
- C8. The `Uncategorized` bucket in `services/reports._category_sections` and
  the `category_id is None` branches in `services/budgets` are dead code since
  ADR-0041: the CHECK refuses an uncategorised expense or income even against a
  raw `INSERT`, so the branch cannot be reached by any database at head. Its
  test was removed in feature 008 (F3) because it could no longer build the row.
  Harmless, but it is an untestable branch — prune it, or keep it deliberately
  with a comment saying why.
- C9. Domain refusals surface in the UI in English (`category 'Servicios'
  already exists`, `amount must be > 0`). Charter §3 says code and identifiers
  are English and **UI copy is Spanish**. This predates feature 008 — every
  backend error has always reached the toast untranslated — but 008 added
  several the owner will now meet often (missing category, wrong direction,
  duplicate name). Decide where translation belongs: the error class, the API
  boundary, or the frontend.
- C10. Six implementation leaks in delivered specs, found by spec-guardian
  during feature 008's Checkpoint 3 and deliberately left alone as out of
  scope. Listed in full in
  `features/008-mandatory-categories/handoffs/2026-08-03T0130-atdd.md`
  ("Left alone on purpose"): `005:195` (`## AC-13 — REST and MCP surfaces stay
  in parity`, the clearest one), `005:202`, `007:615/622/628`, `002:331`,
  `006:491,500`, `007:627`.
- C11. Feature 008 built its mutation tool ad-hoc in a scratch directory and
  feature 007 did the same, so neither is reusable. The manifest declares
  `mutation: opt_in / changed_files / on_demand`, which implies a repeatable
  process. Commit one small AST-based mutator (comparison, boolean, constant
  and `not`-removal operators are what both runs used) so the next feature does
  not rebuild it.

  **It must run both streams.** 008's sweep ran only backend unit tests for
  speed and reported four survivors; re-running them against unit **plus**
  `./run-acceptance-tests.sh` killed some outright. A mutation score measured
  against half the gate understates coverage and sends you writing tests for
  behaviour that was already pinned — by a scenario rather than a unit test,
  which is where this project's rules mostly live.
- C12. The recurring engine mints charges under **archived** categories.
  Reproduced by the CP7 reviewer: create an item under "Servicios", archive
  "Servicios", run `materialize_due` — the charge is created carrying the
  archived category, with no failure reported. AC-16 refuses an archived
  category for a new movement and AC-10 says archiving removes it from the
  choices offered for new movements; the engine is a new-movement path neither
  covers, because `occurrences._create_occurrence_tx` copies `item.category_id`
  without re-validating. The copy predates feature 008, but 008 is the feature
  that pins AC-16. Decide whether the engine should refuse, fall back, or warn —
  it is the one path that moves money with nobody watching.
- C13. `chatAssistantTurn` in `frontend/lib/query.ts` excludes the categories
  root, justified by "no chat tool mutates them in v1". `create_category` was
  already `write_safe`, and feature 008 added `new_category` to four more
  LLM-reachable tools, so an assistant turn can now create a category and leave
  every list in the UI stale. Add the root, or re-check the claim.

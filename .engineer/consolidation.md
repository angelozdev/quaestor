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
3. ~~recurring-engine~~ ← **DONE 2026-08-02.** `features/007-recurring-engine`
   merged to `main` as `91f31ae`; 28 ACs, 69 scenarios, feature `status: done`.
   The record of how it was worked is kept below because its method — clean-room
   ACs first, then diff against shipped behaviour and resolve every divergence
   as fix-or-accept — is the one this backlog reuses for every row after it.

   `features/007-recurring-engine`, branch
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
4. month-close-rollover ← **PARKED 2026-08-10. There is nothing left to cover.**
   The 2026-08-02 note below said the rollover mechanics survive the redesign
   and the remainder was safe to work. Measured before writing a scenario, that
   turns out to be wrong: `close_month` opens a transaction, iterates
   `ROLLOVER_HOOKS` and commits, and the list is **empty at runtime** — 0 hooks
   after `register_recurring_hooks()`, and the only `register_rollover_hook`
   calls in the repository are fakes inside `tests/services/test_rollover.py`.
   The module says so itself: *"The seam is ready and currently empty."* Goals
   took the only hook with them and nothing replaced it.

   Meanwhile `POST /api/rollover` is mounted and answers `{"ok": true}`, and
   `jobs/daily.py` reports `month_closed` every day, both for work that does not
   happen. Covering that with acceptance scenarios would be a green suite over
   code that does nothing — the exact failure 009 spent a week chasing.

   Promoted to roadmap `id:month-close-does-nothing` as a product question with
   the measurements: delete the machinery, give closing a real job (freezing a
   month is the obvious candidate, and it contradicts 009's AC-16, so it needs
   a decision first), or keep the seam and stop the endpoint claiming `ok`.
   **This row unparks when that is answered**, and what it covers depends on the
   answer.

   The original note, kept because its scope call still holds:
   *scope resolved 2026-08-02 — `goal-contribution-hooks` is dropped from this
   task: the discuss that promoted 003 decided goals collapse into funds, so the
   month-close hook that proposes one planned transfer per active goal is
   deleted rather than covered. Do not write acceptance tests for it.*
5. monthly-report (+ month-aggregate-read-path — shared read path)
6. mcp-tool-surface (+ mcp-tool-tier-policy)
7. chat-coach (+ chat-wire-adapter, chat-output-sanitization)
8. auth-session (+ csrf-double-submit)
9. multi-currency-fx (+ daily-scheduler-job)
10. db-migrations-postgres (+ read-path-indexes)
11. bff-api-proxy
12. markdown-rendering
13. Tier 4 features (masters + UI infra), one folder per row, in table order
15. budgets-envelopes + safe-to-spend ← **UNPAUSED 2026-08-10.** It waited on the
    sinking-funds redesign, and `features/003-sinking-funds` is `done`. Nothing
    blocks it now.
    - Open followup from fix `2026-07-31-phantom-budget-assignment`
      (gap: `missing_ac`): land "archived and budget-excluded categories cannot
      hold an envelope" as an AC in `acs.md` and propagate it to `spec.md`. The
      rule is already enforced in `services/budgets.set_budget` and pinned by
      service-layer regression tests — only the AC/spec paper trail is missing.
    - Second followup, from 009's close: **a meta cannot be closed as of a month
      before it existed** is the shape to look for here too. Product ADR-045
      settled it for metas; whether an envelope or a budget answers a month
      before it was set is unasked.

*(Row 14, `goals`, was deleted on 2026-08-10 as its own note instructed —
"delete this row once 003 ships". Goals are not a feature: a goal became a fund
with a dated rule, and 009 then withdrew that rule in favour of the meta. The
`Goal` / `GoalContribution` tables and the goals screen are gone, and 003's and
009's acceptance suites own the behaviour between them. **The number is left
vacant rather than closed up**, because `.engineer/fixes/2026-07-31-phantom-budget-assignment.md`
and its handoff both cite "consolidation #15", and those are records of what was
true when they were written.)*

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
- C14. `services/budgets.set_budget` accepts an envelope on an **income**
  category. Reproduced by the CP7 reviewer: `PUT /budgets {category_id: <an
  income category>, amount_assigned: 123456}` returns 200, and safe-to-spend
  deducts it from then on. An envelope on an income category can never accrue
  `spent` — the direction rule forbids an expense there — so `available` is
  frozen forever while `assigned_envelopes` permanently depresses the headline
  number. Predates feature 008 and is the larger of the two envelope problems;
  `set_budget` already refuses archived and `exclude_from_budget` categories, so
  the direction check belongs beside them.
- C15. The category **filter** dropdown on `/transactions`
  (`app/(app)/transactions/page.tsx:87,267`) lists both directions with bare
  names, so a per-direction name pair — "Intereses" as an expense and as an
  income, now allowed by AC-13's amendment — renders as two identical entries
  with nothing to tell them apart. The Categorías screen and the assistant's
  listing both mark direction; this one does not. It files no money, so it did
  not block the AC-13 ruling, but it is the one surface where the pair is
  ambiguous. Fix: show the direction in the filter's labels, or group by it.
- C16. The assistant's four category tools resolve by name with no way to say
  which direction, so a per-direction pair makes them act on the wrong row in
  silence. `_resolve_category_by_name` (`mcp/tools/core.py`) matches on name
  alone, and `UpdateCategoryInput`, `ArchiveCategoryInput`,
  `RestoreCategoryInput` and `GetCategoryInput` each carry only `category: str`.
  Reproduced on a migrated database: with "Intereses" existing as both an
  expense (id 1) and an income (id 2), `get_category("Intereses")` returns the
  expense and `archive_category("Intereses")` archives it — no error, no
  ambiguity signal, and no input the assistant could have used to mean the
  other one. `update_category` is the sharpest of the four: it can rename or
  re-flag the wrong direction's category.

  **Latent today, and invited by this feature.** Production holds exactly one
  duplicate name (`🛡️ Auto Insurance`, both expense, one archived) which every
  tool resolves correctly. It goes live the first time a name exists on both
  sides — which is precisely what AC-13's amendment was ruled to allow, and
  what `ec25f8b` advertises for "Intereses", "Comisiones" and "Ajuste".

  Refusing on ambiguity is not enough on its own: with no direction field there
  would be no way to answer the refusal, which is the same dead end the owner
  ruled against in N1/N2. The fix is a direction on the four inputs, plus a
  refusal when the name still matches more than one. REST is unaffected — it
  addresses categories by id.
- C17. **Product ADR-004's reconciliation clause has never been built.** The ADR
  states the month's forecast income *"is corrected to actual as transactions
  post, counting each income exactly once (ADR-014)"*, and it also says an
  atypical income "counts when posted". Neither happens.
  `services/budgets._income_forecast` iterates the active recurring items,
  recomputes their due dates inside the month and multiplies by the declared
  amount. It reads no `Transaction` at all, and `safe_to_spend_calc` receives
  that figure and never compares it to anything.

  **Measured 2026-08-03 against the live Postgres.** The forecast reports a flat
  $18.128.501 every month (Ubidots Salary $6.223.101 + Keystone US$3.800 at TRM
  3.133). The record reports $0 in April, $8.366.187 in May and $45.176.653 in
  July. Both describe the same two salaries; nothing in the app has ever
  compared them. A posted income carrying no `recurring_id` — 20 of the 22 in
  production — is invisible to the headline entirely.

  Two caveats against over-reading those figures: the history is a Lunch Money
  import, so the monthly spread reflects when rows were recorded rather than
  when money arrived, and the app itself is roughly a month old. The unread
  transaction table is the finding; the spread is only what makes it visible.

  Feature 003 owns the fix as **AC-14c**, because it replaces the headline
  outright. Filed here anyway: the defect is live today, on the shipped number,
  independent of whether 003 ships.
- C18. ~~**The money available reads too high when a recurring expense posts off
  its promise.**~~ **CLOSED 2026-08-04** — product ADR-039: a turn that posted
  counts at what really left the account, a turn still ahead at what it
  declared. Pinned by six unit tests and by **AC-29**, three scenarios the owner
  authorised adding to the approved `spec.md` and verified to fail against the
  code they replaced — the check AC-7 never had. ADR-0044 accepted; product
  ADR-039 records the decision. Original finding below.

  **The money available reads too high when a recurring expense posts off
  its promise.** `services/funds._uncovered` skips posted rows carrying a
  `recurring_id`, on the assumption that the obligations term beside it already
  counts them. That term sums `_promised` — the *declared* amount — so the two
  only agree when the charge posts for exactly what it said.

  **Probed on 2026-08-04**, unfunded category, obligation declaring $200.000:
  posts at $200.000 → available $4.800.000 ✓; the owner lowers the declaration
  to $150.000 → **$4.850.000, high by $50.000**; the owner switches the
  obligation off → **$5.000.000, high by $200.000**, with `uncovered` reporting
  **$0,00 for a month that really spent $200.000**.

  It is the exact asymmetry ADR-0044 fixed on the income side (decision D5,
  actual-if-any-else-expected) and never declared for the expense side, and it
  moves the headline **upward** — the direction the owner cannot recover from,
  because money is spent before the error can be noticed. No compensating
  surface exists: the breakdown still reconciles *exactly* with a wrong term,
  and a number that agrees with itself and lies is worse than one that visibly
  does not.

  **It is why ADR-0044's acceptance is withheld** — the ADR's own
  `uncovered(M)` paragraph describes behaviour the code does not implement.
  One product answer unblocks both: when an obligation declares one amount and
  posts another, does the month count the declared, the posted, or the greater?

- C19. ~~**"En camino" is structurally true whenever a fund opens the month
  holding nothing.**~~ **CLOSED 2026-08-04** — product ADR-040: a fund is behind
  when the month left it worse than not touching that category would have, which
  happens two ways — the spending pushed up what it must ask, or it went past
  everything the fund had. The second reading is the same overspill figure the
  money available already uses, so the badge and the headline can no longer
  disagree. Five unit tests, one per way to lose ground plus the boundary and
  the not-yet-started fund.

  **Replacing the ask-rise reading was tried first and refused by the contract**
  — `spec.md`'s *"Spending the fund on something else raises what it asks next"*
  asserts a raided fund is behind though it spilled nothing. Completing the
  reading rather than swapping it keeps that scenario green.

  **AC-7 stays open**, split off below: it is the same hole from the spec side
  and needs the owner's permission to touch `spec.md`. Original finding follows.

  `funds._walk` computed the reference figure as
  `_ask(..., max(opening, 0))`; when opening is zero that is the same call as
  the real ask, so the two always coincide and `on_track` can only be `True`.
  Reported first as affecting the two undated rules, it is wider: it also hits
  **every dated fund in its first month and every resetting fund every month**.

  **Seen in the browser on 2026-08-04**, not only in code: a fund needing
  $10.000.000 by the following month, holding $0, renders the green **"En
  camino"** badge. `FundsSummary.n_behind` returned 0 for a fund overspent 350%.

  `on_track` has **zero ACs, zero ADR mentions**, and one one-directional
  assertion in `spec.md` (line 227, on a `from-recurring` fund). It was a
  `feature.md` scope bullet CP2 never converted, so the threshold was the
  implementer's to invent. Not a fix — there is no correct behaviour to
  restore. It needs, in order: a product decision on what "on track" means at
  zero opening, an AC, then scenarios for all four rules.

  **AC-7 belongs to this same hole from the spec side and should be repaired in
  the same unit.** Titled *"A fund that gets drained raises its ask to still
  arrive"*, both its scenarios assert `1200000.00 COP` — exactly what an
  *undrained* fund asks ($7.200.000 ÷ 6). An implementation that ignores
  draining entirely passes both, so the AC cannot fail. Moving its clock to
  2027-02-10 makes the recomputation visible ($2.400.000).

- C20. ~~**AC-24's warning is off by one month, and the browser is what found
  it.**~~ **CLOSED 2026-08-04** — the warning now asks the very divisor the ask
  uses (`months_to_fund`), so it cannot stay silent on a month the whole target
  lands on. No product decision needed: the code's own message already
  described the case it was skipping.

  **Two unit tests pinned the defect and carried the proof inside them** — both
  asserted the preview would ask the target *in full* and that no warning
  fired. Rewritten, and the boundary is now stated as a pair: a target the month
  after the start warns and asks 600.000 whole; two months after does not and
  asks 300.000. AC-24's three approved scenarios never covered the +1 case, so
  the contract is untouched.

  Original finding: `services/funds._warning` returned `None` when
  `months_between(start_month, target_month) >= 1`, but the ask divides by the
  months from the start *through the month before the target*. A fund starting
  2026-08 with target 2026-09 therefore asks its whole target in August while
  the warning stays silent — the very case the warning exists to announce, and
  the code's own message ("leaves no month to save in, so the whole target
  falls on …") describes it.

  **Reproduced in the app on 2026-08-04**: a $10.000.000 target for 2026-09
  starting 2026-08 was created with no warning and immediately asked
  $10.000.000, against a declared monthly income of $3.000.000.

  Invisible to every gate this feature ran — 338 acceptance scenarios, 952
  backend tests, 92.3% mutation, zero CRAP findings — because AC-24's three
  scenarios only cover target = start and target = start + 12. Nothing tests
  target = start + 1. It is the same class feature 008 recorded when the
  browser found two defects its tests did not.

- C21. **The implausible-target warning reaches the owner in English, with the
  figure in raw cents.** Found in the browser on 2026-08-04 while confirming
  C20's fix, and invisible to every test: the unit tests assert
  `preview.warning is not None`, never what it says.

  The app is Spanish throughout. `services/funds._warning` builds the string
  server-side in English and `funds/page.tsx:303` renders `preview.warning`
  verbatim, so the owner sees, in red, above the *Crear de todos modos* button:

  > `2026-09 leaves no month to save in, so the whole target falls on 2026-08: it would ask 100000000 at once`

  Two defects in one line. **The language** — the only English string a Spanish
  user meets in the funds flow. **The figure** — `100000000` is $1.000.000 in
  cents, printed with no separator, no currency and no decimal, next to a form
  where the owner typed `1000000`. The two numbers differ by 100× on screen at
  the exact moment the app is asking them to reconsider.

  C20 makes this worse, not better: the warning now fires on a case it used to
  skip, so it is seen more often. Both belong to `_warning`; the frontend is
  only the messenger.

  **It is systemic, and that was verified rather than assumed.** Creating a
  category that already exists shows the owner `an expense category named
  'Transporte' already exists` — the same English, from a different module,
  through a different path. `api/errors.py:59` puts `str(exc)` on the wire for
  **102 raise sites, 69 distinct messages**, concentrated in categories (21),
  recurring (17), transactions (14), planned (13) and funds (11). ADR-0001
  fixed English for all code and put user-facing copy explicitly out of scope;
  no ADR ever picked it up.

  **Promoted 2026-08-04 to roadmap `id:error-contract`** — the owner chose
  codes-plus-data with the mapping in the frontend. The fund warning is the
  pilot: it is not an exception but a `FundPreview.warning` field in a 200
  response, and its number already travels beside it as `would_ask`, so it
  proves the pattern at the lowest cost. MCP is out of scope — it has its own
  `domain_error_text` and never crosses this seam.

- C22. **Duplicate category names survive the rule that forbids them.**
  `services/categories.py:92` refuses a second category of the same name *and
  direction*, but the check is service-side only: no unique index, no backfill.
  The dev sandbox carries two active expense categories both named
  "Restaurantes" — one grouped in "Estilo de vida", one ungrouped — which the
  app would now refuse to create.

  Seen while picking a category for C19's QA: the *Nueva transacción* dropdown
  offers "Restaurantes" twice with nothing to tell them apart, and the fund is
  on only one of them. Picking wrong silently sends the expense past the fund.
  Whether the local production database carries the same duplicates is
  **unverified** — worth a query before it matters.

- C23. **A fund's opening balance is reachable from the assistant and from
  nowhere else.** Found 2026-08-05 while deciding ADR-0043's anchor amendment,
  by reading the form rather than the service.

  `funds/page.tsx` declares exactly eight fields — `categoryId`, `rule`,
  `amount`, `windowMonths`, `targetAmount`, `targetMonth`, `startMonth`,
  `accumulates` — and the table's only row action is delete. There is no
  opening-balance input and no edit dialog. The API carries it on both paths
  (`FundCreateIn.opening_balance`, `FundUpdateIn.balance`) and MCP exposes both,
  so the owner can say *"this fund already holds $500.000"* to the chat and by
  no other means.

  **The contract could not catch it.** `spec.md`'s preamble says each AC is
  observed "at a surface a person uses — the app **or** the assistant", so
  AC-19's scenarios about a stated balance are satisfied by the assistant alone
  and never ask the app. A surface-parity clause would have caught it; the
  suites, mutation and CRAP could not, because nothing is broken — something is
  merely absent.

  **Closed by building** roadmap `id:fund-opening-balance`, which carries the
  field and the month rule together (product ADR-041). Filed separately from
  that task because the *general* lesson outlives it: an AC satisfiable at
  either surface silently permits a hole in one of them, and this feature has
  30 such ACs.

- C24. **A figure converted at read time has no foreign-currency case anywhere
  but the metas.** Found 2026-08-13 by fix
  `2026-08-13-a-meta-swallows-what-it-cannot-take`, by mutating the line the
  fix had just written.

  Hard-coding `"COP"` where the meta's own currency belonged reported an 800
  dollar contribution as $800 instead of $3.200.000 and passed 1.325 green
  tests: **no test in the project had ever contributed to a meta in dollars.**
  CHARTER §6's foreign-currency rule was written for screens that *write*
  money, and read-time conversion (ADR-0031) happens on screens where the owner
  types nothing.

  §6 was amended the same day to reach the read path, and the metas' own hole
  is closed. **What is left is the sweep:** every other figure `to_cop_cents`
  produces — the fund's asks, the month's income, the uncovered term, the
  report's spending lines — still has no case held in a currency other than
  COP. The amendment makes it required; nothing has audited it yet.

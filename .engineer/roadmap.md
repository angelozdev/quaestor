<!-- DAE-ROADMAP -->
# Roadmap

> DAE-managed strategic feature list. Edit items freely; DAE reads and writes this block.

## now
- [x] **Hybrid budget: envelopes + rollover + safe-to-spend** `id:hybrid-budget` priority:1 status:shipped area:budget → feature:budgets-safe-to-spend
      Product differentiator (ADR-002/003)
- [x] **Transactions CRUD with tags, categories, FX** `id:transactions-core` priority:2 status:shipped area:core → feature:transactions-crud
- [x] **Read-time FX: TRM table as single source of truth (drop frozen to_base) + cross-currency transfers** `id:fx-read-time-conversion` priority:3 status:shipped area:core → feature:fx-read-time-conversion
      Replaces undocumented frozen-snapshot FX design; ADR pending
- [x] **Planned payments / to-pay confirmation queue** `id:planned-to-pay` priority:3 status:shipped area:planning → feature:planned-payments-to-pay
- [x] **Recurring engine with materialize-due** `id:recurring` priority:4 status:shipped area:planning → feature:recurring-engine
- [x] **Savings goals with contributions** `id:goals` priority:5 status:shipped area:planning → feature:—
      SUPERSEDED 2026-08-02 by sinking-funds. Shipped, but being removed: the discuss that promoted 003 decided a goal is not its own concept - it is a fund with a target-by-date funding rule. The Goal / GoalContribution tables, the goals screen and the month-close contribution hook all go away with 003. Kept here as shipped history, not as live surface.
- [x] **Retrospective monthly report** `id:monthly-report` priority:6 status:shipped area:reports → feature:—
- [x] **Agentic chat coach (LiteLLM + MCP bridge, SSE)** `id:chat-coach` priority:7 status:shipped area:agent → feature:—
- [x] **Agent-native MCP tool surface with tier policy** `id:mcp-surface` priority:8 status:shipped area:agent → feature:—
- [ ] **Full ATDD coverage of the existing feature inventory** `id:atdd-consolidation` priority:9 status:planned area:quality → feature:—
      Worked down per .engineer/consolidation.md, tier order
- [x] **Local Postgres container replaces Render as production DB** `id:local-postgres-production` priority:10 status:shipped area:platform → feature:local-postgres-production
      ADR-0030; seeded from verified Render dump 2026-07-28; Render frozen standby
- [x] **Category becomes mandatory on every expense and income** `id:mandatory-categories` priority:10 status:shipped area:core → feature:mandatory-categories
      Decided by Angelo 2026-08-02 during the sinking-funds discuss. Category is nullable today and the gap is live in production: 28 posted expenses and 7 posted incomes carry no category, worth $2,072,854 COP + US$7,486.68 of spending and $7,003,101 COP + US$10,495.55 of income that no budget, average or per-category report can see. All 3 active recurring incomes (both salaries + the quarterly bonus) are uncategorised despite an existing Salary category, and 7 of 11 active recurring expenses are too. RULE: expense and income MUST carry a category; transfers MUST NOT (a transfer between the owner's own accounts is not spending - categorising it would double-count the same money on the way in and again on the way out; all 39 existing transfers are correctly null and must stay that way). SCOPE: backfill the existing rows, categorise the 10 recurring items, then enforce - service layer + migration making the column NOT NULL for expense/income. Product decision to record in docs/decisions/product-decisions.md. SEQUENCING: lands BEFORE 003-sinking-funds so the funding rules derive from clean data - with categories set, the engine can propose 8 recurring-derived funds instead of 3, and Internet resolves to its exact 85,000 recurring amount instead of a 149,585 three-month average polluted by uncategorised rows.

## next
- [ ] **Sinking funds: envelope funding rules + smoothed monthly available** `id:sinking-funds` priority:1 status:in-progress area:budget → feature:sinking-funds
      Replaces due-date safe-to-spend formula (product ADR-003/004, formal supersede at build time); envelopes get funding rules (fixed | N-month average | prorated recurring); goals unify as target-date funds. Parked as features/003-sinking-funds
- [ ] **Doc/code drift cleanup (README, ADR-0018, runbooks, dead code)** `id:doc-drift-cleanup` priority:2 status:planned area:quality → feature:—
      C1 + C6 done 2026-07-29 (README/charter/manifest aligned with ADR-0030); C2–C5 remain
- [x] **Strict ruff configuration as a Python guardrail (+ one-time violation sweep)** `id:ruff-strict-lint` priority:2 status:shipped area:quality → feature:—
      Requested by Angelo 2026-08-02: strict lint config aimed at an author who does not write Python and wants the tool to enforce best practice, not to be argued with. TRIGGER: feature 007's review found `# noqa: E402,F401,BLE001` directives suppressing rules for a linter that is not installed and never runs - no [tool.ruff] in backend/pyproject.toml, no ruff in [dependency-groups], no ruff.toml, no lint recipe in justfile, no CI, no pre-commit. Those directives were removed as dead weight; the real gap is that nothing lints Python at all. CONSTRAINT: CLAUDE.md bans inline comments project-wide, so `# noqa` is itself prohibited - every suppression must live in pyproject per-file-ignores, and the chosen rule set has to be livable without inline escapes. Frontend already has Biome; this is the Python-side equivalent, so match its strictness and its wiring (justfile recipe + whatever gate Biome uses). SCOPE: rule selection needs a web-verified pass on current ruff practice before anything is chosen (CLAUDE.md requires it for tooling), then an ADR in docs/adr (tooling + testing strategy), then a one-time violation sweep across backend/src, backend/tests and acceptance/. Expect the sweep to be the bulk of the work. Decide explicitly whether it gates the acceptance pipeline or only runs on demand.
- [ ] **Daily job that fetches the USD→COP rate so it is never missing** `id:daily-trm-fetch` priority:3 status:planned area:core → feature:—
      Named by Angelo 2026-08-04 as the expiry of product ADR-038: "la tasa se aplica al entrar en la app, siempre debe estar (mientras creamos un feature que obtenga la TRM por debajo día a día)". ADR-038 makes the rate a hard prerequisite of every read path - the money available, the fund status, the rates, the monthly report and the outstanding queue all refuse to render without one, even for a month recorded entirely in pesos. That is a deliberate cost, accepted only because it is meant to be temporary: this job removes it. SCOPE: a scheduled fetch of the official TRM from a source to be chosen (Colombia's TRM is published daily by the Superintendencia Financiera; datos.gov.co exposes it), written through the existing fx.set_trm (last write wins, ADR-011's manual override survives untouched), plus what to do on a fetch failure - the previous rate stands rather than being cleared, since a stale rate beats a locked app. Fits the same scheduler ADR-017's close_month already uses. Until it ships, setting the rate is a manual one-time act on a fresh install.
- [ ] **Automate daily pg_dump of local production DB to iCloud** `id:backup-automation` priority:3 status:planned area:platform → feature:—
      ADR-0030 consequence: backup discipline is load-bearing; candidates: scheduler daily job or launchd + just backup
- [ ] **Remove the 147 prohibited code comments from backend/src** `id:strip-code-comments` priority:3 status:planned area:quality → feature:—
      Surfaced 2026-08-02 while adopting ruff (ADR-0040). CLAUDE.md bans code comments project-wide - docstrings on public modules/functions excepted - but backend/src still carries 147 of them, and ruff has no 'forbid all comments' rule, so the ban is enforced by nobody. This is exactly the gap that let feature 007 introduce five prohibited lines that survived two review rounds. Options to weigh at design time: a custom AST check wired into the same gate as ruff (the repo already has an AST-based mutation runner to copy from), or accept that only review enforces it and say so in CLAUDE.md rather than pretending. Prerequisite: each comment needs judging, not deleting - CLAUDE.md's remedy is 'refactor so the code is self-documenting', not 'strip the line'. Expect real refactors, not a sed pass.

## later
- [ ] **Migrate real data from local SQLite to remote Postgres** `id:sqlite-to-postgres-migration` priority:1 status:dropped area:platform → feature:—
      Obsolete: data had already moved to Render pre-DAE (user confirmed 2026-07-28); ADR-0030 then brought production local
- [ ] **Decide fate of unwired CSV importer (wire up or delete)** `id:csv-importer-decision` priority:2 status:dropped area:core → feature:—
      Candidate for deletion per onboarding triage

<!-- /DAE-ROADMAP -->

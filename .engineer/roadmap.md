<!-- DAE-ROADMAP -->
# Roadmap

> DAE-managed strategic feature list. Edit items freely; DAE reads and writes this block.

## now
- [x] **Hybrid budget: envelopes + rollover + safe-to-spend** `id:hybrid-budget` priority:1 status:shipped area:budget → feature:budgets-safe-to-spend
      Product differentiator (ADR-002/003)
- [x] **Transactions CRUD with tags, categories, FX** `id:transactions-core` priority:2 status:shipped area:core → feature:transactions-crud
- [x] **Read-time FX: TRM table as single source of truth (drop frozen to_base) + cross-currency transfers** `id:fx-read-time-conversion` priority:3 status:shipped area:core → feature:fx-read-time-conversion
      Replaces undocumented frozen-snapshot FX design; ADR pending
- [x] **Planned payments / to-pay confirmation queue** `id:planned-to-pay` priority:3 status:shipped area:planning → feature:—
- [x] **Recurring engine with materialize-due** `id:recurring` priority:4 status:shipped area:planning → feature:—
- [x] **Savings goals with contributions** `id:goals` priority:5 status:shipped area:planning → feature:—
- [x] **Retrospective monthly report** `id:monthly-report` priority:6 status:shipped area:reports → feature:—
- [x] **Agentic chat coach (LiteLLM + MCP bridge, SSE)** `id:chat-coach` priority:7 status:shipped area:agent → feature:—
- [x] **Agent-native MCP tool surface with tier policy** `id:mcp-surface` priority:8 status:shipped area:agent → feature:—
- [ ] **Full ATDD coverage of the existing feature inventory** `id:atdd-consolidation` priority:9 status:planned area:quality → feature:—
      Worked down per .engineer/consolidation.md, tier order
- [x] **Local Postgres container replaces Render as production DB** `id:local-postgres-production` priority:10 status:shipped area:platform → feature:local-postgres-production
      ADR-0030; seeded from verified Render dump 2026-07-28; Render frozen standby

## next
- [ ] **Sinking funds: envelope funding rules + smoothed monthly available** `id:sinking-funds` priority:1 status:planned area:budget → feature:sinking-funds
      Replaces due-date safe-to-spend formula (product ADR-003/004, formal supersede at build time); envelopes get funding rules (fixed | N-month average | prorated recurring); goals unify as target-date funds. Parked as features/003-sinking-funds
- [ ] **Doc/code drift cleanup (README, ADR-0018, runbooks, dead code)** `id:doc-drift-cleanup` priority:2 status:planned area:quality → feature:—
      C1 + C6 done 2026-07-29 (README/charter/manifest aligned with ADR-0030); C2–C5 remain
- [ ] **Automate daily pg_dump of local production DB to iCloud** `id:backup-automation` priority:3 status:planned area:platform → feature:—
      ADR-0030 consequence: backup discipline is load-bearing; candidates: scheduler daily job or launchd + just backup

## later
- [ ] **Migrate real data from local SQLite to remote Postgres** `id:sqlite-to-postgres-migration` priority:1 status:dropped area:platform → feature:—
      Obsolete: data had already moved to Render pre-DAE (user confirmed 2026-07-28); ADR-0030 then brought production local
- [ ] **Decide fate of unwired CSV importer (wire up or delete)** `id:csv-importer-decision` priority:2 status:dropped area:core → feature:—
      Candidate for deletion per onboarding triage

<!-- /DAE-ROADMAP -->

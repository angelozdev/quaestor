# 0031. Read-time FX conversion from the single TRM value replaces frozen per-transaction snapshots

- **Status:** accepted
- **Date:** 2026-07-30
- **Amended:** 2026-07-30 — TRM storage changed from a dated rate table to a
  single scalar value (user decision during discover-acs of feature 005,
  before any implementation; amendment made pre-commit, so no published
  decision is contradicted)
- **Deciders:** Angelo
- **Supersedes:** — (replaces the undocumented pre-DAE frozen-snapshot design)
- **Superseded by:** —

## Context and problem statement

Every transaction freezes its conversion to the base currency (COP) at
registration: `Transaction.to_base` (COP cents) and `Transaction.fx_rate`
are computed once and never recalculated. The user explicitly does not want
this: a snapshot means a mistyped or stale TRM is baked into rows forever,
and totals never reflect the configured rate. The requirement is that the
configured TRM (kept fresh by the daily job, manually overridable) be the
single source of truth — all COP figures computed from it at read time.
This design predates DAE and had no ADR. Feature:
`features/005-fx-read-time-conversion/`.

## Decision drivers

- The TRM must be the single source of truth; correcting it must
  retroactively fix every report, budget, and total.
- The user is the only consumer (single-user, local-only, ADR-0026/0030);
  accounting-standard reporting stability is not a hard requirement.
- Simplicity: one conversion semantic that is easy to explain and test.
- Cross-currency movements (USD account → COP account) must become
  representable; today `transfer()` rejects them.
- Industry practice consulted 2026-07-30: Beancount/Ledger convert at
  report time from a price database; Firefly III stores original-currency
  amounts and converts to the primary currency from its rate table,
  and models cross-currency transfers as two explicit amounts; IAS 21
  prescribes a hybrid (transaction-date rate for flows, closing rate for
  monetary balances).

## Considered options

1. **Read-time conversion, everything at the current rate.** Drop
   `to_base`/`fx_rate` from `Transaction`; a single helper converts
   `amount × most-recent fx_rate row` at read time; COP is identity; no
   per-transaction override.
2. **Read-time conversion, IAS 21 hybrid.** Same storage change, but flows
   (reports, budgets) use the rate at the transaction's date (dated lookup)
   while balances/net worth use the current rate.
3. **Keep frozen snapshots** (status quo): `to_base` frozen at
   registration, optional per-transaction `fx_rate` override.

## Decision outcome

Chosen option: **1 — read-time conversion, everything at the current rate**,
because it maximally satisfies the source-of-truth driver with the simplest
possible semantic. Option 2 was recommended by the agent (standard-correct:
past expenses keep their historical cost) and **explicitly rejected by the
user**, accepting the consequence that closed months' totals move with the
TRM. Option 3 is the design being replaced.

Concrete shape:

- `Transaction` keeps only `amount` (integer cents) + `currency`; the
  `to_base` and `fx_rate` columns are dropped (migration touches real
  data → low-autonomy gate per manifest path override).
- **The TRM is a single scalar value, not a dated series** (amendment
  2026-07-30): under "everything at the current rate", correcting a past
  date's rate changes nothing, so a dated table stores history no read
  ever uses. The dated `fx_rate` table is dropped in the same migration;
  the daily job overwrites the value; manual set overwrites it too; last
  write wins. Rate history survives only in database backups.
- One conversion helper backed by the single TRM value. Unset TRM →
  `MissingRate` raised **at read time** for any base-currency read, even
  when all data is COP (fail loud; no silent rate-1 fallback à la
  Firefly). Registration no longer requires a rate.
- No per-transaction rate override of any kind.
- **Cross-currency transfers**: the same-currency validation is removed.
  Input takes two explicit physical amounts (sent X in the source
  account's currency, received Y in the destination's); each leg stores
  its own `amount`/`currency`; no rate is stored — the effective rate is
  implicit in the ratio. This does not reintroduce snapshots: both
  amounts are physical facts (what the bank moved), not conversions.
- `Settings.base_currency` remains decorative (COP hardcoded in
  `domain/money.py`); making it functional is out of scope and stays a
  known issue.

### Pros and cons of the options

**1. Read-time, everything at current rate (chosen)**
- Good, because one rate lookup, one semantic; the table is trivially the
  source of truth; fixing a rate fixes everything.
- Good, because it deletes two columns and the write-time FX resolution
  path (`_resolve_fx`) instead of adding machinery.
- Bad / cost, because historical reports are not stable: a closed month's
  COP total changes whenever the TRM moves. Accepted explicitly.
- Bad, because it diverges from IAS 21 for flows; if the ledger ever needs
  accounting-grade history, a dated-lookup variant must supersede this.

**2. Read-time, IAS 21 hybrid (rejected by user)**
- Good, because past expenses keep their historical cost; monthly reports
  are stable; standard-compliant.
- Bad, because two semantics to implement, test, and explain; the dated
  lookup needs a rate row reachable for every transaction date.

**3. Frozen snapshots (status quo, replaced)**
- Good, because reports are immutable and cheap to query.
- Bad, because a wrong rate is baked in forever; the rate table is not
  authoritative; contradicts the user's explicit requirement.

## Consequences

- Good: correcting the TRM (or the daily job catching up) retroactively
  fixes every COP figure with zero data rewrites.
- Bad / cost (amendment): in-app rate history is gone — "what was the TRM
  last week" is only answerable from backups. Accepted: no read path uses
  history under the chosen semantic, and reintroducing a dated store would
  require superseding this ADR anyway (same door as the IAS 21 variant).
- Good: cross-currency transfers become representable with two physical
  amounts — the two-leg `transfer_group_id` model already supports it.
- Good: registering a foreign-currency transaction no longer fails on a
  missing rate; the failure moves to read time, where it is fixable by
  setting today's rate.
- Bad / cost: every `to_base` consumer must be rewritten to convert at
  read time: reports, budgets, month_aggregate, goals, planned, recurring,
  REST schemas, MCP formatters (parity per ADR-0006/0009).
- Bad / cost: closed months' totals fluctuate with the TRM — an assumed
  and accepted property, not a bug. UI copy should not imply historical
  cost.
- Bad / cost: destructive schema migration on real data (drop two
  columns) — human at the wheel per the autonomy gate.
- Neutral: transfer deletion (currently blocked "P1") becomes
  well-defined with per-leg amounts; noted as a possible unlock for the
  feature plan, not committed here.
- Follow-up: budget math (`amount_assigned` in COP cents vs spending
  converted at current rate) must be re-derived in the feature plan.

## Confirmation

- Acceptance specs of `features/005-fx-read-time-conversion/` (ATDD
  pipeline) lock: conversion uses the current TRM value; a TRM change
  retroactively changes report output; unset TRM → `MissingRate` at
  read; cross-currency transfer stores both physical amounts and no rate.
- Schema check: `Transaction` has no `to_base`/`fx_rate` columns and the
  `fx_rate` table no longer exists after the migration; grep in CI/review
  for `to_base` must return no live code.
- Code-review checklist: any new COP figure must go through the single
  conversion helper — no caller may store a converted amount.

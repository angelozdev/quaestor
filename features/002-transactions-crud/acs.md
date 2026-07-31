---
ac_count: 16
high_priority_count: 9
discovered: 2026-07-31
---

# Acceptance criteria — 002 transactions-crud

Discovered 2026-07-31 (Checkpoint 2), reverse-engineer mode. Source
material: shipped code + 58 existing unit tests, P0 core design, ADR-0021,
ADR-0027, product review with Angelo. Four behavior decisions made during
discovery: **full tagging on every surface** (AC-6, new behavior),
**permanent delete confirmed** (AC-4, feature.md's "soft-deletes" corrected),
**transfers become deletable as a pair** (AC-5, new behavior — schema
change), **transfer sides stay independently editable but the pair must be
visible** (AC-10). Cross-currency transfer mechanics and read-time COP
conversion are already pinned by feature 005's acceptance suite — AC-2 and
AC-9 reference, not duplicate, that coverage.

## AC-1: Record an expense or income

- **Priority:** high
- **Type:** happy-path

Recording an expense or income takes a positive amount in the account's own
currency, a payee, a date, and optionally a category and notes. The account
balance moves immediately — down for an expense, up for an income.
Recording works with no TRM set and stores nothing about conversion.

## AC-2: A transfer is an atomic pair

- **Priority:** high
- **Type:** happy-path

A transfer produces two linked movements: the source account goes down by
the sent amount, the destination up by the received amount — both recorded
or neither. Same-currency transfers take one amount; cross-currency
transfers take both explicit amounts (mechanics pinned by feature 005).
Transfers never count as income or expense in any total.

## AC-3: Editing touches only balance-safe fields

- **Priority:** high
- **Type:** happy-path

Payee, notes, category and date of a transaction can be edited; the
category can also be cleared. Amount, account, currency and type are
immutable — no edit can ever desynchronize an account balance.

## AC-4: Deleting is permanent and reverses the balance

- **Priority:** high
- **Type:** happy-path

Deleting a posted expense or income permanently removes it and reverses its
balance effect; its tag links disappear while other transactions' tags are
untouched. There is no trash or restore (user decision 2026-07-31 — the
interface warns the action is permanent).

## AC-5: A mistaken transfer can be deleted as a pair

- **Priority:** high
- **Type:** happy-path

Deleting either side of a transfer removes both movements atomically and
reverses both account balances exactly; a half-deleted transfer can never
exist. (New behavior, user decision 2026-07-31 — today transfers cannot be
deleted at all. Requires recording each side's direction: schema change +
data migration, low-autonomy path per the manifest, ADR due at plan time.)

## AC-6: Tags work on every surface, add and remove

- **Priority:** high
- **Type:** happy-path

Tags can be added and removed both when creating and when editing a
transaction, equally from the app's pages, the API and the agent. Tags
auto-create by name (idempotent — re-applying an existing tag never
duplicates anything), and removing a tag from one transaction never affects
other transactions carrying it. (New behavior, user decision 2026-07-31 —
today only the agent can tag, only at creation, with no removal path.)

## AC-7: Lists show the most recent activity first

- **Priority:** high
- **Type:** happy-path

Transaction lists order by the transaction's own date, newest first, with a
deterministic tiebreak for same-day rows. Planned transactions appear at
their due-date position among posted ones so upcoming obligations are
visible in the same view. An opt-in registration-order sort exists for
auditing (ADR-0021).

## AC-8: Filters combine and live in the URL

- **Priority:** medium
- **Type:** happy-path

Lists filter by account, category, tag, type, status and date range —
boundary days inclusive — and filters combine. In the app, active filters
are fully described by the page URL: a reload or a shared link reproduces
the exact same view (ADR-0027).

## AC-9: COP equivalents are read-time

- **Priority:** medium
- **Type:** happy-path

Every read shows each transaction's COP equivalent computed at the current
TRM; reads fail loud when no TRM is set, while recording never requires one
(pinned by feature 005 — this AC only asserts the transactions surface
honors it).

## AC-10: A transfer side is never edited blind

- **Priority:** medium
- **Type:** edge-case

Each side of a transfer is edited independently — editing one side never
silently changes the other (legitimate: real bank dates can differ per
side). In exchange, the interface always presents a transfer side as part
of its pair: the counterpart is identified and reachable, so a per-side
edit is an informed act, not a surprise (user decision 2026-07-31).

## AC-11: Boundary values are honored

- **Priority:** medium
- **Type:** edge-case

One-cent amounts are accepted for records and for either transfer side.
Date-range filters include transactions falling exactly on the from/to
days.

## AC-12: Invalid registrations are rejected whole

- **Priority:** high
- **Type:** error

A registration with a non-positive amount, an unsupported currency, a
currency different from the account's, an unknown account or category, or
an archived account or category is rejected with a clear message — nothing
is recorded and no balance moves.

## AC-13: Failed multi-part writes leave nothing behind

- **Priority:** medium
- **Type:** error

When any multi-part write fails partway (e.g. a transfer to a destination
that doesn't exist), no partial movement remains and no balance changes.

## AC-14: Missing transactions answer clearly

- **Priority:** medium
- **Type:** error

Reading, editing or deleting a transaction that doesn't exist answers with
a clear "not found" — never a silent no-op.

## AC-15: The agent is a co-equal surface

- **Priority:** high
- **Type:** cross-cutting

Everything this feature does — record, transfer, list with filters, edit,
delete, tag — is available identically through the app and through the
agent (ADR-0006/0009), and every transaction records which surface created
it (manual, agent or import).

## AC-16: The surface requires a session

- **Priority:** medium
- **Type:** cross-cutting

No transaction data can be read or written without an authenticated
session (mechanics owned by the auth feature; this AC asserts the
transactions surface is covered by it).

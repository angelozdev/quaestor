---
slug: movement-corrections
checkpoint: 4
plan_status: approved
created: 2026-08-10
---

# Plan — 012 movement-corrections

Architecture confirmed by the owner 2026-08-10, with one standing instruction
attached: **DRY, KISS, low coupling, high cohesion.** Section *Where the design
bar bites* names every place this plan could have broken one of them and what it
does instead — not as a slogan, as a list of decisions.

## Architecture

### The one idea

**Correcting a movement is reversing its effect and applying it again to the same
row.** Recorded as ADR-0051.

```
today    delete   =  reverse the effect  →  drop the row
new      correct  =  reverse the effect  →  restate the row  →  apply the new effect  →  prove it
```

The reversal half already exists and is already trusted: `_delta_balance_of` and
`_reverse_balance` in `services/transactions.py` are what `delete_transaction`
uses, and all 25 of production's transfer pairs were deleted through them. This
feature adds the restate-and-apply half and the proof, and stops throwing the row
away.

### Two verbs, one core

The owner does two things, so the service says two things:

| Verb | What the owner is doing |
|---|---|
| `move_to_account(tx_id, account_id, amount=None)` | *this did not come out of Nu Débito, it came out of RappiCard* |
| `correct_amount(tx_id, amount, counterpart_amount=None)` | *this was not 93.558, it was 95.200* |

`amount` on the first is required exactly when the destination account holds a
different currency, and never accepted otherwise — the app refuses to invent a
figure (rule 2). `counterpart_amount` on the second is required exactly when the
movement is a leg of a transfer that crosses currencies, and refused otherwise:
in one currency the two halves are one number (AC-11), across currencies they are
two (AC-12).

Both funnel into one private core, `_restate(session, tx, mutate)`, which owns
the whole sequence — snapshot, reverse, mutate, apply, prove, commit or roll
back. **The balance arithmetic is written once.**

### The proof, and the one detail that makes it real

```
before   read the affected balances FROM THE DATABASE
         compute the exact delta each must move
apply    reverse, restate, re-apply
flush    push the writes down
after    read those balances FROM THE DATABASE AGAIN — not from the session's copies
check    each moved by exactly its delta, or roll back the whole correction
```

Reading the in-memory objects would only check the code against itself. Re-reading
after the flush also catches a change computed correctly and never persisted,
which is Firefly III's [#4589](https://github.com/firefly-iii/firefly-iii/issues/4589)
exactly.

The check asserts how much each balance **moved**, never what it **is**. An
account already off by $2.101.837,94 is off by exactly that afterwards, and the
three that reconcile keep reconciling. It cannot repair old drift and cannot
create new drift (AC-23).

### Confirming a payment

`planned.confirm_payment` gains `account_id`. A planned row has moved no balance,
so there is nothing to reverse: confirming reuses only the part that resolves the
target account and reconciles the currency, then posts as it already does.

### Where it lives

`services/transactions.py`, beside the apply-and-reverse code it reuses. 579 →
roughly 740 lines, in line with `metas.py` (685) and `funds.py` (598). A separate
module would have to import that module's privates or copy them. The import-linter
contracts are untouched: no new edge, no new layer.

### What comes free

`_require_account` already raises `NotFound` for a missing account and
`ValidationError` for an archived one. Routing every **destination** through it
gives AC-15 and AC-25 with no new code — and gives AC-16 too, because the
**source** is never revalidated. The one-directional rule the owner chose falls
out of a helper that already exists.

### The API

A correction does **not** enter through `update_transaction`. That function
promises no balance ever moves; folding balance-moving fields into it would hide
the most dangerous write in the app inside the most innocent one. Corrections get
their own named path (ADR-0051).

The assistant is untouched (AC-28) — a deliberate, documented exception to
ADR-0009's parity stance, recorded in ADR-0051's consequences.

### The screens

Two dialogs gain an account control and an amount control. The conversion
prefill — *choosing an account in another currency fills in the converted
figure* — is **one** helper used by both (AC-4 and AC-13 are the same behaviour
on two screens; the owner made them identical on purpose). `MoneyInput`,
`EntitySelect` and `currencyOf` already exist and are reused, not rebuilt.

The edit dialog loses the line *"Para cambiar monto/cuenta, elimina y vuelve a
crear."* and stops printing `cuenta #5` (AC-14).

## Where the design bar bites

| Principle | Where it could have broken | What this plan does |
|---|---|---|
| **DRY** | Two verbs each doing snapshot → reverse → apply → prove | One private `_restate`; the verbs only say *what changes* |
| **DRY** | Confirming and correcting both resolving account + currency + amount | One resolver shared by both |
| **DRY** | The conversion prefill living in two dialogs | One helper; the two screens differ in nothing |
| **DRY** | A second way to compute a balance delta | `_delta_balance_of` stays the only one; correcting calls it |
| **KISS** | An audit trail, a corrections table, an event log | None. The owner decided a correction forgets (AC-30 of the discuss); building history anyway would be scope nobody asked for |
| **KISS** | A general invariant framework over all balances | The check covers exactly the accounts the correction touched |
| **KISS** | An opening-balance column to make the check "complete" | Declined, priced, filed as its own roadmap item |
| **Low coupling** | A new `services/corrections.py` importing another module's privates | Correcting lives with the reversal code it needs; no new import edge anywhere |
| **Low coupling** | Balance-moving fields on the balance-safe editor | A separate path, so the two are told apart by name |
| **High cohesion** | Balance mechanics split across two modules | One module owns applying, reversing and restating a balance effect |
| **High cohesion** | The archived-account rule restated in the new code | Routed through `_require_account`, which already holds it |

## Charter Check

| Charter rule | Verdict | Evidence |
|---|---|---|
| §1 DAE + full ATDD coverage | ✅ | 30 ACs, 66 scenarios, red confirmed before any code |
| §1 ADRs for significant decisions | ✅ | ADR-0051 accepted before implementation, as CLAUDE.md requires |
| §2 Backend layering api → services → domain | ✅ | New code sits in `services/`, reads `domain/rules`; no upward import |
| §2 MCP surface at REST parity (ADR-0006/0009) | ⚠️ | Deliberately broken here: the assistant gains nothing (AC-28). Amendment recorded in ADR-0051's consequences and decided by the owner on 2026-08-10 |
| §3 English for code, Spanish for UI (ADR-0001) | ✅ | |
| §3 No code comments (CLAUDE.md) | ✅ | Docstrings only, lean |
| §3 pnpm only (ADR-0003) | ✅ | No new dependency on either side |
| §3 Conventional Commits | ✅ | |
| §4 Single user, local-only | ✅ | |
| §6 Nothing merges without both suites green for the touched surface | ✅ | See Test strategy |
| §7 Human required for migrations | ✅ | **No migration.** No column, no table |
| §7 Human required for merges to `main` | ✅ | The owner merges |
| §7 Autonomy medium, ceiling = the local test surface | ✅ | Validation is pytest + vitest + the acceptance pipeline; no staging exists |
| Verification independence at CP6/CP7 | ⚠️ | See below — a decision the owner owes at CP6, not now |
| Mutation policy | ✅ | Opted in for this feature: `services/transactions.py` and `services/planned.py` |

### Amendments

**ADR-0009 parity, amended for this feature.** The MCP surface does not gain the
correction verbs. Correcting is the only path that moves two stored balances at
once, and the owner decided on 2026-08-10 that it belongs on a screen where he
sees what he is changing before it happens. Recorded in ADR-0051's consequences
rather than as a separate ADR, because it is a consequence of that decision
rather than a decision of its own. AC-28 binds it: three scenarios assert the
assistant cannot do it and that what it could already do still works.

**Verification independence — a decision owed at CP6, flagged now.** Feature 009
is the reason this is called out. Its CP6 ran on the same agent that wrote the
code; the Principle-7 gate went red, and an independent review afterwards found
**six user-facing defects in already-merged code** that three AC-tracing rounds
had missed. This session operates under a standing instruction not to dispatch
subagents unless the owner asks. So CP6 and CP7 here have exactly two honest
options — the owner invokes fresh agents himself, or he authorises dispatch —
and picking one is his. It does not block CP5, and the plan proceeds. It must not
be forgotten at CP6.

## Phasing

Four slices. Each ends with a runnable subset of the suite, not a task list —
the tasks are the scenarios.

**Slice 1 — the core and the proof.** `_restate`, the two verbs, the shared
resolver, the arithmetic check. The 30 unbound step handlers.
*Closes AC-7, 8, 9, 15, 16, 21, 23, 24, 25, 26.*

**Slice 2 — confirming names its account.** `confirm_payment` gains the account;
the planned path reuses the resolver.
*Closes AC-2, 3 (backend arm), 4 (backend arm), 5, 6, 20.*

**Slice 3 — transfers.** Leg-level account moves, pair-level amounts, the
same-currency equality rule and the crossing-currency two-figure rule.
*Closes AC-10, 11, 12, 13 (backend arm), 22.*

**Slice 4 — the screens and the negatives.** Both dialogs, the shared prefill
helper, the deleted instruction, label association; then the invariants that must
be shown not to move.
*Closes AC-1, 3/4/13 (screen arms), 14, 17, 18, 19, 28, 29, 30.*

Slices 1–3 are backend and independent of 4. Slice 4's screen scenarios are the
13 untagged ones and cannot go green from Python — which is the point.

## Performance budgets

Autonomy is medium, so budgets are not mandatory; one figure is worth stating
anyway. **Each correction adds two account reads** (the after-snapshot) on top of
what a delete-and-recreate would have cost, against an operation the owner
performs a handful of times a month. No read path changes, so no screen gets
slower. `month_aggregate` never reads the account and is untouched.

## Collaboration schedule

- **CP5 implement** — agent, autonomy medium, on `movement-corrections`.
- **CP6 refine / CP7 verify** — blocked on the independence decision above.
- **Merge to `main`** — the owner, CHARTER §7.
- The owner is asked once more only if a scenario turns out to encode something
  he did not decide.

## Execution modes

Local only. Cloud dispatch is not enabled (`remote.ready: false`). Validation is
the local stack: host-side pytest on in-memory SQLite, vitest, and the acceptance
pipeline. Real production data is never written to; the QA rig, if needed, is a
`pg_dump` restored into a scratch database served on port 8001 with the scheduler
off — never `just dev-prod`.

## Test strategy

`feature.md` carries no `validation_method`, so this is the standard DAE stack,
stated explicitly:

- **Acceptance** — 66 scenarios. 53 generate pytest against the services layer;
  13 bind to vitest against the screen. Full pipeline before any push:
  `./run-acceptance-tests.sh features/012-movement-corrections`.
- **Unit** — backend pytest and frontend vitest for the touched surface (CHARTER
  §6). The acceptance suite binds at the services layer, so the REST path and the
  dialogs need their own tests or they are covered by nothing that executes them
  — the lcov `FNF:12 / FNH:0` finding from 009 is the precedent.
- **Mutation** — opted in for `backend/src/quaestor/services/transactions.py` and
  `backend/src/quaestor/services/planned.py`:
  `python3 backend/scripts/mutate.py --target <path> --stage "<cmd>" --cwd backend`.
  These two modules are the balance-moving path, and AC-23's whole value is a
  check that can actually fail — a surviving mutant inside the verification would
  mean it cannot.
- **Real data** — a lifecycle pass over HTTP against a restored copy of
  production before the feature is called done, because that is what found 009's
  seventh defect after every suite was green.

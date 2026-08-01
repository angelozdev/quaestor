> ▶ CP7 verify done 2026-07-31 (uncommitted) | NEXT: Angelo reviews the diff, then CP8 harden | BLOCKED: none

# Progress — 002 transactions-crud

Shipped before DAE adoption (onboarding intake 2026-07-28); re-entered the
pipeline 2026-07-31 to formalize ACs and close two behavior gaps: full tagging
on every surface (AC-6/AC-15) and atomic transfer-pair deletion (AC-5, schema
change — ADR-0032).

Branch `transactions-crud`, 4 commits ahead of `main`, not pushed. It also
carries the `2026-07-31-phantom-budget-assignment` fix, which landed here
instead of its own branch — see that fix's handoff for the open split decision.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | onboarding intake (2026-07-28) |
| 2 | ACs | done | 2026-07-31T0950-discover-acs.md |
| 3 | Spec | done | 2026-07-31T1013-atdd.md |
| 4 | Plan | done | 2026-07-31T1018-plan.md |
| 5 | Implement | done | 2026-07-31T1045-implement.md |
| 6 | Refine | done | 2026-07-31T1314-refine.md |
| 7 | Verify | done | 2026-07-31T1903-verify.md |
| 8 | Harden | pending | — |

CP6 baseline: acceptance 64/64, backend 741, frontend 213, `tsc --noEmit`
clean, Biome clean on touched files.

CP7 result: acceptance 64/64, backend 750, frontend 214, `tsc --noEmit`
clean, Biome clean on touched files, coverage 95% total
(`services/transactions.py` 90% → 92%). The backend number rose from CP6's
741 to 744 on the two budgets-fix commits, then to 750 with CP7's five new
delete tests. Changes are in the working tree, uncommitted.

## Runbook

Closed 2026-07-31 (`runbook.md`). Both migrations self-applied at container
boot before their planned backup — 0006 on 2026-07-31T15:27Z, 0007 on
2026-07-31T22:05Z. Neither caused damage:

- **0006** backfilled 18/18 groups correctly; verified out/in_ per group and
  lower-id-is-out.
- **0007** was a **no-op on real data**: 0 staggered pairs across 634
  transactions, so it wrote zero rows. Verified by count first, then shape
  (`alembic_version` 0007, 0 malformed groups, 0 groups whose lower id is not
  `out`). Backup `quaestor-local-2026-07-31-post-0007.dump` taken and verified
  with `pg_restore --list`.

The repeat incident is the CP8 gap-analysis item: the operational rule written
after 0006 ("bring the pg stack down before touching `migrations/`") did not
prevent the recurrence because it relied on a human remembering. The fix is
structural — disarm auto-migration in the pg profile, or stop bind-mounting
`src` there.

## Pendientes para CP7 — CERRADOS en 2026-07-31T1903-verify.md

Los tres puntos de abajo quedaron resueltos en CP7. Se conservan como
registro de lo que se verificó.

### 1. Planned single-leg transfers cannot be deleted (defect, found 2026-07-31) — RESUELTO

`delete_transaction` routes on `type == TxType.transfer` **without checking
`status`**, so a planned or skipped goal contribution — one leg, no
`transfer_group_id` — enters `_delete_transfer_pair`, which raises
`ValidationError: transfer {id} has no transfer group; cannot delete its pair`
(`services/transactions.py:424-428`, `:457-460`).

Real data: ids **1462** (`skipped`, 2026-06-30) and **1545** (`planned`,
2026-07-31), both `Goal: Korea`, 3.000.000 COP, account 9, goal 1. These are
correct by design — the second leg is born at confirm time — so the rows are
not the bug; the delete path is.

Not a two-row curiosity: every planned goal contribution is born this way, so
one new undeletable row accrues per goal per period. The row action "Eliminar"
is offered on every row with no status gate
(`frontend/app/(app)/transactions/page.tsx:168-174`).

Severity: **low, no data risk** — fail-loud, raises before touching balances or
rows. Workaround exists and is already in use: "Omitir" on the *Por pagar* page
(`skipPlanned`), which is how 1462 reached `skipped`.

Also wrong: the confirm dialog promises *"Se eliminarán ambos lados de la
transferencia y se restaurarán los saldos de las dos cuentas"* for any
`type === "transfer"` row (`page.tsx:326-329`) — false for a single-leg planned
row.

Decision (Angelo, 2026-07-31): fix inside CP7 of 002 rather than as a separate
`/engineer.fix`, because AC-5 is exactly "transfers delete as a pair" and a new
branch would repeat the orphan-branch problem already open with the budgets fix.

Scope for CP7: delete a group-less transfer through the normal single-row path
(reverse one balance, only if `posted`), correct the dialog copy for
single-leg rows, and pin both with tests — `grep "no transfer group"` over
`backend/tests/` currently returns nothing.

Cierre: `delete_transaction` ahora enruta al borrado de par solo cuando el
leg tiene `transfer_group_id`; sin grupo borra una sola fila y revierte
saldo únicamente si estaba `posted`. Copy del diálogo condicional. Cinco
tests nuevos escritos en rojo primero. ADR-0032 amendado.

### 2. AC-5 must be re-verified across all three creation paths — RESUELTO

CP6 found `transfer_direction` was set only in `transactions.transfer()`;
`planned._confirm_transfer()` and `goals.contribute_to_goal()` were fixed in
that checkpoint. Verify all three, not just `transfer()`.

Cierre: son **cuatro** rutas de creación, no tres. La cuarta,
`goals.propose_goal_contributions()`, escribe un solo leg `planned` sin
grupo y sin dirección — correcto por diseño, y es exactamente el origen del
defecto #1.

### 3. Independence — RESUELTO

CP7 must run on an `agent_id` distinct from CP5's `cp5-implementer-subagent`
(plan.md Charter Check, Principio 7).

Cierre: CP7 corrió como `cp7-verifier`.

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-07-30T1232 | prime-context | main | context loaded |
| 2026-07-31T0942 | prime-context | main | re-primed for the AC pass |
| 2026-07-31T0950 | discover-acs | main | ACs discovered; 4 user decisions (full tagging, permanent delete, pair deletion, independent sides) |
| 2026-07-31T1013 | atdd | main | spec.md + pipeline generated |
| 2026-07-31T1018 | plan | main | architecture + ADR-0032; runbook created |
| 2026-07-31T1045 | implement | cp5-implementer-subagent | implementation green |
| 2026-07-31T1314 | refine | main | 3 review lenses; AC-5 defect found + fixed at all 3 creation sites; revision 0007 written; 13 proposals applied |
| 2026-07-31 | runbook-close | main | 0007 verified no-op on real data; backup taken; planned single-leg delete defect found |
| 2026-07-31T1903 | verify | cp7-verifier | 16/16 ACs mapped; a 4th transfer creation path found; group-less delete fixed test-first; 64/750/214 green; 3 process findings |

## Tracker sync

- Tracker `local` — feature files are the tracker. Roadmap item
  `transactions-core` already marked shipped (pre-DAE code); consolidation
  task #1 covers this ATDD pass.
- Note: `feature.md` still carries `status: done` from the onboarding intake,
  which described the pre-DAE code. The current pipeline pass is at CP6 with
  unmerged work — reconcile the field when 002 merges.

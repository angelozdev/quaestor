---
slug: "2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget"
title: "Restoring a cancelled meta charges its month a contribution it had already handed back"
severity: medium
blocks_user: false
workaround: "remove the contribution from the meta's history before restoring it — `Ver aportes` lists it"
status: closed

source:
  kind: internal
  ref: "found by the CP7 verifier of fix 2026-08-13-a-meta-gives-back-money-no-month-ever-gave-it"

repro: |
  1. Open a meta and contribute 1.000.000 COP to it in November.
  2. Cancel it in November. It hands back everything the months put in.
  3. Restore it, still in November.
  4. Read November.

expected: |
  `restore_meta`'s own docstring: a restored meta "begins at the month it is
  restored in and fills from zero. Resuming with the old holdings would give the
  owner the same money twice."
actual: |
  November charges the new instalment AND the old contribution again — the row
  was never deleted and `start_month` is now November, so the walk reads it a
  second time. Half of what the meta holds came out of a meta that was
  cancelled.

  A contribution made in a month BEFORE the restore is the mirror image: it
  stays listed at face value (AC-42) and no month ever reads it — the same
  "money the owner believes he saved" that
  `2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in` closed on the
  write path.

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1

pin_confirmation:
  feature_refs:
    - feature: "features/009-named-goals"
      red_run:
        result: red
        command: "./run-acceptance-tests.sh features/009-named-goals"
        output: |
          FAILED test_a_restored_meta_does_not_charge_again_a_contribution_the_cancellation_gave_back
            AssertionError: the meta 'Portatil' holds 200000000, expected 100000000
          FAILED test_a_contribution_made_in_a_month_the_restore_left_behind_is_given_back_too
            AttributeError: 'MetaContribution' object has no attribute 'returned_month'
          2 failed, 153 passed
        note: |
          The guard scenario shipped beside them and was GREEN from the first
          run by design — a meta never cancelled goes on counting its
          contributions, so the new filter cannot over-reach.

fix_commits:
  - d70b3ad
  - c9afeb9
  - 24f2411
  - e9d7cc0

verification:
  independent_agents:
    - id: cp7-verifier-restore
      told_to: "break the fix, not confirm it"
      verdict: "BROKEN — 2 money findings, both regressions introduced by d70b3ad"
      findings: |
        F1. A contribution dated AFTER the cancellation month was stamped
        `returned_month` although that month's give-back never included it —
        the fold sums rows dated at or before the cancellation. A meta with a
        September contribution cancelled in August went from holding
        2.785.714,29 to 1.785.714,29. A million nobody returned, lost.
        Closed by `_given_back_by`, which bounds the stamp by
        `row.year_month <= meta.cancelled_month`.

        F2. Restoring in a month BEHIND the cancellation cleared
        `cancelled_month`, so no month gave anything back, while the stamp took
        the contribution out of the months that still ran. July fell from
        1.833.333,34 to 833.333,34. Closed by refusing the restore.

        F3 (no action). Three mutants survived the whole suite at d70b3ad —
        dropping the `returned_month is None` guard, stamping `today`, stamping
        `"1970-01"` — because the acceptance handler asserted only that a stamp
        exists. All three are killed at HEAD by c9afeb9's
        `test_a_second_cancellation_leaves_the_first_ones_give_back_month_alone`,
        which asserts the exact (month, returned_month) pairs.
      held_up: |
        40+ month readings with the identity
        `free = income − Σfund asks − Σmeta asks − contributed + released − uncovered`
        matching `free` exactly; a USD meta; a stated opening (AC-34); an amount
        lowered below holdings (AC-16); a planned linked purchase (AC-43);
        `month_split` (AC-37); restore twice in one month; cancel twice without
        a restore between; two metas where only one is restored; `_room_left`
        after a restore; `remove_contribution` on a stamped row moving nothing.
      note: |
        Both findings were reproduced independently by the implementer before
        being accepted, rather than taken on the agent's word.

harden_results:
  mutation_score: 0.959
  arch_check: "Contracts: 2 kept, 0 broken (cd backend && uv run lint-imports)"
  bug_line_mutation_confirmed: true
  mutation_evidence: |
    `backend/scripts/mutate.py --target backend/src/quaestor/services/metas.py`
    in a detached worktree at e9d7cc0, three stages, each green-gated on
    untouched source first. 197 mutants, 189 killed, 8 alive, 95.9%.

    All eight read and judged equivalent, each verified rather than carried
    over from the 2026-08-13 sweep of the same module:
      - four `frozen=True` on `MetaPreview`, `_Month`, `_Walked`, `MetaFold`.
        Each is built once and only read; `replace()` works unfrozen too.
      - two on `funded: int = 0`. The default is taken only by the pre-start
        `_Month(ask=0, holds=0)` of line 280, and `holds=0` clamps it at every
        reader — `min(month.holds, month.funded)` in `_gave_back` is the only
        one that reaches it.
      - two on `progress = … if amount else 0`. All three writers pass through
        `_validate_spec`, which refuses `amount <= 0`, so the `else` arm is
        unreachable.
    None of the fix's own lines survived.
  bug_line_evidence: |
    Five load-bearing lines, each mutated by hand and each killed:
      1. the stamping loop in `restore_meta` removed → 2 failed, 1 passed
      2. `MetaContribution.returned_month.is_(None)` dropped from the
         aggregate's WHERE → 2 failed, 1 passed
      3. `if row.returned_month is None` removed (the second-cancellation
         guard) → the whole 1190-test backend suite stayed GREEN, and only
         `test_a_second_cancellation_leaves_the_first_ones_give_back_month_alone`,
         written for exactly this, went red. That guard had no test at all
         until c9afeb9.
      4. `row.year_month <= (meta.cancelled_month or "")` dropped from
         `_given_back_by` → only
         `test_a_contribution_the_cancellation_never_gave_back_is_not_marked_as_given_back`
         went red (1 failed, 1 passed).
      5. the `today < meta.cancelled_month` refusal removed → only
         `test_a_meta_cannot_come_back_in_a_month_behind_the_one_it_left_in`
         went red (1 failed, 1 passed).
    The frontend half was proven red the same way: stashing `meta-actions.tsx`
    left 1 failed | 32 passed.

gap_analysis:
  - feature: "features/009-named-goals"
    category: missing_ac
    finding: |
      AC-29 said only that a meta is archived and restored. It never decided
      what becomes of the money the owner had put in by hand, so the question
      reached the code undecided — and the code answered it in a docstring:
      "a restored meta begins at the month it is restored in and fills from
      zero. Resuming with the old holdings would give the owner the same money
      twice." It kept half of that: it cleared `stated_opening` and moved
      `start_month`, and left every contribution row untouched.

      A promise a docstring makes and no criterion holds it to is not a
      contract. Nothing could fail when only half of it was true.
    closed_by: "AC-29 gained three clauses, and AC-42 one, in this fix."
  - feature: "features/009-named-goals"
    category: inadequate_verification
    finding: |
      The acceptance handler asked whether the contribution carried a stamp,
      not which month it carried:

          assert any(… and r.returned_month for r in rows)

      So the ADR's central claim — that the stamp names the month the
      cancellation actually released the money — was pinned by nothing. Three
      wrong ways of writing it survived the whole 1.185-test suite: stamping
      `today`, stamping a constant `"1970-01"`, and overwriting an earlier
      life's stamp.

      The general shape: a truthiness assertion on a field whose VALUE is the
      decision proves only that the field is populated.
    closed_by: |
      `test_a_second_cancellation_leaves_the_first_ones_give_back_month_alone`
      asserts the exact (month, returned_month) pairs and kills all three.
  - feature: "features/009-named-goals"
    category: inadequate_verification
    finding: |
      CHARTER §6's browser check was recorded as waived on this feature earlier
      the same day, for a reason nobody verified: "the frontend container does
      not bind-mount its source". The base `docker-compose.yml` mounts
      `./frontend/app`, `components`, `lib` and `ui`; only the ADR-0033 dev
      OVERRIDE is backend-only, and the claim was drawn from reading the
      override alone.

      Driving the browser once the mistake was found took ten minutes and
      surfaced a defect the waiver had hidden: the create form never shows its
      refusal and never disables `Crear`, with the server answering 422.

      The general shape: an exit criterion excused by an unverified claim about
      infrastructure is an unmet criterion recorded as met.
    closed_by: |
      Cross-filed. The false claim is corrected in place in
      `.engineer/handoffs/2026-08-13-metas-refuse-what-cannot-land-close.md`,
      the defect it hid has its own artifact
      (`2026-08-13-the-create-form-never-shows-the-refusal-the-server-gave-it`),
      and the fact is saved so it cannot be re-derived wrong.

followups:
  - to: ".engineer/consolidation.md"
    as: "C25"
    kind: advisory
  - to: ".engineer/consolidation.md"
    as: "C26"
    kind: advisory
---

# Restoring a meta revives a contribution it promised to forget

## The two halves

`restore_meta` rewrites `start_month` to today and clears `stated_opening`, but
`MetaContribution` rows survive untouched. The walk then starts from the new
month, so the rows split in two:

- **made in the restore month** — read again, on top of the money the
  cancellation already handed back.
- **made before it** — read by nothing, listed at face value by AC-42.

Both are the same seam this evening's fixes closed everywhere else: nothing
tied what the owner offered to what a month actually took.

## Note for the pin

The regression needs both halves, and the product question is which way it
goes — delete the rows the restore orphans, or leave them and stop reading the
ones in the restore month. The first loses history AC-42 promises; the second
leaves the owner a list of contributions that did nothing.

## Also filed here: a rounding drift

The give-back cap compares meta-currency ints and converts once, while each
month's ask converts on its own. Over a meta's life the two diverge by ±1 cent
in COP for a foreign-currency meta at some rates — measured at TRM 3333,33 and
4123,77. Sub-peso and not user-visible, but it is the only case where
`released` can exceed what the months put in.

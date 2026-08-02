---
skill: consistency-check
agent_id: main
started: 2026-08-02T0930
ended: 2026-08-02T0955
checkpoint: null
artifacts: []
scope: feature
findings:
  errors: 0
  warnings: 8
  informational: 3
exit_criteria:
  - criterion: Every feature-scope check ran
    verified_by: tool
    met: true
    evidence: "slug/folder, frontmatter, AC ids + counts, domain language, ADR existence, handoff completeness, tracker_ref, parent_feature — spec.md/plan.md checks N/A (artifacts do not exist at CP2)"
  - criterion: Structural checks pass
    verified_by: tool
    met: true
    evidence: "dae_handoff.py features/007-recurring-engine -> exit 0, 'ok -- latest complete checkpoint: 1.5'; acs.md AC-1..AC-26 unique and sequential, ac_count 26 == 26 sections, high_priority_count 17 == 17 'Priority: high'; ADRs 0005/0013/0034 all present in docs/adr/; slug recurring-engine == folder 007-recurring-engine"
  - criterion: No implementation leakage in AC bodies
    verified_by: tool
    met: true
    evidence: "grep for .py paths, function-call syntax, HTTP/status/endpoint, column/table/class, model names across everything from '## AC-1:' onward -> no matches; file paths appear only in the preamble ledger, matching the 006 precedent"
  - criterion: Report delivered without mutating artifacts
    verified_by: judgment
    met: true
    evidence: "read-only run; no Edit/Write against feature artifacts, ADRs or the P3 design doc"
findings_summary: "0 errors. 8 warnings: one superseded ADR cited, nine target ACs contradicting accepted product decision ADR-020 with no supersede, three ACs requiring state the accepted design has no room for, two coverage gaps that leave acs.md incomplete before CP3, and an unaddressed migration case"
human_action_needed: yes
human_action_kind: decision
recommended_next: "/engineer.discover-acs edit pass to close W6 and W7 (both are missing ACs, not wrong ones), then /engineer.feature-edit for W1 and I3, then /engineer.atdd — W2/W3/W4/W5 are ADR work that belongs at plan time, not before the spec"
tracker_update: "none — read-only check"
status: complete
---

# consistency-check — handoff summary

## What I did

Feature-scope check on `007-recurring-engine` at the CP2/CP3 boundary. Loaded
`feature.md`, `acs.md`, both handoffs, `CHARTER.md`, the manifest, ADR-0005 /
0013 / 0034, `docs/decisions/product-decisions.md` and the P3 temporal-engine
design; ran `dae_handoff.py`; grepped the AC bodies for leakage. No LSP servers
are recorded, so identifier lookups used grep + Read.

Nine of the 26 ACs are `target` — they change a shipped feature. That is a much
larger delta than a consistency check normally sees, and it is where every
warning below comes from.

## Errors

None. Every error-severity check passes.

## Warnings

**W1 — `relevant_adrs` cites a superseded ADR.** `feature.md` lists ADR-0013
(daily scheduler as a thin sidecar), whose frontmatter reads
`Superseded by: 0026`. The scheduler is no longer a sidecar container: CHARTER §2
puts it in an asyncio task in the FastAPI lifespan. AC-2 rests on that mechanism.
Fix: `feature-edit` — `relevant_adrs: [0005, 0026, 0034]`, or add 0026 beside
0013.

**W2 — nine target ACs contradict an accepted product decision, with no
supersede.** `docs/decisions/product-decisions.md` § ADR-020 is the accepted
contract for this engine: daily due-driven materialization, and "a **manual** is
generated `planned` for the current month, visible in to-pay". The P3 design adds
"**`materialize_due` is NOT a user tool**" in four separate places. AC-12 makes
creation interactive for passed dates and AC-6 removes manual income entirely.
CLAUDE.md requires an explicit supersede, never a silent contradiction. Two
project-level notes: the CP2 handoff already flags two ADRs due at plan time,
which covers the architectural half; and
`docs/decisions/product-decisions.md` has had no entry since 2026-07-03 —
feature 006's five decisions live only in its `acs.md` too, so this is drift
across the DAE era, not a 007 defect.

**W3 — AC-13 overloads ADR-0005's lifecycle flag.** ADR-0005 makes
`RecurringItem.active = false` mean "the user soft-deleted this, and `restore`
brings it back". AC-13 has the *system* write the same flag for an unrelated
reason (the end date passed). Two consequences: restoring an ended obligation
re-activates something that still produces nothing, and the list can no longer
tell "I switched this off" from "this finished". Decide at plan time between
deriving "ended" at read time (no schema change, ADR-0005 untouched) and a real
third state (schema + an ADR superseding ADR-0005's uniform two-state
lifecycle).

**W4 — AC-17 needs state that does not exist.** "Resuming picks up from today"
requires knowing when the pause ended; the only anchor stored today is
`start_date`, which is why the shipped engine charges the whole paused stretch.
That behaviour is not an accident — ADR-0013's consequences state it as a
feature: "scheduler downtime of N days is self-healing — the next run
materializes the missed occurrences in one pass". AC-17 keeps that for downtime
(AC-9) and removes it for pauses. Schema + ADR at plan time.

**W5 — AC-12 needs an "awaiting decision" marker the daily job must not
touch.** AC-2 and AC-9 keep the engine unattended; AC-12 forbids creating a
passed date before the user answers. With nothing recording that an answer is
outstanding, the next daily run either backfills silently (AC-12 broken) or the
offer is lost between sessions. Same ADR as W2.

**W6 — coverage gap: the occurrence side of an undone skip.** `feature.md`
scope says "this feature owns only the occurrence side of the skip sync", and
ADR-0034 with feature 006's AC-8 makes a skip reversible, syncing the occurrence
back to `planned`. No AC in `acs.md` asserts it. AC-15 states "a skipped date is
never recreated by a later run" without noting that a restore does bring it
back — true but incomplete, and it will read as a contradiction to whoever
writes the spec. `acs.md` is not complete for CP3 until this is added.

**W7 — coverage gap: AC-20's escape hatch is unasserted.** AC-20 refuses to skip
a date already charged and directs the user to delete the movement instead,
leaning on feature 002's balance-reversing delete. But deleting an engine-made
movement leaves its occurrence still marked charged and pointing at a movement
that no longer exists, so that due date stays consumed forever and no later run
brings it back. Nothing in `acs.md` says what deleting an engine-made movement
should do. AC-20 depends on an answer it does not state.

**W8 — AC-6 does not address obligations already declared.** Forcing incomes to
automatic is written as a rule for new declarations. Any manual recurring income
already sitting in the production database is unaddressed. Count them before
implementing — production is the local Postgres container (ADR-0030) and the
manifest forces `low` autonomy for anything touching it, so that count is a
human-gated step.

## Informational

**I1 — CP2 reads as incomplete, correctly.** `dae_handoff.py` reports "latest
complete checkpoint: 1.5" even though the CP2 handoff says `status: complete`,
because its "human reviewed the ACs" criterion is `met: false`. The gate is
working: CP2 closes when the review lands.

**I2 — the P3 design doc is stale in three places, as predicted.** ADR-0034's
consequences asked this check to flag its "skipped (canceled)" wording rather
than edit the historical record — flagged. Two more: the doc specifies auto
materialization with a "frozen `to_base`", which ADR-0031's read-time FX
superseded; and it documents `skip_recurring` as creating an occurrence for any
given date, which AC-21 refuses. Do not edit the doc; `acs.md` is the live
contract.

**I3 — the pre-DAE `ADR-020` pointer in `feature.md` is imprecise.** The Notes
send the reader to the P3 spec, but `ADR-020` resolves to
`docs/decisions/product-decisions.md` § ADR-020, which `Source links` does not
list. That file is the one W2 turns on. Minor `feature-edit`.

## Human action needed?

Yes — decision. W6 and W7 are missing ACs, so `acs.md` is not ready for CP3 as
it stands. W1 and I3 are one-line corrections. W2, W3, W4 and W5 are ADR work
that belongs at plan time; they need acknowledging now, not resolving.

## Recommended next step

`/engineer.discover-acs` as an edit pass for W6 and W7 (preserving AC IDs), then
`/engineer.feature-edit` for W1 and I3, then `/engineer.atdd`. Re-run this check
after `plan.md` exists to pick up the Charter Check and the ADR supersedes.

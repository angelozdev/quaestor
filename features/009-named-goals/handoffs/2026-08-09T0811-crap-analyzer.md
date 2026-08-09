---
skill: crap-analyzer
agent_id: subagent-crap-cp7
feature: 009-named-goals
started: 2026-08-09T0800
ended: 2026-08-09T0815
checkpoint: 7
artifacts:
  - features/009-named-goals/handoffs/2026-08-09T0811-crap-analyzer.md
exit_criteria:
  - criterion: The checkpoint's entry gate is clean
    verified_by: tool
    met: false
    evidence: "`python3 …/engineer/0.19.0/scripts/dae_handoff.py features/009-named-goals --through 6` → `verifier-independence violated: CP6 handoff 2026-08-09T0758-refine.md shares agent_id main-session with the CP5 implement handoff (Principle 7)`, exit 1. NOT MET AND NOT CLAIMED. This checkpoint ran anyway on the owner's explicit instruction; the sequence CP5→CP6→CP7 is not clean and this handoff does not pretend it is."
  - criterion: Verification independence for THIS checkpoint (Principle 7)
    verified_by: judgment
    met: true
    evidence: "`agent_id: subagent-crap-cp7`, a fresh agent that wrote none of the code under measurement. Differs from the CP5 and CP6 `main-session`."
  - criterion: Real coverage was generated, not assumed
    verified_by: tool
    met: true
    evidence: "Backend unit — `cd backend && SESSION_SECRET=… uv run --with pytest-cov pytest -q --cov=quaestor --cov-report=json:… --cov-report=term` → `TOTAL 5096 276 95%` and `1012 passed, 1 warning in 86.67s`. Frontend — `cd frontend && pnpm vitest run --coverage --coverage.provider=v8 --coverage.reporter=lcov …` → `Test Files 55 passed (55) / Tests 397 passed (397)` and `Statements : 83.42% ( 6385/7654 ) / Branches : 86.08% ( 1151/1337 ) / Functions : 56.72% ( 443/781 )`. `pytest-cov` is NOT in the backend venv (`uv run python -c \"import pytest_cov\"` → `ModuleNotFoundError`); `uv run --with pytest-cov` supplied it per-invocation and installed nothing into the project."
  - criterion: The third test stream was measured too, not inferred
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh` → `472 passed, 1 warning in 30.70s`. Then the same generated dirs re-run under coverage — `cd backend && SESSION_SECRET=… uv run --with pytest-cov pytest -q --cov=quaestor --cov-report=json:… ../features/002-…/.build/generated … ../features/010-…/.build/generated` → `TOTAL 5096 1388 73%` and `472 passed, 1 warning in 53.95s`. Union of the two backend streams: 4879/5096 executable lines = 95.7%."
  - criterion: CRAP computed over the branch's changed code, both languages
    verified_by: tool
    met: true
    evidence: "Diff `git diff --merge-base main HEAD` — 87 files, 9145 insertions. Backend, union coverage — `compute_crap.py --diff backend-rel.diff --repo-root <clean HEAD export>/backend --lcov merged-coverage.json --threshold 20` → `No functions above threshold (20.0).` Same result against the unit stream alone. Frontend — `compute_crap.py --diff frontend-rel.diff --repo-root frontend --lcov fe-coverage/lcov.info --threshold 20` → 1 finding: `components/transaction-create-dialog.tsx:84` `TransactionCreateDialog`, complexity 29, coverage 76% (220/289), CRAP 40.45."
  - criterion: Every finding above threshold was read before being judged
    verified_by: judgment
    met: true
    evidence: "The one finding above 20 was read in full (409 lines) along with its per-line lcov record, and is classified as an artefact below with the reason. The sub-threshold backend list was read the same way, and the useful signal turned out not to be a CRAP score at all — it is the residual all-streams-uncovered lines, listed below with file:line."
  - criterion: Report only — no refactor applied, no test written
    verified_by: tool
    met: true
    evidence: "`git status --short` at exit shows only ` M backend/src/quaestor/services/metas.py` and `?? backend/src/quaestor/services/metas.py.orig`, neither of which this agent created — see the concurrency warning below. No file under `backend/`, `frontend/`, `acceptance/` or `.build/` was written by this checkpoint. Nothing staged, committed or pushed."
  - criterion: Working tree left clean
    verified_by: tool
    met: partial
    evidence: "PARTIAL, AND NOT BECAUSE OF THIS AGENT. My own artefact (`backend/.coverage`) was deleted; all coverage reports and the clean-source export live in the session scratchpad. The tree is dirty because a CONCURRENT session is running mutation testing on this same checkout — see the concurrency warning. I did not revert it: it is not my work to discard."
findings_summary: "CRAP FINDS ALMOST NOTHING, AND THAT IS THE ACCURATE ANSWER — but the coverage it needed to say so found four places the app can go where no test of any stream has ever been. BACKEND: zero functions above the default threshold of 20, whether scored against the unit stream alone or against the union of unit + acceptance. The worst is `load_month_aggregate` at 17.0 with 100% coverage, and its complexity is comprehension-counting, not branching. FRONTEND: one finding above 20 — `transaction-create-dialog.tsx:84` at CRAP 40.45 — and it is an artefact: complexity 29 is ~20 JSX render-prop arrows, the 69 uncovered lines are the pre-existing transfer tab and error handlers, and every line this branch added to that file is covered. THE REAL PAYLOAD IS THE RESIDUE. Merging both backend streams leaves nine lines of `services/metas.py`, one of `services/transactions.py` and one of `api/routers/metas.py` that NO stream executes. Four of them are this feature's own behaviour: (1) `api/routers/metas.py:62` — the whole body of `PATCH /metas/{id}`, the AC-11 edit adapter. The service is covered (acceptance calls `metas.set_meta` directly), the screen calls it (`meta-actions.tsx:195`), and the wire between them is executed by nothing — the frontend test mocks `@/lib/api/metas` and no backend test issues the request. This is the CP5 shape inverted: not a behaviour no screen reaches, but a screen and a service joined by an adapter no test runs. (2) `services/metas.py:503-506` — `_amend`'s replace-this-month's-amendment branch, whose docstring promises 'editing twice in October leaves October with one amendment'. `if existing is not None` is evaluated and never true; the promise is unverified. (3) `services/metas.py:261` — `_to_meta_currency`'s non-COP branch, i.e. AC-26 'a purchase reaches its meta in the meta's own currency', never once exercised. (4) `services/metas.py:53` and `services/transactions.py:70` — both 'meta not found', so every NotFound path this feature added is untested. SEPARATELY, ON THE SCREEN: `app/(app)/metas/create-form.tsx` lines 75-77, 83-90 and 98-101 are uncovered — the create form's submit handler and its success/error handlers. `createMeta` is mocked and `mockResolvedValue`-primed in `page.test.tsx:85` and never asserted as called; the test at line 194 asserts the 'Crear de todos modos' button EXISTS. That is the CP5 finding verbatim, one screen over. AND A PROCESS HAZARD: another session was mutating `services/metas.py` in this same working tree while I measured. Caught it, re-measured against a clean `git archive HEAD` export, and the numbers above are the corrected ones."
human_action_needed: yes
human_action_kind: decision
recommended_next: "Two decisions, then CP8. (1) THE CONCURRENCY, FIRST AND IMMEDIATELY — a second session is running mutation testing directly on this working tree; `backend/src/quaestor/services/metas.py` is currently an AST round-trip of itself with `# noqa: E712` stripped from line 63 — `ruff check` on it returns `Found 18 errors.`, so if that session dies before restoring `metas.py.orig` the lint gate stops `run-acceptance-tests.sh` before a single test runs. CP8 belongs in a git worktree, not in the checkout CP7 is measuring. (2) THE ELEVEN UNCOVERED LINES — they are a test-writing decision, not a refactor one, and CRAP will never surface them because the functions holding them are trivial. `PATCH /metas/{id}` and the create form's submit are the two that would have been caught by exactly the driving-the-app pass CP5 says found its four gaps. Then CP8 mutation on `domain/rules.py` and `services/metas.py` per plan.md — noting that mutation will report a healthy score on `_amend` and `_to_meta_currency` for the wrong reason: mutants in never-executed lines cannot be killed and may be reported as no-coverage rather than survivors, depending on the tool."
tracker_update: "local — 009 at checkpoint 7, status in-progress. CRAP: 0 backend findings above 20 (union of both backend streams, 95.7%); 1 frontend finding above 20, classified artefact. Streams re-verified green: acceptance 472, backend unit 1012, vitest 397. Eleven all-streams-uncovered lines recorded, four of them this feature's own. CP7 entry gate still failing on Principle 7 for CP5/CP6. CP8 open."
status: complete
---

# crap-analyzer — handoff summary

## What I did

Generated real coverage for all three test streams, merged the two backend ones,
and ran `compute_crap.py` over `git diff --merge-base main HEAD` for both
languages — then read every function above threshold and every line the merged
coverage still could not reach. No refactor was applied and no test was written.

## Artifacts produced

This handoff. Coverage reports, the merged report and a clean-source export live
in the session scratchpad and are not in the repo.

## Findings

### The scores

```
backend    threshold 20   0 findings     union of unit + acceptance, 95.7%
frontend   threshold 20   1 finding      CRAP 40.45, and it is an artefact
```

Backend, worst five at threshold 5, scored against both streams:

| # | File:Line | Function | Cx | Cov | CRAP |
|---|-----------|----------|---:|----:|-----:|
| 1 | `services/month_aggregate.py:187` | `load_month_aggregate` | 17 | 100% | 17.0 |
| 2 | `services/month.py:62` | `_uncovered` | 14 | 100% | 14.0 |
| 3 | `services/categories.py:246` | `update_category` | 12 | 87% | 12.32 |
| 4 | `migrations/…0016….py:44` | `_free_the_name_of_a_cancelled_meta` | 3 | n/a | 12.0 |
| 5 | `services/funds.py:445` | `_validated_spec` | 12 | 100% | 12.0 |

### What is an artefact, and why

**`components/transaction-create-dialog.tsx:84` — `TransactionCreateDialog`,
CRAP 40.45.** The only finding above the default threshold, and it is not a
risk this branch created. Complexity 29 is roughly twenty JSX render-prop
arrows plus markup ternaries; the actual decision logic in the function is about
six branches. The 69 uncovered lines are the transfer tab's JSX (323-382), the
transfer mutation (161-177) and the two `onError` handlers (154-156) — all
pre-existing. Every line this branch added is covered: `meta_id` on the payload
(149) and the `MetaField` subscribe block (283-293), pinned by
`sends the chosen meta with the purchase`. The skill's own rule 7 puts template
and markup changes out of scope for this tool, and that is the right call here.
The one true observation is a cohesion one and it predates 009: two unrelated
forms live in one 409-line component. Not this feature's churn to pay for.

**`load_month_aggregate` at 17.0, `_uncovered` at 14.0, `month_split` and
`_spent_where_spending_is_saving` at 8.0.** All 100% covered. Their complexity
is comprehension and generator counting in linear code, not branching. Refactor
value: none.

**The four migration entries (12.0, 6.0 ×3).** `n/a` coverage — alembic modules
are never imported by any test, so the script scores them as fully untested.
Migration rehearsal is CHARTER §7 human work and was recorded in CP5. Ignore.

### What is genuine, and it is not a CRAP score

Merging the unit stream with the acceptance stream lifts `services/metas.py`
from 76% to 96%. Eleven lines survive that merge — executed by no test in any
stream. Four are this feature's own behaviour.

**1. `backend/src/quaestor/api/routers/metas.py:62`** — the entire body of
`PATCH /metas/{meta_id}`:

```python
return metas.set_meta(session, meta_id, today=month, **body.model_dump(exclude_unset=True))
```

Every other line of that router is covered. This one is reached by nothing.
The service beneath it is fully covered, because `acceptance/handlers/named_goals.py`
calls `service.set_meta(...)` directly at lines 156, 165 and 174. The screen
above it calls it too — `app/(app)/metas/meta-actions.tsx:195` → `setMeta` →
`PATCH /metas/{id}` — but `page.test.tsx` mocks `@/lib/api/metas` wholesale, so
`lib/api/metas.ts:19` never runs either. Both ends are tested against a middle
that is not. Nothing here is *proven* broken; what is proven is that if the
query parameter, the schema field names or the route shape were wrong, all
three streams would still be green. Note also that `setMeta`'s TS signature
takes `Partial<MetaCreate>`, which permits `currency` and `stated_opening` —
fields `MetaUpdate` does not declare and Pydantic silently drops.

**2. `backend/src/quaestor/services/metas.py:503-506`** — `_amend`'s
replace-branch. Line 502's `if existing is not None` is executed; it is never
true. The docstring states the contract in as many words: *"editing twice in
October leaves October with one amendment, the last one, rather than a trail
nothing reads."* Nothing tests it. A second edit in the same month is the
obvious thing an owner does.

**3. `backend/src/quaestor/services/metas.py:261`** —
`return round(cop_cents / float(agg.trm))`, the non-COP branch of
`_to_meta_currency`. That function's docstring cites AC-26, *"a purchase reaches
its meta in the meta's own currency"*. Every meta in every test is COP, so the
conversion is never performed. A USD meta is a shipped, reachable state.

**4. `backend/src/quaestor/services/metas.py:53` and
`backend/src/quaestor/services/transactions.py:70`** — both
`raise NotFound(f"meta {meta_id} not found")`. Every "no such meta" refusal this
feature added is untested, including the one guarding a purchase pointed at a
nonexistent meta (AC-23/AC-25).

The remaining survivors are `metas.py:70` (a meta needs a name), `metas.py:133`
(`_walk` before the start month), `metas.py:336` (contribution not found), plus
pre-existing defensive raises in `funds.py` (392, 441-442, 548) and
`rules.py` (41, 251) that 009 did not touch.

### And the same shape CP5 wrote up, one screen over

`frontend/app/(app)/metas/create-form.tsx` lines 75-77, 83-90 and 98-101 are
uncovered: the submit handler, and the mutation's `onSuccess` and `onError`.
`page.test.tsx:22` mocks `createMeta`, line 85 primes it with
`createMeta.mockResolvedValue(meta())`, and no test ever asserts it was called.
Line 194 asserts that the button reading *"Crear de todos modos"* is in the
document. CP5's own words for the /metas action buttons were: *"the screen test
asserted they existed without clicking one."* The create form is the same
assertion, still in place, on the path a first-time owner takes.

For contrast, the parts of the feature that ARE well covered: `services/month.py`
100%, `services/month_aggregate.py` 100%, `domain/models.py` 100%,
`api/schemas.py` 100%, `domain/dtos.py` 100%, `lib/available-breakdown.ts` 100%,
`lib/metas.ts` 100%, `components/meta-field.tsx` 100%, `app/(app)/metas/page.tsx`
100%.

### The thing that worried me most, and it is not in the diff

**Another session is mutating this working tree right now.** Partway through,
`git status --short` went from clean to:

```
 M backend/src/quaestor/services/metas.py
?? backend/src/quaestor/services/metas.py.orig
```

`metas.py` on disk is 426 lines against HEAD's 520 — an AST round-trip with
blank lines collapsed, string quotes normalised and, critically, the
`# noqa: E712` stripped from line 63. That is a mutation-testing harness, i.e.
CP8, running in the same checkout CP7 is measuring, with a `.orig` backup it
will restore only if it exits cleanly. If it does not, the lint gate fails:
`uv run --project backend ruff check backend/src/quaestor/services/metas.py`
returns `Found 18 errors.` against the file as it stands, and
`run-acceptance-tests.sh` runs `ruff check` before it runs a single test.

It also silently corrupted a measurement: my first merged CRAP run read function
spans from the mutated file while the line numbers came from the clean one, and
reported `_status` at `metas.py:119` instead of `metas.py:141`. Every number in
this handoff was recomputed against a `git archive HEAD` export in the
scratchpad after that was caught. I verified both coverage JSONs describe the
clean file (205 statements, max line 520, matching HEAD) before merging them.

I did not revert the other session's file. It is not my work to discard.

The process lesson is the one CP6 already wrote from the other side, extended:
this repo has three test streams and now two agents. CP8 belongs in a worktree.

## Human action needed?

**Yes — a decision, and one of the two is urgent.**

1. **The concurrent mutation run.** Decide whether CP8 continues in this
   checkout or moves to a worktree, and confirm `metas.py` is restored from
   `metas.py.orig` before anything else runs the lint gate. Nothing in this
   handoff depends on the answer; the branch's cleanliness does.

2. **The eleven uncovered lines.** They are a test decision, not a refactor
   decision, and no CRAP threshold will ever surface them because the functions
   holding them are two and three branches wide. Worst-first by consequence:
   `PATCH /metas/{id}`, the create form's submit, `_amend`'s replace branch,
   `_to_meta_currency`'s non-COP branch.

The entry gate remains failed and is recorded above verbatim. CP5 and CP6 share
`main-session`; this checkpoint does not, but it cannot repair theirs.

## Recommended next step

CP8 mutation on `domain/rules.py` and `services/metas.py` per `plan.md`'s test
strategy — in a worktree, after the decision above. One caveat to carry into it:
mutants planted in `_amend:503-506` and `_to_meta_currency:261` sit on lines no
test executes, so the tool will report them as uncovered rather than surviving,
depending on how it classifies. A clean mutation score on those two functions
means nothing until they have a test at all.

## Tracker update

Local driver. 009 at checkpoint 7, `in-progress`. CRAP clean at the default
threshold on the backend; the single frontend finding is an artefact and named
as one. Streams re-verified: acceptance 472, backend unit 1012, vitest 397.
Eleven all-streams-uncovered lines recorded. CP8 open, and blocked on a decision
about where it runs.

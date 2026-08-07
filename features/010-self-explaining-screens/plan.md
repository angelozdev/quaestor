---
slug: self-explaining-screens
checkpoint: 4
plan_status: approved
created: 2026-08-07
---

# Plan — 010 self-explaining-screens

113 scenarios over 21 ACs, approved 2026-08-07 after three spec-guardian passes.
Architecture confirmed by the owner the same day.

## Architecture

### A. The backend seam — three figures, one extra fold step, zero new queries

`FundStatus` gains three fields: **what the category spent this month**, **what
the fund carries into next month**, and **what next month will have to spend**.

The load-bearing finding, verified before proposing: **every input next month's
ask needs is already in the loaded aggregate.** Checked rule by rule against
`services/funds.py` and `services/month_aggregate.py`:

| rule | next month's ask needs | already loaded? |
|---|---|---|
| `fixed` | `fund.amount` | yes — on the record |
| `average` | the window shifted one month | yes — `_spent_by_cat_month` holds all history as per-(category, month) sums |
| `from_recurring` | next month's turns and skips | yes — `_turns_this_month` is pure date maths on the item, `agg.spent_in` returns 0 for a future month, and **`skipped_turns` loads every skipped occurrence with no month bound at all** (`month_aggregate.py:190`) |
| `target_by_date` | the carry and the months remaining | yes — both derivable from the fold |

So the change is **one more iteration of the loop `_walk` already runs**, and
**no new DB access**. ADR-0028's bounded read path is untouched, which was the
real risk in taking this feature out of frontend-only.

**Shape.** `_walk` keeps its signature and its return. A new
`_look_ahead(agg, fund, walked, year_month) -> tuple[int, int]` runs the same
body once for `next_year_month(year_month)` and returns `(carries,
next_month_has)`. `_status` gains the three fields; `FundStatusOut` and the
frontend type follow.

**Why not fold it into `_walk`.** `_walk`'s loop invariant is "advance until the
month asked for". Making it overshoot by one changes the meaning of its return
and touches the one function whose correctness 003's whole suite rests on.
A separate call that *reuses the same body* keeps the blast radius at a new
function plus three fields.

**Risk named:** `_ask` for `from_recurring` in a month the aggregate was not
built for is the one call that could behave differently. AC-18's two new
scenarios (`A fund that reads its recurring charges asks what it asked before`,
and the target-by-date twin) exist to pin that the *current* month's answer does
not move; the `@backend` AC-3 scenarios pin the look-ahead itself.

### B. The two nouns are derived, never stored

`accumulates == false` → **presupuesto**; `true` → **fondo**. One helper in
`frontend/lib/funds.ts`, used by every screen that names a shape.

**Rejected: a stored `shape` field.** The record stays one shape, which is
exactly what product ADR-037 decided and what ADR-042 explicitly upholds. The
split is presentation, and storing it would create a second source of truth that
can disagree with `accumulates`.

**Consequence:** `RULES_THAT_CHOOSE` disappears from `funds/page.tsx`. Which
entry point was used decides `accumulates` at creation; nothing asks.

### C. The panel — one component, content co-located with each screen

`components/screen-help.tsx` owns the mechanics only: the trigger in the header,
the panel shell, keyboard open/close, focus return, the focus trap, and the
full-height sheet on a narrow viewport. It renders whatever content it is given.

**Each page writes its own content** and hands it to `PageHeader` beside the
existing `action` slot.

**Rejected: a central content module keyed by route.** It couples all ten screens
to one file, and the panel's whole point (AC-8) is quoting *that screen's own
figures* — data only that screen has already loaded. A registry would have to
re-fetch or receive everything, which is the coupling the charter's design bar
exists to prevent.

**`QueryBoundary` (ADR-0029) is not touched.** The panel sits outside it: AC-16
requires the panel to open and explain when the screen's figures never arrive,
so it cannot live inside the boundary that hides content on failure.

### D. Empty states — the component already takes the button

`EmptyState` accepts `action` today and 10 of 12 uses don't pass one. The change
is passing it, plus a teaching sentence — which needs one new optional prop
(`description`), since `message` is a label and AC-10 asks for a label *and* an
explanation.

Transacciones is the exception: it renders through `data-table.tsx`, so its
empty state is reached via `emptyMessage`. That path needs the same two props.

### E. The generator learns tags — ADR-0045's first task

Tags live in `spec.md`; `dae_gherkin.py` drops them as free-form markdown and the
IR has no tag field.

**Decided by the owner: read the tags from `spec.md` in the generator**, reusing
`acceptance/spec_coverage.tagged_scenarios`. `generate(feature_dir, only=None)`
gains a name filter; `run-acceptance-tests.sh` passes the `@backend` set for a
`mixed` feature and adds its generated dir to the pytest run.

**Rejected: teaching `dae_gherkin.py` about tags.** It is plugin-owned, portable
and shared across every project using DAE. Editing it is a fork the next plugin
update overwrites. If tags in the IR turn out to be right, it belongs upstream,
not in this repo.

### Where the new code lives

```
backend/src/quaestor/services/funds.py     _look_ahead, three fields on FundStatus
backend/src/quaestor/api/schemas.py        FundStatusOut gains the three
frontend/lib/funds.ts                      shape(fund), the one derivation
frontend/components/screen-help.tsx        the panel's mechanics
frontend/components/page-header.tsx        a help slot beside action
frontend/components/empty-state.tsx        a description prop
frontend/app/(app)/*/page.tsx              per-screen help content, empty states,
                                           the two entry points, the noun split
acceptance/generator.py                    an optional name filter
run-acceptance-tests.sh                    route the @backend subset
```

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| §1 DAE with full ATDD coverage | ✅ | 21 ACs, 113 scenarios, three streams, all red but the five green by design |
| §1 ADRs for significant decisions | ✅ | ADR-0045 written and amended at CP3; product ADR-042 at CP2 |
| §2 Backend layering api → services → domain | ✅ | `_look_ahead` sits in `services`; `domain/rules.py` untouched |
| §2 MCP/REST parity (ADR-0006/0009) | ⚠️ | The three new fields must reach the MCP fund tool too, or parity breaks. Folded into phase 1 rather than deferred — see Amendments |
| §2 `QueryBoundary` as the async contract (ADR-0029) | ✅ | Untouched; the panel deliberately sits outside it, and AC-16 is why |
| §3 English for code, Spanish for UI copy | ✅ | This feature is almost entirely Spanish UI copy |
| §3 pnpm only (ADR-0003) | ✅ | No new frontend dependency at all |
| §3 Conventional Commits | ✅ | In use |
| §5 Agent team roles | ✅ | Implementer ≠ verifier, enforced by `dae_handoff.py` |
| §6 Nothing merges without both suites green | ✅ | Three streams named in Test strategy |
| §7 Human required for migrations / `.dev-data` / main / `dev-real` | ✅ | **No migration, no schema change.** The three fields are computed, not stored |
| §7 Autonomy medium | ✅ | Within `allowed_levels`; no path override applies |
| Verification independence (Principle 7) | ✅ | CP7/CP8 `agent_id` must differ from CP5's |
| Mutation policy (manifest: `opt_in`, `changed_files`) | ✅ | **Opted in on `services/funds.py`.** See Test strategy §4 |
| CLAUDE.md: no code comments | ✅ | Docstrings on public functions only |

### Amendments

**⚠️ §2 MCP/REST parity.** ADR-0006/0009 require the MCP surface to match REST.
Three new fields on the REST fund status create a gap the moment they ship.

**No amendment ADR is needed, because nothing is being deviated from.** The
parity rule is being *honoured*, not bent: the MCP fund tool gains the same three
fields in the same phase as REST. This row is ⚠️ only to record that the
requirement was found during planning rather than after, and that it grew phase 1
by one file (`mcp/tools/`). Had it been deferred, an amendment would have been
required.

## Phasing

Four slices. Each ends green on the streams that can see it.

**Phase 1 — the three figures.** `_look_ahead`, three fields through
`FundStatus` → `FundStatusOut` → MCP tool → frontend type. Closes the 13
`@backend` scenarios. Independent of everything else and the only phase that
touches the backend.

**Phase 2 — the generator learns tags.** `generate(feature_dir, only=…)`, the
runner routing, and the `@backend` subset actually running. Ordered second
because phase 1's scenarios have nothing to run them until it lands — but phase 1
is written first so there is something to run.

**Phase 3 — the two nouns.** The derivation helper, the two entry points, the
vanished checkbox, the two headings, the row copy, and every vocabulary site
AC-21 reaches: Dashboard, Reportes, toasts, delete dialog, empty screen, Ajustes,
and the dead `Excluir del presupuesto` checkbox and its badge. The largest slice
and the one that carries the feature's reason for existing.

**Phase 4 — the panel and the empty screens.** `ScreenHelp`, the header slot, ten
screens' content, the `description` prop and twelve empty states. Last because it
quotes the vocabulary phase 3 settles; writing it first would mean writing it
twice.

## Performance budgets

Not a performance feature, and the one thing that could have been is not.

- **No new DB round-trip.** `_look_ahead` reads the aggregate already in memory;
  the fund read path keeps its current query count. This is asserted, not
  assumed — the rule-by-rule table in Architecture §A is the argument.
- **One extra fold iteration per fund per request.** With the owner's data that
  is single-digit iterations of pure arithmetic.
- **No new frontend dependency**, so no bundle-size budget to state.
- The panel renders from data the screen already has; it issues no request of its
  own, which is also what makes AC-16 satisfiable.

## Collaboration schedule

- **Phase 1** — agent implements; owner reviews the three field *names* before
  they reach the UI, since they become vocabulary and ADR-042 is what this
  feature is about.
- **Phase 3** — the copy is the feature. Owner reviews the Spanish for the two
  headings, the two entry points, the rule picker and the row lines before
  phase 4 quotes them.
- **Phase 4** — owner reviews the Fondos panel against the real sandbox before
  the other nine are written.
- **AC-14** is verified with the owner able to see it: Chrome MCP at 390px, with
  the observation recorded in the CP5 handoff per ADR-0045.

## Execution modes

- **Local, autonomy medium.** `remote.ready: false` — cloud dispatch is not
  enabled, so every phase runs locally.
- Phases 1 and 2 are mechanical and bounded — good subagent work.
- Phases 3 and 4 are copy-heavy and need the owner in the loop; agent drafts,
  owner reads.
- `frontend/AGENTS.md` applies to phases 3 and 4: **this is not the Next.js you
  know** — read the relevant guide in `node_modules/next/dist/docs/` before
  writing component code.

## Test strategy

`feature.md` carries no `validation_method`, so this is the standard DAE stack —
acceptance + unit + mutation per charter — with the three streams ADR-0045
defines.

**1. Generated pytest — the 13 `@backend` scenarios.** What a fund reports.
Runs once phase 2 lands. Their step vocabulary is 003's, verbatim, so
`acceptance/handlers/sinking_funds.py` already binds all but three families —
`spent N COP this month`, `carries N COP into next month`, `will have N COP to
spend next month`.

**2. vitest — the 98 untagged scenarios.** What a screen says and offers. Bound
by `acceptance/spec_coverage.py`, which fails on any untagged scenario with no
test carrying its name. Binding is exact-string; a smart quote leaves a scenario
silently unbound, which errs safe and is recorded as a known sharp edge.

**3. Chrome MCP — the 2 `@browser` scenarios.** Layout and position, which jsdom
cannot see because it has no layout engine and reports every element as
zero-sized. **Evidence rule (ADR-0045): green only when the CP5 handoff records
the URL, the viewport and what was observed.** An unrecorded check is an
unverified scenario.

**4. Mutation — opted in on `backend/src/quaestor/services/funds.py`.** The
manifest default is `opt_in`; this feature opts in on the one backend file it
changes. `domain/rules.py` is untouched and stays out. Run with
`backend/scripts/mutate.py`; 003 measured `funds.py` at 88.2% and that is the
floor to hold, not a target to beat.

**5. The regression proof.** 003's suite — 348 scenarios — is what proves AC-18's
claim that nothing moved, and it must be green at every phase boundary, not only
at the end. Baseline to hold: **348 acceptance, 253 vitest, lint exit 0.**

**6. What no stream covers, stated rather than left implicit.** `spec_coverage.py`
is a gate with no test of its own, matching `generator.py`'s precedent — thinner
justification for a gate than for a generator. Phase 2 adds one, since it is the
phase that touches it. And draft 3 of `spec.md` was approved without a fourth
spec-guardian pass, a residual risk the owner took knowingly.

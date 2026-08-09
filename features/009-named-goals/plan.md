---
slug: named-goals
checkpoint: 4
plan_status: draft
created: 2026-08-08
---

# Plan — 009 named-goals

## Architecture

Settled by **technical ADR-0046** and **product ADR-043**, both accepted
2026-08-08. This section states what they mean for the code rather than
re-arguing them.

### Where the new code lives

```
domain/models.py        Meta, MetaContribution; Transaction.meta_id;
                        Category.counts_as_saving; FundRule loses target_by_date
domain/dtos.py          MetaStatus, MonthSplit; MonthAvailable gains two terms
domain/rules.py         meta_ask_calc, meta_uncovered_calc, split_calc
                        — pure, session-free, next to fund_ask_calc
services/metas.py       create/set/cancel/close/restore/contribute/
                        remove_contribution/preview_meta/meta_status/list_metas
services/funds.py       _uncovered nets linked movements; month_available gains
                        the meta, contribution and release terms; the split
services/month_aggregate.py   two queries: the month's metas, its contributions
api/routers/metas.py    the REST surface
api/schemas.py          MetaOut, MetaStatusOut, MonthSplitOut
mcp/format.py           money_available_card names metas — read only
frontend/app/(app)/metas/       page, create form, card, contribution list
frontend/lib/api/types.ts       the DTOs the screen reads
migrations/versions/    0013 additive, 0014 the withdrawal
```

### The three decisions that shape everything

**Nothing is stored that can be derived.** `Meta` has no balance column, the
same constraint ADR-0043 put on `Fund` and for the same reason: a stored figure
is a second truth that drifts, and AC-27 requires a past month to answer as
that month stood. What a meta holds is a fold, walked arithmetically the way
`_walk` already walks a fund.

**The month always charges its instalment.** `meta_ask_calc(amount, held,
months_left)` is `_ceil_div` at the cent, and it knows nothing about
completing, cancelling or contributing. Those are separate terms in the month,
never adjustments to the instalment. This is the rule the CP3 audits were about,
and putting it in one pure function is how it stays true in all 124 scenarios.

**The identity is asserted, not assumed.** `available_calc` gains two arguments
and stays one expression. `month_available` must satisfy
`income − funds − metas − contributions + releases − uncovered == free` by
construction, and a unit test pins that with property-style inputs rather than
only through the acceptance suite.

### Coupling, deliberately kept low

`services/metas.py` does not import `services/funds.py`. Both read the same
`MonthAggregate` and both hand their asks to `month_available`, which is the
only place they meet. A meta belongs to no category, so nothing in
`services/categories.py` changes except the new flag's write path.

The one real seam is `_uncovered`. Today it takes every posted expense in an
unfunded category plus the excess past each fund. It gains one step before
both: **partition the month's expenses by `meta_id`**, net the linked ones out
of the category arithmetic entirely, and add each meta's own excess. That is
the single place double counting could enter, and AC-12's third scenario — a
gap in a category that *also* carries a fund — exists to catch it.

## Charter Check

| Charter rule | Verdict | Note |
|---|---|---|
| §1 ADRs respected, superseded never contradicted | ✅ | ADR-0046 + product ADR-043; ADR-037's two clauses superseded explicitly, ADR-0044 and ADR-0028 amended in 0046 |
| §2 Backend layering api → services → domain → db | ✅ | `metas.py` is a service; the arithmetic is pure in `rules.py`; the router holds no logic |
| §2 MCP surface with REST parity (ADR-0006/0009) | ⚠️ | **Read parity only.** The assistant names metas in the money-available card and can do nothing else. Deviation stated in ADR-0046's Consequences and in AC-32 |
| §2 Local-only posture, local Postgres is production | ✅ | No remote, no new service |
| §3 English identifiers, Spanish UI copy (ADR-0001) | ✅ | `Meta` is the domain noun and the UI word; that is the ADR-042 precedent for `fondo` |
| §3 pnpm only, Biome, colocated vitest | ✅ | 13 scenarios bind to colocated `*.test.tsx` |
| §3 Soft-delete + restore for masters (ADR-0005) | ✅ | AC-29; ADR-0046 states why a meta gets it where a fund does not |
| §4 Scope: personal finance, single user, local | ✅ | — |
| §6 Nothing merges without both suites green | ✅ | Test strategy below |
| §7 Human required for migrations on real data | ✅ | Two migrations, both in the runbook, both owner-owned, both backup-gated |
| §7 `migrations/**` capped at autonomy `low` | ✅ | Runbook steps are `owner: human` |
| CLAUDE.md — no code comments | ✅ | Enforced in review; the docstring convention stands |
| CLAUDE.md — ADR before architecturally significant code | ✅ | ADR-0046 accepted before any code |
| Verification independence (Principle 7) | ✅ | CP6 refine and CP7 verify run on agents distinct from the implementer |
| Mutation policy (`opt_in`, `changed_files`) | ✅ | Opted in on two modules — see Test strategy |

**Amendments required:** none outstanding. The one ⚠️ has its amendment
already written — ADR-0046's Consequences section states the ADR-0009 and
CHARTER §2/§4 deviation in full, which is what the hard rule requires.

## Phasing

Eight slices. Each ends with its acceptance scenarios green and both suites
green; none is a task list.

**Phase 0 — Ground (human).** `just backup`, then migration `0013`, additive
only: `meta`, `meta_contribution`, `transaction.meta_id`,
`category.counts_as_saving`. Nothing is dropped here, so the app keeps running
on the old code. See `runbook.md`.

**Phase 1 — A meta fills itself.** The record, `services/metas.py`'s read path,
`meta_ask_calc`, and the meta term in the money available. This is the slice
that decides the whole feature: if the fold is wrong here, every later phase
inherits it.
→ AC-1, 2, 3, 4, 9, 17, 18, 20, 21, 22, 26, 27, 31, 34, 45 *(the backend half)*

**Phase 2 — The link on the movement.** `meta_id` on the write path, the
`_uncovered` partition, the fund left untouched, the reports left whole.
→ AC-6, 7, 8, 12, 13, 19, 23, 25, 28, 33, 35, 43

**Phase 3 — The acts.** Contribute, remove a contribution, cancel, close, edit,
restore — each a term in the month, none an adjustment to the instalment.
→ AC-10, 11, 14, 15, 16, 24, 29, 39, 42

**Phase 4 — The split.** consumo / ahorro / libre, the saving-marked category,
the month's report listing metas beside funds.
→ AC-36, 37, 38, 41

**Phase 5 — The withdrawal.** `FundRule.target_by_date` and its two columns
removed, in code first and then migration `0014`. Ordered here because a fund
using the rule would have had somewhere to go by now — production has none, so
this is safe earlier too, but the ordering costs nothing and keeps the risky
step last among the schema changes.
→ AC-40

**Phase 6 — The screens.** `/metas`, the create form with the warning, the
`¿Cómo funciona esto?` panel, the empty state, the order, the phone width.
→ AC-5, 30, 44, and AC-45's frontend scenario

**Phase 7 — The assistant reads.** `money_available_card` names each meta.
Small, last, and separate so the deviation stays visible.
→ AC-32

## Performance budgets

- **The month's read path stays bounded.** ADR-0028's statement count rises by
  **four** — the live metas, the contributions, the amendments, and the posted
  purchases carrying a `meta_id`. Aggregate loads go from 10 to 14, asserted by
  `test_load_issues_bounded_query_count` rather than trusted.

  *Corrected twice, and the correction is the finding.* This plan said two,
  then three. Each addition is an act that had to record its own month because
  a fold cannot recover one. A meta **derives what it holds and stores what the
  owner did to it** — contributions, cancellations, amendments. That is the
  boundary of ADR-0043's derive-everything stance, found by building against
  it.

  **Settled at 13, not 14 (2026-08-09, after CP6.)** The four additions above
  all landed. Refine then merged the month's expense window and its income
  window — two statements over the same two months — into one, which is a
  saving on the pre-existing ten rather than on the four this plan budgeted.
  `BOUNDED_LOADS = 13` in `test_month_aggregate.py` is the asserted figure; the
  budget above is what was planned, kept as written. See ADR-0046, *The read
  path*.
- **The meta fold is arithmetic, not queries.** Walking a meta from its start
  month to the month asked about issues nothing; it is the same shape as
  `_walk`.
- **No N+1 on the screen.** `list_metas` returns every meta's month in one
  pass, the way `list_funds` does.

## Collaboration schedule

- **Phase 0 stops for the owner.** The backup and both migrations are his, in
  person (CHARTER §7). Nothing in Phase 1 starts until `runbook.md` says
  `0013` is applied.
- **Phase 5 stops again** for migration `0014`.
- Everything else runs at autonomy `medium` without check-ins. The owner sees
  each phase's handoff.
- **CP6 refine and CP7 verify run on fresh agents**, distinct from the
  implementer (Principle 7).

## Execution modes

| Phase | Mode |
|---|---|
| 0, 5's migration | Human, in person |
| 1–4 | Local implementer, `atdd:atdd-team` |
| 5 code, 6, 7 | Local implementer |
| CP6 / CP7 / CP8 | Fresh agents, per the charter |

Cloud dispatch is not enabled (`remote.ready: false`).

## Test strategy

`feature.md` declares no `validation_method`, so the standard DAE stack applies
and is stated here explicitly rather than assumed.

**Acceptance — 124 scenarios over 45 ACs, `acceptance_stream: mixed`.**
111 tagged `@backend` generate pytest and bind to `services/`; 13 untagged bind
to colocated vitest. Run by `./run-acceptance-tests.sh features/009-named-goals`.

**The two green pins.** *"A fund saving toward a charge still stops the month
before, unchanged"* and *"The three rules that remain are unchanged"* pass today
and must pass at every phase boundary. They are the regression contract for the
fund.

**003's whole suite is a second contract.** 361 scenarios that must stay green,
because this feature changes `_uncovered` and `month_available` — the two places
003's figures come from.

**Unit tests, in the small.** `meta_ask_calc` at its boundaries: one month left,
an amount that does not divide, an already-full meta, a target month equal to
the start month. And the identity — `income − funds − metas − contributions +
releases − uncovered == free` — pinned directly with generated inputs, not only
through the acceptance suite.

**Mutation testing: opted in**, per the manifest's `opt_in` /
`changed_files` policy, on exactly two modules:

```
backend/src/quaestor/domain/rules.py
backend/src/quaestor/services/metas.py
```

Those are where a wrong figure hides. `services/funds.py` is excluded because
003's suite already mutates its arithmetic and this feature only adds a
partition to it. Run with:
`cd backend && SESSION_SECRET=$(python3 -c "print('x'*64)") uv run pytest -q`

**What is deliberately not tested here.** The assistant's rendered answer is
asserted at the services and formatter layer, never through the LLM — the first
spec had a scenario that would have passed on an empty answer, and it is gone.

## Known gaps carried forward, not solved

Named so the next reader does not mistake them for oversights.

- **Spanish refusals.** Every refusal in AC-20 through AC-25 and AC-39 speaks
  English in production until `id:error-contract` ships. This feature adds
  eight more to the pile.
- **`exclude_from_budget`** is read by nothing since 003 but is set to `true` on
  `🔄 Payment / Transfer` in production. Dead in code, live as data. Belongs to
  the doc-drift cleanup with its own backup, not here.
- **`id:fund-opening-balance`** — product ADR-041 promised a fund the dated
  opening statement that AC-34 now gives a meta. After this ships, metas have
  the field and funds do not.
- **The UX audit's open findings** — D1 (every field marked required), D6
  (English month picker), D10 (tables on a phone), D12 (no thousands
  separators). AC-44 keeps the *new* screen off D10; the rest arrive intact
  because the shared components carry them.
- **Zero funds exist in production**, four days after 003 shipped. Recorded at
  CP3, not acted on. If metas see adoption and funds still do not, that is
  worth a discuss.

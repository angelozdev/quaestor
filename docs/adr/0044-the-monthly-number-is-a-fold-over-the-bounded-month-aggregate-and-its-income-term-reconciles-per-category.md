# 0044. The monthly number is a fold over the bounded month aggregate, and its income term reconciles per category

- **Status:** accepted
- **Date:** 2026-08-04
- **Accepted:** 2026-08-04, after the gap that held it was closed. Checkpoint 7
  withheld acceptance because the `uncovered` term described behaviour the code
  did not implement; product ADR-039 decided the rule, the code now matches the
  paragraph, and six unit tests pin it. One debt is carried openly rather than
  waived: the behaviour has no acceptance scenario yet, because adding one means
  editing an approved `spec.md`.
- **Deciders:** Angelo
- **Supersedes:** — (extends 0028; **0031 stands unamended** — see the
  withdrawn amendment below)
- **Superseded by:** —

## Context and problem statement

ADR-0043 makes a fund's balance derived. This ADR records **where that
derivation runs**, what it costs, and how the headline's income term is
computed — the one term that turned out to be a live defect rather than new
scope.

Two problems, one read path.

**The read path.** ADR-0028 replaced per-category rollover recursion and
per-budget query fanout with a single bounded load: `load_month_aggregate` runs
~8 statements, and every accessor after it reads memory. Feature 003 adds a
per-fund forward fold over months, a per-category average over a window, and a
set of rates — all of which look like they want history the aggregate does not
hold.

**The income term.** `services/budgets._income_forecast` sums the recurring
incomes due in the month and **never reads a posted movement**. Product ADR-004
was accepted seven months ago with the clause *"the forecast is corrected to
actual as transactions post, each counted exactly once"*; that clause has never
been built. The measurement: the forecast reports a flat `$18.128.501` every
month while the record reports `$0` in April and `$45.176.653` in July — both
describing the same two salaries, never compared. Filed separately as
consolidation **C17**, because it is wrong today regardless of this feature.

Prompted by `features/003-sinking-funds/` (acs.md AC-3, AC-9, AC-10, AC-13,
AC-14, AC-14b, AC-14c, AC-17, AC-18).

## Decision drivers

- **ADR-0028 must hold.** The read path stays bounded: a fixed number of
  statements, then memory. No per-fund or per-month query fanout.
- **AC-14 is the term that must not run backwards in time.** The money available
  never counts income that has not arrived; an error here is spent before it can
  be corrected.
- **AC-14b is the term that must be smoothed.** The earning rate, the cost rate
  and the margin are rates — descriptions, never permission to spend — and they
  are never merged with the headline.
- **AC-16**: every figure is derived from what is known now, including past
  months.
- The 92 approved scenarios are the contract; the design has to make them
  runnable as written.

## Considered options

**For the fold's home:**

1. A separate service that issues its own queries per fund and per month.
2. A materialised `fund_month` cache refreshed by the daily job.
3. The fold inside `MonthAggregate`, over data it already loads.

**For the income term:**

1. Keep the forecast as-is (expected only) — leaves ADR-004's clause unbuilt.
2. Take the maximum of expected and posted per month.
3. **Per income category**: what actually arrived this month if anything did,
   otherwise what the category's obligations promise.
4. Per recurring item: drop an obligation's expectation once its own occurrence
   posts, and separately handle posted income carrying no recurring link.

## Decision outcome

### The fold lives in the month aggregate; the read path grows by two statements

Chosen: **3**. The fold needs posted expense per (category, month) from each
fund's start month forward — which `_spent_by_cat_month` already holds as GROUP
BY sums for *all* history, loaded in one statement. The `average` rule needs the
same data over a window. The `from-recurring` rule needs active recurring items,
already loaded. None of it is a new query.

Net change to `load_month_aggregate`:

| | |
|---|---|
| removed | `SELECT * FROM budget` (the table is dropped) |
| added | `SELECT * FROM fund` |
| added | recurring occurrences for the report month — AC-17 (a skipped charge lowers its fund's ask) and AC-14c (an income that already posted) |
| added | `MIN(date)` over posted movements — AC-3's *"a month the app has no data for is not counted at all"* |
| **net** | **+2 statements on ~8** |

The fold itself is O(funds × months since the earliest start): at the real scale
7 funds × 12 months, 84 in-memory steps.

Option 2 (a materialised cache) is rejected for the same reason ADR-0043
rejected a stored balance: it needs a job to stay true, and a cache that
disagrees with the rule is worse than no cache. Option 1 is the fanout ADR-0028
exists to prevent.

### The income term reconciles per income category

Chosen: **3**.

```
income(M) = Σ over income categories:
    what actually arrived in the category this month, if anything did
    otherwise, what that category's obligations promise for this month
```

Against the scenarios: a salary expecting `$5.000.000` where `$4.200.000` was
recorded counts `$4.200.000`, not `$9.200.000` (AC-14c). A salary the engine
already posted counts once (AC-14c). Money recorded with no obligation behind it
counts from the moment it is recorded (AC-14c). A quarterly bonus contributes
nothing to August and all of itself to September (AC-14).

**This is product ADR-004's reconciliation clause, finally built.** ADR-004 is
therefore *not* superseded — its forecast clause is split across the headline
(AC-14) and the earning rate (AC-14b), and its unbuilt clause becomes AC-14c.

Option 2 (maximum of expected and posted) is rejected because it fails AC-14c
outright: it would report `$5.000.000` for a month where `$4.200.000` actually
arrived, which is exactly the direction of error that gets spent.

#### A declared boundary: the reconciliation is per category, not per obligation

Two obligations in the same income category where only one has posted: the
other's expectation is dropped too, and the month counts only what arrived.

Option 4 would fix that, at the cost of a matching rule between posted incomes
and obligations — by `recurring_id` where present, and by something weaker where
absent. Production offers no evidence for the weaker rule: the history is a
Lunch Money import and the app has been in real use about a month, so the 20-of-
22 unlinked incomes are migration artefacts, not a pattern.

The chosen rule is one sentence the owner can hold: *once money lands in an
income category, that category stops guessing.* Written here, as ADR-0041's D4
was, so nobody "fixes" it later without knowing it was chosen. Revisit when
there is real evidence of two obligations sharing one income category.

### The three terms, and the two numbers that are never merged

```
free(M)  = income(M) − Σ funds asks(M) − uncovered(M)
```

`uncovered(M)` is everything no fund covers: posted spending in categories with
no fund, what those categories' obligations still promise for turns that have
**not** posted, planned payments no fund covers, and the excess past a fund's
holdings (AC-13 — only the excess leaves the money available, never the whole
amount). One term, because the breakdown must add up exactly:
`income − Σ asks − uncovered = free` is asserted by AC-10.

**The expense term stops guessing turn by turn, mirroring the income term.** A
charge that posted is counted at what actually left the account; a turn still
ahead carries what its obligation declared. So an obligation declaring
`200.000` whose bill posts at `250.000` costs the month `250.000`, one that
posts at `150.000` costs `150.000`, and one switched off *after* its charge
posted still costs the `200.000` that really left. Every posted expense is
counted exactly once, at its real figure.

The reconciliation is finer here than on the income side, and deliberately: a
posted expense carries the `recurring_id` of the turn that produced it, so each
posted charge replaces exactly one promised turn. Income has no such link,
which is why its boundary is per category (above). A weekly obligation with one
turn posted and three ahead therefore counts one real amount plus three
promises.

Recorded as product ADR-039, decided by the owner on 2026-08-04. The
alternatives — always the declared amount, or the greater of the two — were
weighed and rejected: the first is what the defect did, and the second hides
money from the owner in every month a bill comes in cheap.

Separately, and never mixed in:

```
earning(M) = Σ recurring incomes, each ÷ the months of its cycle
cost(M)    = Σ funds asks(M) + obligations no fund covers, normalised
margin(M)  = earning − cost
```

A quarterly `$3.000.000` bonus contributes `$1.000.000` to the earning rate in
every month of its cycle, and `$0` to the money available until the month it is
due. The gap between the two numbers carries information rather than noise.

#### The gap this ADR was held over, and how it closed

Checkpoint 7 refused to accept this ADR because the paragraph above described
an `uncovered(M)` that `services/funds._uncovered` did not compute: a posted
expense carrying a `recurring_id` was skipped from the spending term on the
assumption that the obligations term covered it, and that term summed what each
obligation **promised**, never what posted. An obligation declaring `200.000`
whose charge posted at `250.000` left `50.000` off the headline; switched off
after posting, the whole `200.000` vanished and the money available read that
much **too high** — the direction that is spent before it can be corrected.

AC-16 justifies dropping a **promise** when an obligation is switched off. It
never justified dropping a **posted movement**.

The suite was green over it because no approved scenario records a recurring
charge, in a category with **no fund**, posting at anything other than the
amount promised. Neither did mutation testing catch it: mutation measures
whether tests discriminate behaviour that *exists*, and the tests pinned the
defective behaviour, so its mutants died. A missing requirement has no mutant.

Closed 2026-08-04 by the owner's decision (product ADR-039), implemented as the
`uncovered(M)` paragraph now states, and pinned by six unit tests in
`backend/tests/services/test_funds.py`. **Still owed: an acceptance scenario.**
Adding one means editing an approved `spec.md`, which is the owner's to
authorise; until it exists this behaviour is defended by unit tests alone and
would not be caught by the acceptance contract if it regressed.

### Withdrawn: the lazy TRM. ADR-0031 stands unamended

**This section proposed an amendment to ADR-0031 and the owner rejected it. It
is kept as the record of what was proposed, on what evidence, and why the
answer was no.**

ADR-0031 established that read paths producing COP figures call `get_trm` and
**fail loud** when no rate is set; writes use `get_trm_or_none` and succeed
without one. `safe_to_spend`, `list_budgets` and `budget_status` all fail loud
today.

**What was proposed.** That their replacements — `available`, `rates`,
`fund_status`, `list_funds` — fetch the rate **only when a non-COP amount is
actually encountered**. A COP-only month would need no rate; a month holding a
US$30 obligation would still fail loud without one.

**The measurement behind it.** 85 of the 92 approved scenarios of feature 003
set no TRM. Only AC-18's three do, because it is the AC about currency. Read
literally, under fail-loud, the approved contract could not pass.

**The owner's ruling, 2026-08-04.** *"La tasa se aplica al entrar en la app.
Siempre debe estar (mientras creamos un feature que obtenga la TRM por debajo
día a día)."* The rate is demanded **on entry**, on every read path, always —
and a rate must always be set. The friction is accepted because it has a named
expiry: a future job that fetches the TRM day by day, after which the rate is
never missing in practice. Recorded as product decision **ADR-038**.

**Why the measurement did not force the amendment.** It measured the specs, not
the app. A running Quaestor always has a rate; the 85 scenarios were silent
about it, not dependent on its absence — every scenario that makes the missing
rate its subject says `Given no TRM has been set` explicitly, nine times across
002, 005 and 006. The specs are therefore satisfied by **seeding the rate as
background state** in the acceptance `World` (`SEEDED_TRM`, a value that appears
in no spec so an accidental dependency comes out wrong rather than
coincidentally right), and `Given no TRM has been set` now clears it. No spec
was touched and no read rule was relaxed.

That also removes a collision the amendment had created: 005's AC-9 asserts a
report with no rate is refused, while 003's AC-12 reads a pure-COP month's
report — two specs, one global step registry, and under the lazy rule they
contradicted each other. Under the entry rule and a seeded World, both hold.

**The accepted cost.** A month recorded entirely in pesos still cannot be read
until a USD→COP rate is set. The owner knows this and accepts it: one rule to
remember instead of two, consistent with product ADR-030, which already made
the same call for the outstanding queue.

## Consequences

- **Good:** ADR-004's reconciliation clause exists for the first time, and
  consolidation C17 closes with it.
- **Good:** the whole feature costs +2 statements on the read path, and no new
  history query — the fold rides data ADR-0028 already made available.
- **Good:** the headline's breakdown adds up by construction, so nothing in it
  is unattributable (AC-10).
- **Good:** ADR-0031's "reads fail loud" stays uniform. There is one rule, not
  two, and no reader has to know which figures crossed the converter.
- **Bad / cost:** the per-category reconciliation boundary, above.
- **Bad / cost (accepted by the owner):** **a month recorded entirely in pesos
  still cannot be read until a USD→COP rate is set.** This is the price of the
  withdrawn amendment and it is paid on entry to every read path. It expires
  with the daily-TRM job on the roadmap.
- **Bad / cost:** the fold's growth over years, carried from ADR-0043.

## Confirmation

- `features/003-sinking-funds/spec.md`. The income term is pinned by AC-14c's
  four scenarios and AC-14's three; the two-numbers separation by AC-14b's five,
  which assert the earning rate and the money available in the *same* scenario
  and expect them to differ (`6.000.000` a month against `5.000.000` available).
- The breakdown's arithmetic is asserted directly: `the breakdown adds up to the
  money available` (AC-10).
- Read-path cost: `backend/tests/api/test_reports_query_count.py` already pins
  the statement count for the report path and is the place the +2 is recorded.
- The entry-time TRM is asserted from both sides: the nine scenarios across
  002, 005 and 006 that say `Given no TRM has been set` and expect a refusal,
  and AC-18's three that set a rate and expect the ask to move with it. The 85
  silent scenarios assert nothing about the rate — the acceptance `World` seeds
  one as background state, as a running app has.

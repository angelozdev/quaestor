# 0049. Closing leaves the screen, not the month, and a purchase stops only what the owner has not restarted

- **Status:** accepted
- **Date:** 2026-08-09
- **Deciders:** Angelo
- **Supersedes:** the three implementation clauses of [0048](0048-a-purchase-stops-the-meta-and-closing-it-moves-no-figure.md). Its decision — *a purchase ends the instalment series from the following month, and closing moves no figure* — stands unchanged.
- **Superseded by:** —

## Context and problem statement

ADR-0048 was taken an hour before this one and its decision was right. Its
Decision Outcome then spelled out how to implement it in four bullets, and
**three of the four were wrong.** A second independent verifier
(`subagent-verify-cp5-round2`, handoff `2026-08-09T1400-verify-round2.md`)
traced the 45 acceptance criteria against the shipped code and found nine
wrong; seven were this.

Every one of the four gate streams — 1063 backend tests, 417 frontend tests,
472 acceptance scenarios, lint — was green over all of it.

**Clause 1 said `statuses()` drops closed metas.** So the month went on
charging a closed meta through `asks_total()` while nothing named it. The money
available stayed correct and became unexplainable:

```
dashboard   Ingreso 5.000.000 − Sin fondo 0        sobre  Disponible 3.400.000
asistente   Income 5000000.00 / Uncovered −0.00    sobre  Available 3400000.00
reporte     asked 1.600.000                        sobre  una sección Metas vacía
reparto     ahorro 0 · libre 5.000.000             en los cinco meses
```

`libre` stopped equalling `free`. AC-38's December that must read 54 % saved
read 0 %. The assistant card printed verbatim the shape product decision 15
exists to prevent.

**Clause 2's stop was unconditional**, so AC-8's second and third offers moved
no figure: a meta kept on with a new amount or a new month reported `pide 0,00`
for the rest of its life. And `contribute` still accepted money for it — 201,
charged to the month, listed under *Ver aportes*, counted as ahorro, with the
meta holding exactly what it held before. Money entered and reached nothing.

**Clause 3 read the purchases without saying posted-only**, and it was
implemented not-posted-only. AC-43 says the opposite in its own words: a
planned purchase *"does not complete, **it keeps asking**"*. The test that
pinned the wrong behaviour was written in the same session **to kill a
mutant**. The mutant was right and the test was wrong.

## Decision drivers

- **The identity must not only hold, it must be explainable.** `income − Σ
  claims = free` was true throughout. A breakdown that omits a claim it charges
  is a correct total nobody can check.
- **AC-27 is month-derived, and `closed` is a timeless flag.** Filtering on it
  erases the meta from months it demonstrably ran through.
- **A test that kills a mutant is not thereby a correct test.** Mutation says a
  behaviour is undistinguished, never that it is right.

## Considered options

1. **Filter closed metas out of `statuses()`** — ADR-0048's clause, and the
   defect.
2. **Filter in `list_metas`, on the timeless `closed` flag.**
3. **Filter in `list_metas`, from the month of the purchase.**

## Decision outcome

Chosen option: **(3)**, with two further corrections.

- **`statuses()` returns every meta the month charges, closed ones included.**
  It is what the breakdown, the report, the split and the assistant all read,
  and each of them must name every claim or stop adding up.
- **`list_metas` — the /metas screen, and only it — drops a closed meta, from
  the month its purchase was made.** The aggregate carries only purchases on or
  before its own month, so a September read of a meta closed in December sees
  no purchase and lists it, holding and asking what it held and asked. No date
  arithmetic and no stored month.
- **An amendment resumes the meta**, and it stays resumed. Saying a meta wants
  a new amount or a new month is AC-8's second and third offer, and it starts a
  new series from the month the owner said it. **The purchase month counts as
  one where he may say it** — that is where the screen puts the offers, on a
  meta that completed the moment its purchase was linked. An amendment later
  than the month being read never reaches back into it (AC-27). Both edges were
  found by mutation after this decision was drafted, and both mutants were
  right. `_room_left` answers zero for a meta that has finished, so a
  contribution to one is refused rather than swallowed.
- **`_bought_in` is posted-only.** Netting a debt against what a meta holds is
  the month's arithmetic (AC-12); the meta finishing is a different question and
  only money that left answers it (AC-43, ADR-0044).

And one defect older than ADR-0048, exposed by making dollar metas creatable:
**`MetaStatus` now carries `asks` in the meta's own currency and `asks_cop` in
the month's pesos**, named as such. The dashboard breakdown, the assistant card
and the split all summed the first as if it were the second — a USD 333,34
instalment counted as $333. `released` was already pesos without saying so; the
docstring now says which figures are which and why.

### Pros and cons of the options

**(1) Filter in `statuses()`**
- Good, because it is one line and every list-shaped caller gets it free.
- Bad, because every list-shaped caller is not a list: four of them are the
  month's arithmetic explaining itself.

**(2) Filter in `list_metas` on `closed`**
- Good, because the screen is the only place the flag means anything.
- Bad, because `closed` has no month and AC-27 requires one — it empties the
  past on the screen exactly as clause 1 emptied it everywhere.

**(3) Filter in `list_metas`, from the purchase month**
- Good, because it is derived from the aggregate's own window and needs nothing
  stored.
- Good, because it is the same fact the stop already reads.
- Bad, because a meta closed long after its purchase disappears from the months
  between the two. That is the correct reading: from the purchase on, it is
  finished business.

## Consequences

- Good: `libre` equals `free` again, and every claim the month charges is named
  by the column that charges it.
- Good: AC-8's three offers all move money, and no contribution can be accepted
  by a meta that cannot take it.
- Bad / cost: `MetaStatus` carries two currencies. The alternative was to
  convert in three screens and one formatter, which is where the bug was.
- Bad / cost: **the acceptance suite still cannot see any of this.** No scenario
  of AC-4, AC-31, AC-36 or AC-37 closes a meta; AC-39's only close is in January
  over a December purchase, where nothing can move; AC-27 cancels rather than
  closes; AC-43 only asserts *is running*. 472 green scenarios saw nine wrong
  ACs. Closing that needs new scenarios in `spec.md`, which is the owner's
  contract and was not modified.

## Confirmation

`backend/tests/services/test_metas.py` pins each correction by name:
`test_a_closed_meta_is_still_named_by_the_month_that_pays_for_it`,
`test_a_month_the_meta_ran_through_still_names_it_after_it_is_closed`,
`test_a_meta_kept_on_with_a_new_amount_asks_again`,
`test_a_meta_kept_on_with_a_new_month_asks_again`,
`test_a_finished_meta_takes_no_more_money_instead_of_swallowing_it`,
`test_a_purchase_owed_but_not_yet_paid_leaves_the_meta_asking`,
`test_a_dollar_meta_says_what_it_costs_the_month_in_pesos`, and
`test_a_dollar_meta_is_saved_in_pesos_like_everything_else_in_the_split`.

`backend/tests/api/test_metas.py::test_a_closed_meta_stays_in_the_breakdown_it_still_costs`
asserts the same thing over REST, where the verifier reproduced it.

Each fails against the code as ADR-0048 left it.

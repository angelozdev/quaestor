---
ac_count: 28
high_priority_count: 19
discovered: 2026-08-03
---

# Acceptance criteria — 003 sinking-funds

Discovered 2026-08-03 (Checkpoint 2), greenfield mode. The behaviour specified
here does not exist: it replaces the shipped envelope/goal/safe-to-spend
surface rather than documenting it.

Source material: `feature.md` and its eight decisions from the 2026-08-02
`discuss`, read-only measurements against the production Postgres (ADR-0030),
the shipped read path (`services/budgets._income_forecast`,
`services/month_aggregate`, `services/reports`), and an industry comparison
against YNAB and Actual Budget on the four points where `feature.md` left the
answer open.

## Two figures in `feature.md` are wrong, and the corrections shape the ACs

**"8 funds derivable from recurring items" — it is 7.** The expense categories
holding an active recurring item are Services, Software, Auto Insurance, Rent,
Home Maintenance, Internet and Fitness. Two income categories (Salary, Bonos)
hold the rest. The 3 → 7 lift still justifies having sequenced 008 first; the
8 was miscounted.

**"Internet resolves to its exact $85.000" — 🌐 Internet holds three recurring
items**, totalling $161.400/month (Internet Hogar $85.000, Plan de datos
$38.900, Plan de datos Mamá $37.500). It is not the exception: 🛡️ Auto
Insurance holds two annuals ($7.000.000 + $447.300) and 🔥 Services holds two
items with *different* intervals (EPM $250.000 monthly, DolarApp Premium
US$69,99 yearly).

`feature.md` describes `from-recurring` as a "linked recurring item", singular.
The data says several is the normal case, which is what AC-4 answers.

## Decisions taken during discovery

**1. A dated obligation divides by the months remaining, not by twelve.**
Verified against the references before deciding. Actual Budget's schedule
template funds an upcoming charge *over the months until it lands* — a $1.200
May insurance budgeted from January spreads over five months, not twelve — and
its by-date template recalculates *what is missing ÷ months remaining* each
month. YNAB documents the same first-year behaviour: it lets you save for the
first yearly expense even when the target is created less than a year ahead.
Neither offers a fixed ÷12 as an option; both derive it.

The owner's own decision 3 settles the tie: the headline must tell *"la verdad
desde el inicio"*. A fixed ÷12 shows $37.275/month for the SOAT and then comes
up $111.825 short on 2027-05-02, with nothing having announced it.

**2. The fund carries a start month the owner chooses.** Added at discovery,
not in `feature.md`. The division runs from that month, so a fund can be
configured today and begin contributing in November.

**3. The fund is whole the month *before* the charge.** The charge month does
not contribute. The SOAT charging 2027-05-02 from a November start spreads over
six months at $74.550 rather than seven at $63.900 — otherwise the money is
still $63.900 short on the morning it is taken.

**4. The budget and the record are different surfaces, and both are right.**
The owner asked whether the July 2027 report must still show the $7.000.000
payment if the fund absorbs it. It must, and no compromise is needed: in every
envelope budgeter, spending reduces *its own* envelope rather than the global
pool, while the transaction stays whole in the register and the reports.
Quaestor already splits these — the monthly report builds its category
sections from real movements and its envelope lines separately — so AC-11 and
AC-12 are two surfaces, not a trade-off.

**5. Non-monthly income is smoothed, over a stated objection.** The owner was
shown the asymmetry: smoothing an *expense* forward is conservative (money is
held that may not be needed), while smoothing *income* forward is optimistic
(money is counted that may not arrive), and YNAB forbids the second outright —
its rule is to budget only what is already in the account, because anticipating
income creates a false sense of available funds.

The owner chose to smooth anyway, with a reason that answers the objection:
**a recurring income is a declaration of what you count on, and the abnormal
case is an edit, not a detection.** If the bonus stops or the job ends, the
recurring item is edited and every month recomputes. This is why the app does
*not* try to notice a missed payment on its own — see AC-15.

Note that "the month it falls due" is what the app does *today*
(`_income_forecast` counts the occurrences due inside the month), so the
smoothing in AC-14 is the change, not the status quo. This decision supersedes
product ADR-004's forecast clause for non-monthly income; ADR-004 itself named
the trigger — *"revisit if income becomes very irregular"*.

**6. Nothing is frozen; every month recomputes from what is known now.** This
is already true of the shipped code, and it is where Quaestor departs from both
references. In YNAB and Actual, what was assigned in August is a stored fact.
In Quaestor the whole number is derived, so switching a recurring item off today
changes August's figure too. The owner chose to keep that. The cost is stated in
AC-16: a screenshot of August's number will not always match the app.

**7. The average has one form, not a configurable one.** Two reasons a month
can be empty were separated: *the month has no data at all* (the app's history
starts 2026-01) versus *the month existed and nothing was spent*. The first is
unknown and is excluded from the division; the second is a real zero and counts.
With that separated, the remaining choice — 🎢 Entertainment's single $430.950
over three months giving $143.650 or $430.950 — is not two ways to average but
two different questions, and only one of them is a budget. The other one is
already reachable: it is the `fixed` rule.

Dividing by the *category's* own history was rejected: 🛡️ Auto Insurance, whose
first movement is 2026-06-21, would read $3.619.109/month, so any new category
would look like the largest expense in the app.

**8. Actual Budget is permissive where this app cannot be.** Actual's average
template neither errors nor warns on thin history. Quaestor cannot copy that:
Actual's user sees a budget grid every month, where a $0 row is visible, and
decision 2 deliberately removes that ritual here. A fund silently asking $0
forever is a fund nobody opens again — hence the refusal in AC-23.

**9. The Korea goal is not migrated.** The owner corrected the premise during
discovery: the $14.659.572 sitting in the 🇰🇷 Korea account is *not* the goal's
progress — *"olvida la cuenta"* — the $10.000.000 exist but have never been
registered, and the owner is waiting for this feature to register them. That
correction is this feature's thesis stated by its owner. The goal is
nonetheless not migrated, because decision 5 says the app starts empty and the
moment the owner sits down to register the money is the moment they create the
fund.

**10. The assistant keeps parity, reversing a mid-discovery call.** The owner
first excluded the assistant ("no lo uso"), then asked whether including it was
actually cheaper. It is: the goal tools are deleted either way, `set_budget` is
the very tool funds replace, the rules live in the services layer so the tools
inherit every refusal free (008's AC-14 needed no code for exactly this
reason), and skipping parity would require an ADR overriding charter §2.

---

## AC-1: A fund is created on a category and asks for a monthly amount

- **Priority:** high
- **Type:** happy-path

A fund is created on one expense category, with a name inherited from the
category, a funding rule and a start month. From that month on it asks for a
monthly amount, and that amount is subtracted from the money available to spend.

There is no monthly ritual. Once configured, a fund costs nothing per month
forever — the rule is the number.

## AC-2: A fund asks a fixed amount when the owner names one

- **Priority:** high
- **Type:** happy-path

Under the `fixed` rule the fund asks exactly the amount typed, unchanged month
to month until the owner changes it.

## AC-3: A fund asks the average of what the app has recorded

- **Priority:** high
- **Type:** happy-path

Under the `average` rule the fund asks what was spent in that category, divided
by the completed months the app holds data for, over a window the owner chooses
per fund. A month inside that window with no spending counts as zero; a month
the app has no data for is not counted at all.

The fund states how many months the figure was computed over, so the number is
never magic. 🎢 Entertainment, whose only movement is $430.950 in June, asks
$143.650 over a three-month window.

## AC-4: A fund derived from obligations sums every obligation in its category

- **Priority:** high
- **Type:** happy-path

Under the `from-recurring` rule the fund asks the monthly equivalent of **every**
recurring item filed under its category, added together. 🌐 Internet asks
$161.400 (three items), 🛡️ Auto Insurance asks $620.608 (two yearly items). A
new obligation filed under the category raises the fund without the owner
touching it.

## AC-5: A dated obligation is spread over the months that remain

- **Priority:** high
- **Type:** happy-path

For an obligation with a known charge date, the fund asks what is still missing
divided by the months remaining between its start month and the charge, and
recomputes that every month. The SOAT's $447.300, first charged 2027-05-02 from
a November start, asks $74.550 a month.

The amount changes when reality does: putting in more one month lowers the next.

## AC-6: The fund is whole the month before the charge

- **Priority:** high
- **Type:** edge-case

The month the charge lands does not contribute. The money is complete on the
last day of the preceding month, so a charge on the 2nd finds it waiting.

## AC-7: A fund that gets drained raises its ask to still arrive

- **Priority:** high
- **Type:** edge-case

If spending empties a fund that is saving toward a dated charge, the fund raises
its monthly ask so the charge is still met. 🛡️ Auto Insurance emptied of
$3.000.000 with six months left before a $7.000.000 charge asks $1.166.666 a
month from then on, not $636.363.

## AC-8: A fund accumulates or resets, and the choice is offered only where it exists

- **Priority:** medium
- **Type:** happy-path

A fund either carries its balance forward or starts each month fresh. The owner
chooses **only** where both make sense — the `fixed` and `average` rules, where
🍽️ Restaurantes resets and 💻 Tecnología accumulates.

Rules that save toward a date always accumulate, and are not asked. A car
insurance fund that reset every month would never reach $7.000.000.

## AC-9: The money available this month is what is left after every fund

- **Priority:** high
- **Type:** happy-path

The headline is the month's income, minus what every fund asks, minus spending
in categories no fund covers. It replaces the previous figure outright — the two
are never shown side by side.

## AC-10: The headline shows its work

- **Priority:** high
- **Type:** happy-path

The number opens into the terms that produced it: the income it counted, each
fund by name and amount, and the uncovered spending. Nothing in the headline is
unattributable.

## AC-11: The fund pays its own obligation and the headline does not move

- **Priority:** high
- **Type:** happy-path

When the charge a fund was saving for finally lands, and the fund holds enough,
the money available that month is unaffected. It was already set aside, month by
month. The fund empties and its next cycle begins.

Charging it against the headline as well would take the same money twice.

## AC-12: The record still shows the payment in the month it happened

- **Priority:** high
- **Type:** cross-cutting

A movement paid by a fund appears in that month's report like any other — same
category, same amount, same date. What a fund changes is the plan, never the
history.

## AC-13: Spending past a fund reduces the headline by the excess only

- **Priority:** high
- **Type:** edge-case

Spending more in a category than its fund holds takes the difference from the
money available, not the whole amount. A fund never carries a negative balance
into the next month.

## AC-14: Income that does not arrive monthly is counted at its monthly equivalent

- **Priority:** high
- **Type:** happy-path

A recurring income arriving on a longer cycle is counted at its per-month value
in every month of that cycle — the quarterly US$2.847 bonus counts US$949 in
each of the three. When the money actually arrives it is not counted again.

## AC-15: Income that stops is a change the owner makes, not something the app detects

- **Priority:** high
- **Type:** error

The app never decides on its own that an expected income has failed. When a
salary ends or a bonus is cancelled, the owner edits or switches off the
recurring income and every month recomputes immediately, with no separate
recalculation step.

## AC-16: Every figure is derived from what is known now, including past months

- **Priority:** medium
- **Type:** cross-cutting

Nothing is stored as a monthly snapshot. Asking for August's available money
after switching off an income in October gives August's figure *without* that
income. The number is always consistent with today's data and never with a
screenshot taken earlier.

## AC-17: A skipped charge lowers its fund's ask that month

- **Priority:** medium
- **Type:** edge-case

Skipping a charge because it will not happen lowers what its fund asks that
month by that amount, and the difference returns to the money available. Skipping
Plan de datos Mamá's $37.500 leaves 🌐 Internet asking $123.900 that month.

## AC-18: A fund covering money in another currency asks in the currency of the headline

- **Priority:** medium
- **Type:** edge-case

Obligations recorded in another currency are converted at read time, as
everywhere else in the app. 🏋️ Fitness (US$30 monthly) and the two yearly
dollar subscriptions each contribute their converted value, and the fund's ask
moves with the rate rather than freezing at creation.

## AC-19: A fund that already holds money is told so once

- **Priority:** medium
- **Type:** happy-path

At creation the owner may type what the fund already holds. That figure is
recorded once and never re-read from anywhere: no fund tracks an account
balance, before or after.

## AC-20: The app starts with no funds at all

- **Priority:** medium
- **Type:** happy-path

No fund is created automatically from recurring items or from spending history.
Every fund exists because the owner made it. Once a fund exists and carries an
`average` or `from-recurring` rule, the rule still computes its own amount —
that is the rule working, not a proposal.

## AC-21: A category holding a fund cannot be archived

- **Priority:** high
- **Type:** error

Archiving a category that has a fund is refused, naming the fund and what it
holds. The owner deletes the fund first. Archiving must never silently release
money that was set aside.

## AC-22: A fund cannot be created on an income category

- **Priority:** high
- **Type:** error

A fund sets money aside for spending, so it is refused on a category that
records money coming in. Such a fund could never be spent against, so it would
depress the money available forever with no way to clear it.

## AC-23: The average rule is refused where nothing has ever been spent

- **Priority:** medium
- **Type:** error

Choosing `average` on a category with no recorded spending at all is refused,
and the refusal names the alternative — a fixed amount. A category with even one
month of spending is accepted, and the fund states what it computed over.

## AC-24: A target that cannot be reached is announced before the fund exists

- **Priority:** medium
- **Type:** error

Creating a fund whose target and date require an implausible amount this month
stops and says so, with the figure. The owner may continue, and then the fund
asks that amount in full. The surprise arrives at creation, never on the
headline.

## AC-25: A category carries at most one fund

- **Priority:** medium
- **Type:** error

Creating a second fund on a category that already has one is refused, naming the
existing fund.

## AC-26: Goals disappear as a concept

- **Priority:** high
- **Type:** cross-cutting

The goals screen, the goal records and the month-end routine that proposed one
transfer per goal are all removed. A goal was a fund with a target and a date,
and that is the only form it keeps. Nothing in the app afterwards requires a
savings account to express an intention.

## AC-27: The proposed goal transfers that were never confirmed are removed with them

- **Priority:** high
- **Type:** cross-cutting

The three unconfirmed $3.000.000 transfers the Korea goal proposed — one
declined 2026-06-30, two still pending for 2026-07-31 and 2026-08-31 — are
removed, and the to-pay queue no longer shows them. They were proposals from a
routine that no longer exists and never moved money.

Real records are being deleted from production, so this runs behind a fresh
backup and explicit human authorisation (charter §7, ADR-0030). Every other
record is left untouched — no envelope has ever been created in the app's
history, so there is nothing else to convert.

## AC-28: The assistant reaches funds exactly as the browser does

- **Priority:** high
- **Type:** cross-cutting

Every fund can be created, changed, listed and removed by talking to the
assistant, and the available money and its breakdown can be asked for in words.
Each refusal and each warning above holds identically there. The goal tools are
removed with the goals.

---

## Left open for the spec (Checkpoint 3)

- The exact wording each refusal uses. UI copy is Spanish (charter §3), and
  domain refusals currently reach the toast in English — consolidation C9.
- Whether the fund list gets its own screen or replaces the budgets screen.
- The shape of the headline's breakdown when many funds exist — one line per
  fund, or grouped.

## Known consequences to carry into the plan

- **This feature closes consolidation C14.** `set_budget` accepts an envelope on
  an income category today and depresses the headline permanently; AC-22 is the
  same refusal on the surface that replaces it.
- **Consolidation task 15** (budgets + safe-to-spend ATDD coverage) is unpaused
  by this feature, and its owed follow-up — "archived and budget-excluded
  categories cannot hold an envelope" — is superseded by AC-21 and AC-22.
- **Consolidation task 14** (goals coverage, cancelled 2026-08-02) can be
  deleted once this ships, per its own note.
- **Product decisions requiring a formal supersede at build time:** ADR-003
  (safe-to-spend as unassigned money) and ADR-004 (forecast income) are replaced
  by AC-9 and AC-14; ADR-006 (goals) is removed by AC-26. ADR-002 (envelopes +
  rollover) and ADR-005 (overdraft eats the pool, no negative rollover) survive
  unchanged and are relied on by AC-13.
- **Feature.md notes this is too large for one pipeline run.** Nothing in these
  ACs contradicts that; the phasing decision belongs to Checkpoint 4.

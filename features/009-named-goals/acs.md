---
ac_count: 35
high_priority_count: 22
discovered: 2026-08-08
---

# Acceptance criteria — 009 named-goals

Discovered 2026-08-08 (Checkpoint 2), greenfield mode. Nothing specified here
exists: migration `0012` dropped `goal`, `goal_contribution`, `budget` and
`transaction.goal_id` on 2026-08-04, and the app currently has one noun for
planned money — the fund.

Source material: `feature.md` and the discuss of 2026-08-05 that promoted it,
the prime-context handoff of 2026-08-08 and its three findings, product ADR-037
and ADR-042, the shipped fund arithmetic (`domain/rules.py`,
`services/funds.py`), the navigation as feature 010 left it, and current
practice in four comparable systems (verified during discovery, cited below).

## Why these ACs exist

The roadmap item this feature came from had recorded the obvious fix as
**failing**: two funds on one category cannot answer *"which one did this
$200.000 charger come out of"*, and asking per purchase reinstates the monthly
ritual feature 003 exists to delete.

Linking on the **movement** rather than on the **classification** dissolves it.
The ordinary charger is linked to nothing and behaves exactly as it does today;
the one purchase that matters is named once, on the day it happens. That is an
event, not a ritual.

## What was verified against current practice

Consulted during discovery, before any option was put to the owner (CLAUDE.md).

| System | Separate noun? | In a category? | The target month |
|---|---|---|---|
| YNAB | No — a *target* on the category | It **is** the category | two target types, one for spending and one for a bill |
| Actual Budget | Templates, not a noun | It **is** the category | **the target month funds too** — `#template 10000 by 2025-12` |
| Firefly III | Yes — *piggy banks* | No | optional, and the date-less case was a real bug |
| Monarch Money | Yes — *Goals* | No | optional; linked expense counts in the goal, budget actuals untouched |

Three of these decided an AC below:

1. **Actual Budget's own worked example is this exact case** — a car bought in
   December, $10.000 target, January start with $1.500 already saved, budgeting
   $708,33 a month. That is $8.500 over **twelve** months, January *through
   December inclusive*. The month you buy in is a month you save in (AC-2).
2. **Firefly III issue #5269** — a user asked for a piggy bank with no target,
   only a monthly amount, and until it was fixed his workaround was *setting a
   fake ten-year target so the app would compute a monthly suggestion*. That is
   the failure mode a mandatory date invites, and it was put to the owner
   before he made the date mandatory anyway (AC-1).
3. **YNAB returns a deleted category's money to the pool** the same month, as
   *Ready to Assign*. Monarch instead makes deletion destructive and tells you
   to archive. Quaestor takes YNAB's arithmetic (AC-15) and its own soft-delete
   for the lifecycle (AC-29).

## Decisions taken during discovery

Nine questions, each put with numbers, each answered by the owner.

**1. The month named is a saving month.** *Celular, $8.000.000, diciembre*,
created in August, asks **$1.600.000** — August through December, five months —
not $2.000.000 over four. The fund's opposite rule (AC-6 of 003: the money is
whole the last day of the month *before*) exists for **bills**, which land on
the first whether or not you are ready. A meta is a purchase the owner decides.

**2. A gap left by buying early is visible.** Bought in October with
$4.800.000 of $8.000.000 put by, the uncovered $3.200.000 comes out of
October's money available and October reads negative. This is not a new rule:
it is `uncovered_excess_calc` — *spent, less what it opened with, less what it
asks this month* — the same one every fund already runs.

Monarch's rule is *"the linked expense does not count against the budget,
because that money was set aside already"*. Correct, **but only for the part
that was actually set aside.** Monarch does not distinguish buying early.

**3. The date is mandatory.** The owner's own words: *"vámonos con que la fecha
es obligatoria"* — chosen after Firefly's fake-ten-year-target evidence was put
to him. There are no undated metas and no way to give a monthly instalment
instead of a date. The risk he accepted is that he will invent dates he does
not believe; *move the date* is already in the completion menu, so the exit
exists.

**4. Cancelling gives the money back, in the month it is cancelled.** Chosen
over asking where it should go and over doing nothing. The $4.800.000 never
moved anywhere — they sit in the account, merely spoken for — so releasing them
into that month's money available is the truthful reading, and matches YNAB.

Nothing carries money from one meta to another. To move it, cancel and let the
new meta ask for what it needs.

**5. The metas have their own screen**, a new `Metas` entry beside `Fondos y
presupuestos` under *Planeación*. Rejected: mixing them into the funds list —
the funds are permanent and about fifteen, the metas are temporary and about
two, and feature 010 has just spent an entire feature making two nouns
distinguishable.

**6. There is an `Aportar` button**, and what it puts in costs that month.
Monarch's asymmetry, adopted whole: contributions **do** count against the
month (that money is genuinely being set aside now), linked expenses **do not**
(it was set aside already). Charging it twice is the error at hand.

**7. A meta may be held in dollars.** The consequence was derived rather than
asked, because only one version works: the meta is **stored in its currency**
and what it asks is converted at the month's rate, exactly as recurring items
already are. USD 2.000 by June asks USD 333 a month; when the rate moves from
$4.000 to $4.400 that same instalment costs $1.466.667 instead of $1.333.334.
Storing the peso figure instead would land the owner in June with the thing
more expensive and the money short.

**8. The dashboard says when a date passed with nothing bought.** Otherwise a
completed meta sits full forever and the owner never remembers to close it.

**9. One expense belongs to one meta**, and a purchase that cost more than the
meta held completes it with the excess visible — the same rule as decision 2,
not a second one.

**A meta is editable while it runs** — name, amount and month — raised by the
owner mid-question: *"es raro que un celular cueste EXACTAMENTE 5M"*. What it
asks recomputes from what is left and the months remaining. Lowering the amount
below what is already saved completes the meta and frees the excess into that
month, by decision 4's rule.

**10. The link changes the plan, never the history.** Found because the owner
asked what a meta's relationship to a fund and a category actually is, and the
first thirty-two ACs answered that for the month's budget and never for the
reports.

He answered it himself, from product ADR-037's own split — *the money available
is a balance and smooths nothing; the rates smooth and answer whether his life
fits his income*. Generalised: one half of the app states what happened and may
never hide anything, the other half plans and may leave things out.

A **movement** is the first half. On 12 December $8.000.000 left the account
against *Tecnología*, and the category's report says so — the year spikes, and
it really did. A **fund's month** and a **meta's month** are the second half:
*"asks $1.600.000"* is not a fact, nobody moved $1.600.000.

So AC-7 is not the app hiding a purchase. The fund leaves the linked expense
out because **the meta already counted it**, and counting it in both would
count the same money twice — the exact defect ADR-002's context warned about
when there were two layers. Rejected outright: hiding it from the reports too,
which would make the sum of every category's report smaller than what was
actually spent. Rejected on cost: a separate line per category report, which
buys a comparison the movement list already gives when the month is opened.

## The overlap this feature creates, and where it is paid

Found at review, when the owner asked what a meta's relationship to a fund and
a category actually is.

**The fund already contains a meta.** Its fourth rule is `target-by-date`, and
product ADR-037 describes it in as many words: *"a goal is a fund with a target
and a date"* … *"`target-by-date` (an amount by a date — **the former goal**)"*.
It ships today, as `target_amount` + `target_month`.

| | fund `target-by-date` | meta |
|---|---|---|
| category | one, required | none |
| how many | one per category | unlimited |
| money whole | the month **before** | the month **of** the date |
| the purchase | deducted by category, automatically | linked by hand, and excluded |
| on completion | nothing | asks what comes next |
| extra contribution | no | yes |

The difference is real — `target-by-date` saves for **a charge that will
arrive**, a meta for **a purchase the owner makes** — and it is invisible. The
owner will open the app wanting to save for something and find two paths that
read the same, one of them inside a four-option dropdown. That is the failure
feature 010 existed to fix, arriving again.

It is squeezed from both sides: for a **recurring** charge the `from-recurring`
rule is strictly better because it renews itself, and for a purchase the meta
is better. One case is left — a dated charge that happens once, a tuition.

**The owner decided to withdraw it, and to do it as its own feature after this
one.** The ordering is forced: the funds using the rule today have nowhere to
go until metas exist. It also needs an ADR superseding ADR-037's four-rule
clause, and a destructive migration on real data — CHARTER §7 requires him in
person, `migrations/**` is capped at autonomy `low`, and ADR-0030 requires a
fresh `just backup` first. None of that belongs inside a feature whose own
scope says the fund's rules do not change.

**The count that shapes that migration is not yet taken.** How many funds run
`target-by-date` in the real database decides how much there is to convert; it
does not decide whether to withdraw the rule, which is already decided.

## What this feature must not do

**Nothing about the fund changes.** Not its four rules — including
`target-by-date`, whose withdrawal is the next feature and not this one — not
its fold, not the one-fund-per-category constraint (AC-25 of 003). A meta
belongs to no category and a category may carry any number of them, or none.

**A meta is never tied to an account.** Firefly III ties a piggy bank to an
asset account and refuses to hold more than that account contains — the exact
coupling product ADR-015 removed and ADR-037 confirmed gone. Not reopened.

**The assistant is out of scope, by the owner's decision.** Asked whether the
chat should be able to create metas, he answered *"quiero quitar el asistente
más adelante"*. AC-32 records the consequence rather than hiding it.

This is a deviation, stated here so it is not contradicted in silence:
**CHARTER §4 names the agent-native MCP layer as one of the product's two
differentiators** (product ADR-001), and ADR-0006/0009 require REST/MCP parity.
While the assistant exists it will see funds and not metas. Removing the
assistant is a decision larger than this feature — it touches the charter,
ADR-001 and the whole `mcp/` layer — and belongs in its own discuss.

## The ADR this feature owes

`feature.md` says *"an ADR is required before code"* without naming what it
answers to. Two things it must state rather than assume, both found while
priming:

**Product ADR-037's decision sentence is** *"One noun: the fund … There is no
separate goals feature and no separate envelope"*, and its rejected alternative
(A) was *"keep envelopes and add funds beside them"*. This feature adds a noun
beside the fund. The distinction that makes it not a reversal: (A) was two ways
to depress the same headline **for the same category**, and a meta belongs to
no category. That sentence has to be written.

**Migration `0012` dropped `transaction.goal_id` destructively** four days
before this discovery, with its own docstring warning that *"the way back is
the dump, not the downgrade"*. AC-6's link is that column returning. The
difference is positional and holds — the old column hung off month-end
**transfer proposals** generated by a ritual, with a forced savings account and
a contributions table; the new one hangs off a **posted expense**, named once
by the owner, no account and no ritual — but it must be said out loud or the
next reader sees a reversal.

**`relevant_adrs` needs correcting.** It cites 0005 and 0006, both recorded in
`docs/adr/README.md` as *superseded by 0043* — and 0006 is *Goals and budgets
write API with MCP parity*, precisely what a hurried implementation would copy
from.

## Coverage checklists

Step 3b ran. The feature is a UI surface for humans → `accessibility.md`, which
the plugin lists as *(when written)* and does not ship; and it introduces a new
record and therefore a migration → `data-migration.md`, same. Neither exists,
both are flagged in the handoff. No auth surface, no deploy surface, no public
web page (local-only, ADR-0026).

The two gaps are covered here from the project's own standing rules instead:
AC-30 from feature 010's AC-9 (every screen carries a *¿Cómo funciona esto?*
panel), and the migration from CHARTER §7 — the owner is required in person and
`migrations/**` is capped at autonomy `low` regardless of this feature's level.

---

## AC-1: A meta is a named amount with a month, and it belongs to nothing else

- **Priority:** high
- **Type:** happy-path

The owner creates a meta by giving it a name, an amount and a month. All three
are required — there is no meta without a month, and no way to give a monthly
instalment in place of one.

A meta belongs to no category. A category may carry any number of metas, or
none, and nothing about it changes when one is created.

## AC-2: The month named is a month that saves

- **Priority:** high
- **Type:** happy-path

*Celular, $8.000.000, diciembre*, created in August, asks **$1.600.000** each
month: August, September, October, November and December. The named month is
the month the thing is bought and the last month money is put by for it.

This is deliberately the opposite of the dated fund, which must be whole on the
last day of the month before its charge. A bill lands whether or not the owner
is ready; a purchase happens when he decides.

## AC-3: A meta fills itself, and no month requires an act of saving

- **Priority:** high
- **Type:** happy-path

What a meta asks each month is what is left to save over the months remaining,
rounded up so the last month never comes up short.

Not opening the app for a month still advances the meta. A month that passes is
a month it saved.

## AC-4: What the metas ask lowers the money available

- **Priority:** high
- **Type:** happy-path

The money-available figure already subtracts what every fund asks. It now also
subtracts what every meta asks, as its own line, so the headline number the
owner reads already accounts for what he is saving toward.

The breakdown adds up exactly: income, less what the funds ask, less what the
metas ask, less what nothing covers.

## AC-5: The metas have their own screen

- **Priority:** high
- **Type:** happy-path

`Metas` is a new entry under *Planeación*, beside `Fondos y presupuestos`. Each
meta shows its name, its amount, its month, what it has put by, what it asks
this month and how far along it is.

Metas never appear in the funds list. The funds are permanent and one per
category; the metas are temporary and end.

## AC-6: The purchase is linked on the movement, once

- **Priority:** high
- **Type:** happy-path

Recording an expense, the owner may point it at a meta. Leaving it unpointed is
the normal case and behaves exactly as it does today.

Only an expense can be pointed at a meta, and it can be pointed at exactly one.
A purchase split across two metas is recorded as two movements.

## AC-7: A linked expense leaves the category's fund untouched

- **Priority:** high
- **Type:** happy-path

An $8.000.000 phone linked to a meta does not read as a $7.900.000 overspend on
a $100.000 *Tecnología* budget. The category's fund does not count the linked
expense at all — neither as spending, nor against what it holds, nor in what it
carries into next month.

## AC-8: Linking the purchase completes the meta and asks what comes next

- **Priority:** high
- **Type:** happy-path

The meta counts the linked expense and closes. The app then offers three
things: close it, keep it with a new amount, or keep it with a new month.

## AC-9: Reaching the amount stops the asking

- **Priority:** high
- **Type:** happy-path

A meta that has put by everything it needs asks for nothing further, even with
months still to run. It does not overshoot and it does not keep taking from the
money available.

## AC-10: The owner may put in extra, and it costs that month

- **Priority:** high
- **Type:** happy-path

`Aportar` adds money to a meta on any month. What it adds comes out of that
month's money available, and what the meta asks for the remaining months drops
accordingly.

$2.000.000 put into a meta holding $3.200.000 takes it to $5.200.000, costs
that month $2.000.000, and drops the instalment from $1.600.000 to $933.334.

Contributions count against the month; linked expenses do not. The money a
purchase spends was already counted when it was saved.

## AC-11: A meta can be edited while it runs

- **Priority:** high
- **Type:** happy-path

Name, amount and month are all editable at any time, and what the meta asks
recomputes at once from what is left and the months remaining.

Raising a $8.000.000 meta to $9.000.000 in October with $4.800.000 put by moves
the instalment from $1.600.000 to $1.400.000 — $4.200.000 over the three months
that remain.

## AC-12: Buying before the money is whole leaves a visible gap

- **Priority:** high
- **Type:** edge-case

An $8.000.000 phone bought in October against a meta holding $4.800.000 leaves
$3.200.000 that was never put by. That $3.200.000 comes out of October's money
available, and October may read negative.

The gap is what the purchase cost, less what the meta opened the month with,
less what it asks this month — never the whole purchase. The same shape the
funds already use.

## AC-13: A purchase that cost more than the meta held completes it anyway

- **Priority:** high
- **Type:** edge-case

A $9.000.000 phone linked to a full $8.000.000 meta completes it — the thing
was bought — and the $1.000.000 the meta did not cover leaves the month's money
available, by AC-12's rule.

The meta's amount is not silently rewritten to the price paid.

## AC-14: A contribution larger than what is missing is trimmed to fit

- **Priority:** medium
- **Type:** edge-case

$5.000.000 offered to a meta missing $3.200.000 puts in $3.200.000, says so,
and leaves the rest in the month. A meta never holds more than the thing costs.

## AC-15: Cancelling gives back what was put by, in the month it is cancelled

- **Priority:** high
- **Type:** edge-case

A meta cancelled in October holding $4.800.000 releases all $4.800.000 into
October's money available, and stops asking. The owner is not asked where the
money should go and it is not moved to another meta.

## AC-16: Lowering the amount below what is saved completes the meta

- **Priority:** medium
- **Type:** edge-case

A $8.000.000 meta holding $4.800.000, edited down to $4.000.000, is complete —
and the $800.000 of excess is released into that month, by AC-15's rule.

## AC-17: Several metas run at once without interfering

- **Priority:** high
- **Type:** edge-case

Any number of metas may be open. Each asks for its own share, all of them
appear as one line in the money available, and a purchase linked to one has no
effect on any other.

## AC-18: A meta created for the month in course asks for the whole thing

- **Priority:** medium
- **Type:** edge-case

*Celular, $8.000.000, agosto* created in August has one month to fill, and asks
for $8.000.000 now. There is no month left to spread it over.

## AC-19: The month arrives with nothing bought, and the app says so

- **Priority:** medium
- **Type:** edge-case

A meta whose month has passed with no purchase linked is named on the dashboard
— it is full, it is asking for nothing, and it is waiting on the owner to link
the purchase, close it or move the date.

## AC-20: A meta with no month, or a month already past, is refused

- **Priority:** high
- **Type:** error

Creating or editing a meta without a month is refused. So is a month earlier
than the month in course — there is no way to save into the past.

## AC-21: An amount of zero or less is refused

- **Priority:** high
- **Type:** error

A meta's amount must be greater than zero, on creation and on edit. So must a
contribution.

## AC-22: A name already in use is refused

- **Priority:** medium
- **Type:** error

Two metas may not carry the same name, the same way two categories may not
(AC-13 of feature 008). An archived meta's name is free to reuse.

## AC-23: Only an expense can be linked, and only to one meta

- **Priority:** high
- **Type:** error

Pointing an income at a meta is refused. So is pointing one expense at two.

## AC-24: A meta in dollars with no rate for the month says so

- **Priority:** medium
- **Type:** error

A meta held in a currency other than the peso needs the month's rate to state
what it asks. With no rate set, it says that plainly rather than showing a
wrong figure or a zero — the behaviour the app already has for every other
converted amount (ADR-0028).

## AC-25: A meta that no longer exists cannot be linked or contributed to

- **Priority:** medium
- **Type:** error

An archived meta accepts neither a contribution nor a new link. Movements
already linked to it keep their link and keep being excluded from their
category's fund.

## AC-26: A meta may be held in dollars

- **Priority:** medium
- **Type:** cross-cutting

The amount is stored in the currency it was given in, and what the meta asks is
converted at the rate of the month being read — never at a stored rate, and
never at the rate of the month it was created.

USD 2.000 by June asks USD 333 a month. At $4.000 that costs $1.333.334; when
the rate moves to $4.400 the same instalment costs $1.466.667, and the owner
still reaches June with the full USD 2.000.

## AC-27: Every figure is derived from the month being read

- **Priority:** high
- **Type:** cross-cutting

What a meta has put by, what it asks and how far along it is are all worked out
from the month asked about and what is known now. Nothing is stored as a
snapshot and no clock is needed — asking about March next year gives the same
answer whenever it is asked.

## AC-28: The link can be removed or moved

- **Priority:** medium
- **Type:** cross-cutting

Editing a movement, the owner can point it at a different meta or at none. The
meta it left recomputes, the meta it joined recomputes, and the category's fund
takes it back the moment it is unlinked.

## AC-29: A meta is archived and restored, never destroyed

- **Priority:** medium
- **Type:** cross-cutting

Cancelling archives. An archived meta is out of the list, out of the money
available and out of the create form's choices, and it can be restored. This is
the project's uniform lifecycle for masters (ADR-0005).

## AC-30: The metas screen says what a meta is

- **Priority:** medium
- **Type:** cross-cutting

The screen carries a *¿Cómo funciona esto?* panel in the same place every other
screen carries one (AC-9 of feature 010), and its empty state says what a meta
is and offers the button that creates the first one.

It has to say the thing the vocabulary work of 010 left it: a **meta** is a
named thing with an end, belonging to no category; a **fondo** carries a
category's leftover money forward; a **presupuesto** is a ceiling that resets.

## AC-31: The money available breaks down into terms that add up

- **Priority:** high
- **Type:** cross-cutting

The metas appear as their own line — not folded into what the funds ask, and
not hidden. An owner reading the breakdown can tell which of the two nouns took
his money.

## AC-32: The assistant knows nothing about metas

- **Priority:** medium
- **Type:** cross-cutting

There is no assistant surface for metas: none can be created, listed, changed
or contributed to through the chat, and no fund answer mentions them.

This is the owner's decision — *"quiero quitar el asistente más adelante"* —
recorded rather than fixed. It stands against CHARTER §4, which names the
agent-native MCP layer as a product differentiator (product ADR-001), and
against the REST/MCP parity ADR-0006/0009 require. While the assistant exists
it will see funds and not metas. Removing it belongs in its own discuss.

## AC-33: The link changes what the month plans, never what the reports say

- **Priority:** high
- **Type:** cross-cutting

A linked expense keeps its category and is counted in full by every report of
what was spent. December in *Tecnología* reads $8.200.000 — the $8.000.000
phone and the $200.000 charger — and the year spikes, because it did.

What the link changes is only the planning side: the category's fund leaves the
purchase out of its month (AC-7) because the meta already counted it, and
counting it in both would count the same money twice.

Nothing is netted, marked or split in the reports. An owner adding up every
category's report gets exactly what left his accounts.

## AC-34: A meta can be told what it already holds

- **Priority:** high
- **Type:** happy-path

Creating a meta, the owner may state what he has already put by for it. A
$8.000.000 meta for December created in August with $3.000.000 already saved
asks **$1.000.000** a month — $5.000.000 over five months — not $1.600.000.

What is stated this way costs no month. It is money saved before the meta
existed, and charging August for it would make August's figure wrong.

This is what `Aportar` (AC-10) cannot do and must not be used for: a
contribution is money set aside **now** and costs the month it is made.

The statement is made for a month and never re-read afterwards, the same way a
fund's is (product ADR-041).

## AC-35: Deleting the linked movement reopens the meta

- **Priority:** medium
- **Type:** edge-case

A meta completed by a purchase goes back to running when that movement is
deleted: it counts the expense no longer, resumes asking for what is missing
over the months that remain, and the category's fund takes back nothing — the
movement is gone from both.

The same holds when the movement is archived rather than deleted.

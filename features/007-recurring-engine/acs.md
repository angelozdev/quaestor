---
ac_count: 28
high_priority_count: 18
discovered: 2026-08-02
---

# Acceptance criteria — 007 recurring-engine

Discovered 2026-08-02 (Checkpoint 2), **clean-room mode** — the method the user
fixed at intake and `feature.md` records: the criteria below were designed from
product behaviour first, and only then contrasted against the shipped engine.
Every divergence is resolved explicitly as fix-or-accept; none is left implicit.

Procedural caveat, stated rather than hidden: the session that drafted these
criteria had already read `services/recurring.py` at Checkpoint 1.5. The
separation is therefore procedural — the criteria were written from product
reasoning and the implementation was reopened only for the diff — not a
memory-clean room.

## Decisions taken during discovery

Nine product decisions. Eight diverge from shipped behaviour.

1. **Past dates are offered, never imposed** (AC-12, target). Declaring an
   obligation with a start date already passed presents the dates that fell due
   for the user to tick one by one; nothing is created before the answer. The
   shipped engine backfills all of them silently on the next daily run.
2. **Repeating incomes are always automatic** (AC-6, target). Manual mode for an
   income produces expected money that no screen can confirm — feature 006
   decided incomes leave the to-pay queue. Forcing automatic closes the hole
   without a new surface.
3. **An obligation that reaches its end date turns itself off** (AC-13, target).
   The shipped item stays in the active list forever once its end date passes.
4. **Resuming a paused obligation does not recover the pause** (AC-17, target).
   The shipped engine charges the whole paused stretch on the first run after
   the resume — pausing only defers.
5. **A date already charged cannot be skipped** (AC-20, target). The shipped
   skip marks the date skipped and leaves the money moved, so the record and the
   balance contradict each other.
6. **One broken obligation does not stop the others** (AC-24, target). The
   shipped daily run rolls the whole batch back, so one unchargeable obligation
   costs the day for every other one.
7. **Every charge is recognisable as recurring** (AC-25, target). The link is
   stored but no screen shows it, and the movement records itself as entered by
   hand.
8. **Deleting a charge the engine made closes that date** (AC-28, target). The
   money comes back and the date is marked skipped, so no later run charges it
   again. This is the escape hatch AC-20 sends the user to, and today it leaves
   the date pointing at a movement that no longer exists.
9. **A closed month freezes nothing** — verified, not assumed. `close_month`
   only runs the savings-goal proposal hook; every figure the user sees is
   recomputed at read time. Backfilled charges therefore carry their own real
   date and past months recompute to include them, which is the truth. No
   closed-month restriction enters these criteria. The one artefact that does go
   stale is a savings-goal proposal already made for an affected month; that
   belongs to `goal-contribution-hooks`, not here.

Decision 1 was taken against industry precedent rather than from first
principles. Firefly III refuses a past first date outright and creates nothing;
Actual Budget keeps schedules forward-only and warns that pulling in older
movements throws the budget out; YNAB treats scheduling as a future-only tool
and puts history in via import. GnuCash is the outlier that does backfill — and
does it through its *Since Last Run* assistant, which lists every missed date
and lets the user mark each Create / Postpone / Ignore. AC-12 is that pattern:
the power to catch up, without anything appearing unseen.

## Divergence ledger

| AC | Shipped behaviour | Decision |
|---|---|---|
| AC-6 | Manual mode accepted for incomes; produces an unconfirmable planned income | **fix** — incomes are always automatic |
| AC-12 | Silent full backfill on the next daily run | **fix** — offer the dates, create only what is ticked |
| AC-13 | Item stays active after its end date | **fix** — turns itself off |
| AC-17 | Resume charges the entire paused stretch | **fix** — resumes from today |
| AC-20 | Skipping a charged date desyncs record and balance | **fix** — refused |
| AC-21 | Any date can be skipped, due or not | **fix** — only real due dates |
| AC-22 | An account archived later keeps being charged | **fix** — stops and is reported |
| AC-24 | One failure rolls back the whole day | **fix** — the rest still land |
| AC-25 | Charge is stored as recurring but shown as hand-entered | **fix** — visibly recurring |
| AC-28 | Deleting an engine-made charge leaves the date pointing at a movement that no longer exists | **fix** — the date closes as skipped |
| AC-27 | Undoing a skip already returns the date to pending | **accept** — asserted, not changed |
| everything else | matches | **accept** |

Eight of the ten fixes were decided by the user during discovery. AC-21 and
AC-22 came out of the diff rather than out of a question, and were ratified
separately on 2026-08-02.

AC-27 and AC-28 were added by the same-day edit pass that closed W6 and W7 from
`consistency-check`. AC-27 asserts a seam that already works and was simply
never written down; AC-28 answers the question AC-20 had been leaning on
without stating.

Out of scope, surfaced during discovery and parked: a **Por cobrar** view for
expected incoming money. The user wants it, it does not fit this feature (new
surface, and feature 006 already ruled one-off planned incomes out), and AC-6
removes the urgency by closing the orphan case. Open it with `discuss`.

The to-pay queue's own behaviour — how a manual charge is confirmed or skipped
from there — is pinned by feature 006 and referenced, not re-decided.

## AC-1: Declare a repeating obligation once

- **Priority:** high
- **Type:** happy-path

Declaring takes a name, a payee, whether it is money going out or coming in, a
positive amount in the account's own currency, an account, a cadence, a start
date, and optionally a category and an end date. Money that moves between the
user's own accounts cannot repeat this way. Once declared, the user never has to
enter that movement again.

## AC-2: The engine runs itself

- **Priority:** high
- **Type:** happy-path

Charges appear because the day arrived, not because the user asked for them.
The engine runs once a day on its own, with no button anywhere to press and no
screen that must be open. A user who does not visit the app for a week still
finds the week's charges when they return.

## AC-3: An automatic obligation pays itself

- **Priority:** high
- **Type:** happy-path

On its due date an automatic obligation is recorded as already paid and the
account balance moves by its amount. Netflix at 25.900 due on the 5th leaves the
balance 25.900 lower on the 5th, with no confirmation asked and nothing pending.

## AC-4: A manual obligation asks first

- **Priority:** high
- **Type:** happy-path

On its due date a manual obligation appears as owed, and no balance moves until
the user resolves it. The rent of 1.800.000 due on the 1st shows up as pending
that day; the balance changes only when the user confirms it, at whatever the
real amount turned out to be. What happens from there — confirming with a
different amount or date, skipping, undoing a skip — is pinned by feature 006.

## AC-5: The cadence is every N periods from the start date

- **Priority:** high
- **Type:** happy-path

An obligation falls due every N days, weeks, months or years counted from its
start date, and stops after its end date, which itself counts as a valid due
date. Every two weeks from 5 January gives 19 January, 2 February, and so on;
every month gives the 5th of each month. An obligation with no end date repeats
indefinitely.

## AC-6: Money coming in repeats automatically

- **Priority:** high
- **Type:** happy-path

A repeating income is always automatic: on its due date it is recorded and the
balance rises. A salary of 4.500.000 on the 30th adds 4.500.000 on the 30th; if
the real deposit was 4.480.000 the user corrects that movement. Declaring an
income that waits for confirmation is refused, because expected money never
enters the to-pay queue (feature 006) and would otherwise sit pending where
nobody can see or resolve it.

## AC-7: The repeating obligations are visible as a list

- **Priority:** medium
- **Type:** happy-path

The user can see everything they have declared, what each one costs, how often
it falls due and when it falls next, and can look at the switched-off ones
separately from the live ones without losing them.

## AC-8: A monthly obligation survives short months

- **Priority:** high
- **Type:** edge-case

An obligation due on the 31st falls due on the last day of any month that has no
31st, and returns to the 31st the following month. Starting 31 January it falls
on 28 February (29 in a leap year), then 31 March. The same holds for a yearly
obligation declared on 29 February.

## AC-9: A machine that was off catches up

- **Priority:** high
- **Type:** edge-case

After days without running, the next run creates every charge that fell due in
the meantime, each on its own date, in order. Three days off with a daily
obligation of 8.000 produces three charges of 8.000 dated to their own days, not
one of 24.000 dated today. No date is skipped and none is merged, and the user
is not asked — these obligations were already approved when they were declared.

## AC-10: Running twice in a day changes nothing

- **Priority:** high
- **Type:** edge-case

A second run on the same day creates nothing, moves no balance and duplicates
nothing. The balance after two runs equals the balance after one.

## AC-11: An obligation that has not started waits

- **Priority:** medium
- **Type:** edge-case

An obligation whose start date is still ahead produces nothing until that day
arrives, however many times the engine runs in between.

## AC-12: Dates already passed are offered, never imposed

- **Priority:** high
- **Type:** edge-case

When an obligation is declared with a start date already behind — or an existing
one's start date is moved back — the dates that already fell due are presented
for the user to accept or decline one by one, and nothing is created until they
answer. Netflix at 25.900 declared on 2 August starting 5 January offers seven
dates; ticking three creates three charges of 25.900 dated 5 May, 5 June and 5
July, so those months' spending and the envelope carry-over that follows from
them recompute accordingly. The declined dates are never created, are never
offered again, and are not recreated by any later run. Declining every date is
allowed and leaves the obligation live from its next future date.

Target — the shipped engine creates all seven on the next daily run without
asking, which in automatic mode takes 181.300 out of the balance unannounced.

## AC-13: An obligation that has ended switches itself off

- **Priority:** medium
- **Type:** edge-case

Once the last due date on or before the end date has passed, the obligation
stops being live: it leaves the list of active obligations and joins the
switched-off ones, so that list only ever holds what is still going to be
charged. Extending the end date brings it back. Target — the shipped item stays
listed as active forever, producing nothing.

## AC-14: Editing changes only what has not happened yet

- **Priority:** high
- **Type:** edge-case

Changing the amount, payee, category, account or cadence applies from the next
due date onward; charges already made keep the amount and date they were made
with. Raising Netflix from 25.900 to 31.900 in August leaves January through
July at 25.900 and charges 31.900 from September. Editing never rewrites,
deletes or re-dates a charge that already exists.

## AC-15: Skipping one date leaves the rest alone

- **Priority:** high
- **Type:** edge-case

A single date can be dropped without touching the obligation or any other date.
Skipping the 5 September Netflix charge means no money moves for that date, it
disappears from what is owed if it was pending, and 5 October arrives normally.
No later run recreates a skipped date; the only thing that brings it back is the
user undoing the skip (AC-27).

## AC-16: Pausing keeps what already happened

- **Priority:** medium
- **Type:** edge-case

Switching an obligation off stops future charges and leaves every charge already
made exactly as it was — the balance, the records and the reports do not move.
Switching something off that is already off changes nothing.

## AC-17: Resuming picks up from today

- **Priority:** medium
- **Type:** edge-case

An obligation paused in March and resumed in August charges next in September.
The four dates that fell inside the pause are not charged and are not offered:
that is what pausing meant. Target — the shipped engine charges all four on the
first run after the resume, 480.000 at once for a 120.000 gym, which turns
pausing into deferring.

## AC-18: An impossible obligation is refused

- **Priority:** high
- **Type:** error

Declaring is refused, with nothing recorded and a message naming the problem,
when the amount is zero or negative, the currency is not supported or does not
match the account's own, the movement is a transfer between the user's accounts,
the cadence is less than one period, the end date falls before the start date,
or the account or category does not exist or has been archived. The same rules
hold when editing.

## AC-19: What an obligation is cannot be changed

- **Priority:** medium
- **Type:** error

Whether an obligation is money going out or coming in, and the currency it is
in, are fixed when it is declared. Changing either means switching that
obligation off and declaring a new one — otherwise charges already made would
stop meaning what they said.

## AC-20: A date already charged cannot be skipped

- **Priority:** high
- **Type:** error

Skipping a date whose money already moved is refused with a message saying it
was already charged and pointing at the movement itself. Nothing changes: the
balance stays as it is and the date stays charged. A charge made by mistake is
undone by deleting that movement, which returns the money. Skipping exists for
what has not happened yet. Target — the shipped skip marks the date skipped and
leaves the 25.900 out of the balance, so the obligation says it was not paid
while the account says it was.

## AC-21: Only real due dates can be skipped

- **Priority:** medium
- **Type:** error

Asking to skip a date on which the obligation never falls due is refused rather
than silently recorded. A monthly obligation due on the 5th cannot have its 3rd
skipped. Target — the shipped skip accepts any date and leaves a record of a
skip that corresponds to nothing.

## AC-22: An account retired later stops the charges

- **Priority:** medium
- **Type:** error

An obligation pointing at an account the user archived after declaring it stops
charging and is reported as needing attention, instead of moving the balance of
an account the user has retired. It resumes once pointed at a live account.
Target — the shipped engine keeps charging the archived account.

## AC-23: The same date is never charged twice

- **Priority:** high
- **Type:** cross-cutting

For any obligation and any date there is at most one charge, whatever happens:
repeated runs, a catch-up overlapping a normal run, an edit between runs, a
resume after a pause. The user can never be charged twice for one due date.

## AC-24: One broken obligation does not cost the day

- **Priority:** high
- **Type:** cross-cutting

When one obligation cannot be charged, the others still are, and the failure is
reported naming which one and why. Seven of eight obligations land; the eighth
is reported and retried the next day. Each charge lands whole — its record and
its balance movement together, or neither. Target — the shipped run rolls the
entire batch back on any failure, so a single unchargeable obligation silently
costs every other one its day, every day, until someone notices.

## AC-25: Every charge says where it came from

- **Priority:** high
- **Type:** cross-cutting

A movement created by the engine is recognisable as such in the list of
movements, without opening anything, and identifies which obligation produced
it. This is how the user reconciles a balance that moved while they were not
looking. Target — today the origin is stored but no screen shows it, and the
movement records itself as having been entered by hand.

## AC-26: Everything works by conversation too

- **Priority:** medium
- **Type:** cross-cutting

Declaring an obligation, listing them, editing one, skipping a date, switching
one off and switching it back on are all reachable by asking, not only through
the screens, and report the same figures the screens do — including the choice
of past dates in AC-12, which must be answerable in conversation rather than
silently defaulting either way. Which of those the assistant may do on its own
is governed by the tool-permission feature, not re-decided here.

## AC-27: Undoing a skip returns the date to pending

- **Priority:** medium
- **Type:** edge-case

When the user undoes a skip on a payment that came from a repeating obligation,
that obligation's own record of the date returns to pending along with the
payment, so the two stay in step: the date is neither treated as still skipped
nor charged a second time by a later run. Undoing a skip on the 5 September
Netflix charge puts that one date back in what is owed, at its original amount
and date, and 5 October is unaffected. The undo itself belongs to feature 006;
what is asserted here is that the obligation follows it.

## AC-28: Deleting a charge the engine made closes that date

- **Priority:** high
- **Type:** edge-case

Deleting a movement the engine created returns the money and closes that due
date: it counts as skipped from then on, and no later run charges it again.
Deleting the automatic Netflix charge of 25.900 from 5 August puts 25.900 back
in the account and leaves 5 August settled for good; 5 September arrives
normally. This is the correction AC-20 points the user to, so it has to leave
the obligation and the account agreeing with each other.

Target — today deleting the movement returns the money but leaves the date
recorded as charged, pointing at a movement that no longer exists. The date is
then consumed forever: no run brings it back and no screen shows that anything
is wrong.

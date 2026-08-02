---
ac_count: 24
high_priority_count: 14
discovered: 2026-08-01
---

# Acceptance criteria — 006 planned-payments-to-pay

Discovered 2026-08-01 (Checkpoint 2), reverse-engineer mode. Source material:
shipped code, 30 existing tests across service, wire, value-object and
component layers, the P3 temporal-engine design, ADR-0023, ADR-0031, ADR-0032,
and a product review with Angelo.

Five decisions taken during discovery:

- **Incomes leave the queue** (AC-15, new behaviour — defect found during
  discovery). A manually-recurring income materializes a planned income that
  today lands in "Por pagar" and *adds* to the amount owed: a planned salary of
  5.000.000 next to a 85.000 phone bill renders "Por pagar 5.085.000".
- **Skipping becomes reversible** (AC-8, new behaviour — a state transition
  that does not exist today; ADR due at plan time).
- **A missing exchange rate keeps failing loudly** (AC-20). Feature 005's AC-9
  is upheld, not superseded: the app never assumes a rate.
- **Resolving something twice is rejected, not absorbed** (AC-18). The balance
  can never move twice either way; the rejection is what the user sees.
- **Planning a one-off income stays out of scope.** Expected money is recorded
  when it arrives; recurring incomes already exist. Forecasting inflows is a
  separate conversation.

Read-time COP conversion is pinned by feature 005's acceptance suite — AC-4 and
AC-23 reference that coverage rather than duplicating it. Transfer-pair
mechanics and stored leg direction are pinned by feature 002 — AC-6 references
that coverage.

## AC-1: Plan a one-off payment

- **Priority:** high
- **Type:** happy-path

Planning a payment takes a payee, a positive amount in the account's own
currency, a due date, an account, and optionally a category and notes. The
payment is recorded as owed, not paid: no account balance moves, and it appears
in the outstanding queue from that moment. Planning works with no exchange rate
set.

## AC-2: The queue separates overdue from upcoming

- **Priority:** high
- **Type:** happy-path

Asking what is outstanding for a period returns two groups: what is already
past its due date, and what is still due within the period. An item belongs to
exactly one group — never both, never neither. Each group is ordered by due
date, earliest first.

## AC-3: Overdue stays visible until it is resolved

- **Priority:** high
- **Type:** happy-path

An item past its due date keeps appearing in the overdue group no matter how
far in the past it fell due and no matter where the period starts. Looking at
"this week" still surfaces a bill that fell due last month. It leaves the view
only by being confirmed or skipped (ADR-0023 — the rule the user stated as
"lo vencido debe aparecer SIEMPRE hasta que se resuelva").

## AC-4: One single total in pesos

- **Priority:** high
- **Type:** happy-path

The queue reports one amount owed in pesos, covering both groups together,
converted at the exchange rate in force at the moment of reading. Items already
in pesos count at face value. The conversion mechanics are pinned by feature
005.

## AC-5: Confirming a payment moves the balance

- **Priority:** high
- **Type:** happy-path

Confirming turns an owed payment into a real movement: the account balance
drops by the confirmed amount and the payment leaves the queue. The real amount
and the real date can differ from what was planned — a bill planned at 80.000
that arrives at 95.000 is confirmed at 95.000, and that is the figure that hits
the balance and the records.

## AC-6: Confirming a planned transfer creates both sides

- **Priority:** high
- **Type:** happy-path

Confirming an owed transfer produces a complete transfer: money leaves the
default source account and arrives in the destination account, both sides
recorded together or neither. The resulting pair behaves like any other
transfer — including deleting as a pair, whose mechanics are pinned by feature
002.

## AC-7: Skipping removes a payment without touching money

- **Priority:** high
- **Type:** happy-path

Skipping cancels an owed payment: it leaves the queue, no balance moves, and
nothing is recorded as spent. A skipped payment that came from a recurring
obligation marks that single occurrence as skipped without affecting the
obligation itself or any other occurrence.

## AC-8: A skip can be undone

- **Priority:** high
- **Type:** happy-path

A payment skipped by mistake can be returned to the queue with its original
payee, amount, due date and account intact, and can then be confirmed or
skipped again like any other. Undoing a skip moves no money on its own. New
behaviour, decided 2026-08-01 — nothing in the shipped product allows it today.

## AC-9: One queue for every kind of obligation

- **Priority:** high
- **Type:** happy-path

Everything the user owes converges in the same queue and is resolved the same
way: one-off planned payments, the manual recurring obligations that fall due,
and the savings-goal contributions proposed at month close. None of the three
gets a special path or a separate screen.

## AC-10: Resolving a recurring obligation keeps it in step

- **Priority:** medium
- **Type:** happy-path

Confirming or skipping something that came from a recurring obligation updates
that obligation's own record of the occurrence, so a later run of the recurring
machinery neither recreates it nor double-counts it. The recurring machinery
itself is covered by its own feature; here only the hand-off is asserted.

## AC-11: What falls due today counts as upcoming

- **Priority:** medium
- **Type:** edge-case

An item due today is upcoming, not overdue. The boundary is the day itself: a
payment due yesterday is overdue from the moment the day turns.

## AC-12: The period caps both groups

- **Priority:** medium
- **Type:** edge-case

Nothing due after the end of the period appears, in either group. Asking about
the next two days never surfaces a bill due next week, whether or not other
items are overdue.

## AC-13: The retrospective view carries no overdue

- **Priority:** medium
- **Type:** edge-case

When the queue is read as a retrospective of a closed period, only what fell
due inside that period is counted; obligations dragged in from earlier periods
are excluded, so a past month's account of what was pending stays true to that
month.

## AC-14: An empty queue says so

- **Priority:** medium
- **Type:** edge-case

With nothing outstanding, every surface states it plainly rather than showing a
blank area or a bare zero. A group with no items is omitted entirely instead of
rendering an empty heading.

## AC-15: The queue shows only what is owed

- **Priority:** high
- **Type:** edge-case

Expected incoming money never appears in the outstanding queue and never
inflates the amount owed. A planned salary of 5.000.000 alongside a 85.000
phone bill leaves the queue showing one item and 85.000 owed. Defect found
during discovery 2026-08-01; the shipped product shows 5.085.000.

## AC-16: An impossible period is rejected

- **Priority:** medium
- **Type:** error

Asking for a period that ends before it starts is refused with a clear message
rather than answered with an empty or arbitrary result.

## AC-17: Planning rejects impossible data

- **Priority:** high
- **Type:** error

A payment cannot be planned with a zero or negative amount, in an unsupported
currency, against an account that does not exist or has been archived, against
an archived category, or in a currency that differs from the account's own. Each
refusal names what is wrong, and nothing is recorded.

## AC-18: What is no longer pending cannot be resolved again

- **Priority:** high
- **Type:** error

Confirming or skipping something already confirmed, already skipped, or never
owed in the first place is refused with a message saying it is no longer
pending. The balance never moves a second time. This is what the user sees when
a stale screen or the agent tries to resolve something already handled.

## AC-19: A transfer that cannot complete is refused whole

- **Priority:** medium
- **Type:** error

Confirming an owed transfer is refused when no default source account is
configured, when source and destination are the same account, when the amount
adjusts to zero or below, or when the currencies of the two accounts do not
match the transfer. No balance moves on any side and the transfer stays owed.

## AC-20: Without an exchange rate there is no queue

- **Priority:** medium
- **Type:** error

If no exchange rate has ever been set, reading the outstanding queue fails with
a clear message telling the user to set it — even when everything owed is
already in pesos. Upholds feature 005's AC-9: the app never assumes a rate.
Planning and skipping keep working without a rate.

## AC-21: Confirming is all or nothing

- **Priority:** high
- **Type:** cross-cutting

A confirmation either lands completely — balance moved, payment marked paid,
recurring occurrence in step, savings contribution recorded — or leaves
everything exactly as it was. A failure anywhere in that chain, including in
the savings-contribution step, rolls back the balance and leaves the payment
still owed.

## AC-22: Resolved items never come back

- **Priority:** high
- **Type:** cross-cutting

Once confirmed, a payment is absent from both groups of the queue forever. Once
skipped, it is absent until explicitly restored (AC-8). No later reading of any
period brings back something already resolved.

## AC-23: Amounts follow today's rate

- **Priority:** medium
- **Type:** cross-cutting

Foreign-currency obligations are shown and totalled at the exchange rate in
force when the queue is read, not at any rate stored when the payment was
planned. Changing the rate changes what the same unresolved queue reports,
with no edit to the payments themselves. Mechanics pinned by feature 005.

## AC-24: Every queue action exists outside the app

- **Priority:** medium
- **Type:** cross-cutting

Asking what is outstanding, planning a payment, confirming and skipping are all
reachable conversationally, not only through the screens, and report the same
figures as the screens do — including the single amount owed across both
groups, which the conversational answer states outright instead of leaving the
user to add up section subtotals. Which of those actions the assistant may
perform on its own versus which need the user's own hand is governed by the
tool-permission feature, not re-decided here.

The missing combined total is a defect found at spec time (2026-08-01): the
screen shows 130.000 for an 85.000 overdue bill plus a 45.000 upcoming one,
while the conversational answer reports 85.000 and 45.000 separately and never
130.000.

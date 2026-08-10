# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One user: the owner, who is also the only operator, the only developer and the
only person who will ever see the data. He works from his Mac, in a browser
window, with the local Docker stack running. There is no second audience —
no household member, no accountant, no guest view.

Confirmed 2026-08-10: **the phone is not part of the scene.** He has never
opened Quaestor from a mobile browser and does not intend to; native mobile apps
are out of scope by charter. The real viewport is a desktop window.

His job: know where the money went and what he still owes, without performing a
monthly ritual to keep the numbers true.

## Product Purpose

A personal-finance system he owns end to end — his own database, his own
backend, and an agent that talks to *his* schema instead of a third party's API.
Ownership plus agent-native is the driver; the three original pains (what do I
still have to pay, saving toward named things, the monthly report) are the proof
of value, not the justification (product ADR-001).

Success is two things at once: the app tells the truth about the month, and
keeping it true costs zero clicks per month.

## Positioning

Two claims a neighbouring product could not truthfully copy:

- **The rule is the number, so there is no monthly ritual.** YNAB and Actual
  Budget both require a monthly button that distributes money into categories.
  Quaestor copied that shape once and measured the result: in seven months of
  real use, zero envelopes were ever created. A fund now carries a rule that
  computes its own monthly ask, forever, unattended (ADR-037).
- **An agent as a co-equal write path over an owned schema.** The assistant is
  not a chatbot bolted onto a UI; it and the screens are two surfaces over the
  same services, with REST/MCP parity as a tested requirement.

A third departure, chosen knowingly: **nothing is frozen.** Asking for August's
available money after switching off an income in October gives August's figure
*without* that income. In YNAB and Actual an assignment is a stored fact. The
accepted cost is that a screenshot of a past month will not always match the app
later.

## Operating Context

- **Local-only, on one Mac.** Docker Compose: `api` (FastAPI + uvicorn),
  `frontend` (Next.js), `db` (Postgres 18 in a named volume). Production data
  lives in that local container; nothing leaves the host (ADR-0026, ADR-0030).
  Backups are a dated `pg_dump` to iCloud Drive via `just backup`, and that
  discipline is load-bearing — between dumps the Mac holds the only live copy.
- **The assistant writes, the screens read.** Confirmed 2026-08-10: a $45.000
  lunch is recorded by telling the assistant, not by opening a form. The twelve
  screens exist and support the day-to-day CRUD, but the habit they actually
  serve is reviewing — the month, the funds, the accounts, what is still owed.
  Reading surfaces therefore carry more weight than entry forms.
- **Two currencies, one rate.** Money is held in COP and USD. Every COP figure
  is computed at read time from a single USD→COP rate (the TRM), which must
  always be set: a read path with no rate refuses rather than guesses. Setting
  it is manual today; a daily fetch job is on the roadmap and will retire the
  friction (ADR-038).
- **A daily unattended run.** A scheduler materialises due obligations, fetches
  what it can and ensures the month is closed. It is the only surface that moves
  a balance with no user action, which is why its charges are recognisable as
  its own and why dates it was never authorised for are offered rather than
  imposed.
- **A monthly reading ritual, not a monthly bookkeeping ritual.** The report is
  the screen he opens once a month, and its figures are the ones he acts on.
- **Engineering method as operating context:** DAE with ATDD — features in
  `features/NNN-slug/`, acceptance specs before implementation, decisions
  recorded as ADRs (`docs/adr/` technical, `docs/decisions/product-decisions.md`
  product). This is why the product's own vocabulary is unusually settled.

## Capabilities and Constraints

**Three nouns, and the vocabulary is load-bearing** (ADR-042, ADR-043):

| Noun | What it does |
|---|---|
| **presupuesto** | a monthly ceiling; what is not spent is not kept |
| **fondo** | carries its leftover into the next month; lives on one expense category |
| **meta** | a named thing with an end, belonging to no category; a purchase closes it |

The words matter because the failure they fix was measured: on 2026-08-05 the
owner commissioned three features that were already built, tested and in
production, because nothing in the app named them.

**The month shows two numbers, never merged** (ADR-037):

```
money available = income this month − Σ what every fund asks − what no fund covers
```

Not smoothed, and income counts only in the month it is due. The earning/cost
rate is the other number, and *is* smoothed, because it answers a different
question — does my life fit my income.

Other confirmed rules future work must not contradict:

- **Every peso in or out carries a category**, and a category belongs to one
  direction. Transfers carry none by rule — moving money between his own
  accounts is not spending (ADR-036).
- **What really happened if it happened; what was expected if not.** A posted
  bill counts at what left the account; a turn still ahead counts at what it
  declared (ADR-039, ADR-004).
- **Credit cards on an accrual basis:** the expense counts on the purchase date;
  the statement payment is a transfer, never an expense (ADR-021).
- **The outstanding queue holds debt only** — expected incoming money never
  inflates what is owed (ADR-027). Skipping is reversible (ADR-028); resolving
  something twice is refused with the reason, never silently absorbed (ADR-029).
- **A charged date is corrected by deleting the movement,** which returns the
  money and closes the date; skipping something already charged is refused
  (ADR-034).
- **Repeating income is always automatic** (ADR-031). Dates already past when an
  obligation was declared, and dates inside a pause, are offered one by one and
  never charged unannounced (ADR-026, ADR-033).
- **Out of scope by charter:** multi-tenant, public deployment, TLS termination,
  native mobile apps.

**Explicitly undecided, parked, or decided-but-unbuilt** — not oversights:

- whether transfers should carry a category at all (parked as its own discussion);
- a **"Por cobrar"** view for money expected but not yet received; until it
  exists, a repeating income whose money never arrived is reachable only through
  the assistant (ADR-027, ADR-031);
- `close_month` currently does nothing — an empty hook list, parked pending a
  product decision;
- a fund's **opening balance** is decided (it carries the month it was stated
  for) but not built, and the form has no field for it (ADR-041);
- **the assistant does not know the words *presupuesto* and *meta*,** and cannot
  manage metas. A stated deviation, filed, not fixed.

## Brand Commitments

- **Name:** Quaestor.
- **Language split:** all code and identifiers in English (ADR-0001); **all UI
  copy in Spanish**. Refusal messages currently surface in English — known gap,
  tracked as `id:error-contract`.
- **Voice:** plain Spanish, no technical jargon on screen. *"Job"* was flagged
  as a defect in the UX audit for exactly this reason. Names describe the work,
  not the arithmetic: *"Promedio de los últimos meses"* says what a calculation
  does, not what it is for.
- **Screens must explain the mechanism, not only show the result.** This is the
  audit's transversal diagnosis and feature 010's whole purpose. Where the
  content determines whether the owner chooses right or wrong, it is a visible
  label — never a tooltip (Nielsen Norman's rule, applied directly).
- **Dark-first theming** with an app-level elevation token layer (ADR-0004).
- **App-agnostic design system in `frontend/ui/`** — the boundary is enforced
  (ADR-0002, ADR-0047).
- **Categories carry emoji** as part of their names (🍽️ Restaurantes,
  💼 Salary, 📈 Inversión).
- **Standing visual preference, chosen 2026-08-10:** the category standard,
  played straight — no irony, no smuggled quirk. The craft bar is **Linear and
  Stripe**: dense, restrained, tables taken seriously, keyboard-first, colour
  only where it carries meaning. Offered a distinctive alternative world and an
  austere data-field one, the owner took the standard deliberately.
- **Three red lines, stated by the owner the same day.** A polished result is
  wrong if it (1) hides behind one extra click a number that is visible today,
  (2) looks like a consumer bank app — cards everywhere, gradients, decorative
  charts, (3) trades dense tables for air: Transacciones must keep showing many
  rows per screen.
- **Everything visible, better ranked.** Asked whether the explanation lines
  under each fund could move behind a disclosure, the owner refused: nothing is
  hidden, the ranking does the work. Minimal here means hierarchy, not removal.

## Evidence on Hand

- **Real production data**, in the local Postgres container. Product decisions
  are argued from measurements against it: 477 posted expenses, 34 categories,
  131 uncategorised rows resolved by hand before the mandatory-category rule
  turned on, **zero fund rows** as of 2026-08-08, and one goal reading
  `$0 of $10.000.000` while the account it demanded held `$14.659.572`.
- **49 technical ADRs** in `docs/adr/` and **45 product ADRs** in
  `docs/decisions/product-decisions.md` — each with its rejected alternative and
  its consequence.
- **A UX audit**, `docs/ux/2026-08-audit.md` (2026-08-05): twelve screens,
  mobile, empty states, basic accessibility and the fund-creation flow, with
  numbered defects. The assistant was excluded from its scope by the owner.
- **`CHARTER.md`** — the signed engineering charter (architecture, conventions,
  scope, autonomy stance).
- **Absences that must not be invented:** there are no other users, no
  testimonials, no customers, no pricing, no public URL, no staging environment,
  no monitoring, and no e2e test layer. Nothing may claim otherwise.

## Product Principles

1. **Zero monthly ritual.** Any design that needs a recurring manual action ends
   up empty. This is measured, not theorised — seven months of data said so.
2. **Show the work.** Every headline number opens into the terms that produced
   it: the income it counted, each fund by name and amount, the uncovered
   spending. Nothing in it is unattributable.
3. **Teach what the app can do.** A capability nobody can find is a capability
   that does not exist; the owner ordering three built features proved it.
4. **Refuse rather than guess.** No rate, no COP figure. Resolving something
   twice is refused with the reason — the refusal *is* the feedback.
5. **The record and the money always agree.** No state the user cannot act on,
   no date consumed by a movement that no longer exists, no balance moved by a
   verb wearing the wrong name.

## Accessibility & Inclusion

No standard is established, and that is a confirmed answer rather than a gap:
one operator, on his own Mac, with no screen reader in use and no keyboard-only
requirement. The bar is that the figures read clearly in the dark-first theme.

Existing controls should still not lie to assistive tech where it costs nothing
to avoid — the audit's D15 (an unnamed checkbox at the form's most important
decision) was fixed by removing the control, not by adding a label.

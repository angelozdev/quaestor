---
title: "Every screen can explain itself, with the owner's own numbers"
slug: self-explaining-screens
number: 010
status: ready
autonomy_level: medium
branch: self-explaining-screens
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: fund-vs-budget-vocabulary
relevant_adrs: [0001, 0002, 0029, 0043, 0045]
created: 2026-08-05
intake: discuss
---

# Every screen can explain itself, with the owner's own numbers

## Outcome

On every screen, a discreet **¿Cómo funciona esto?** opens a panel that explains
what that screen does — not in general, but **using what the owner actually has
there right now**. It never interrupts and it is always available, in the same
place whether the screen holds data or not.

And every screen that is still empty teaches what the thing is and offers the
button that starts it, instead of spending the first visit on a label.

The fund rules stop being named after the arithmetic they run and start being
named after the job they do, so the picker and the panel say the same thing.

## Why

On 2026-08-05, in one conversation, the owner asked for **three capabilities
that were already built, tested and in production**. He commissioned all three
and could not find any of them.

| Lo que pidió | Lo que ya era |
|---|---|
| *"esos no son fondos sino presupuestos"* | a fund with the accumulate box unticked |
| saving what is left over for irregular costs | the same box, ticked |
| *"ahorrar mes a mes para una suscripción anual, ¿esto es posible?"* | the `from-recurring` rule, which also renews itself every cycle |

The UX audit (`docs/ux/2026-08-audit.md`) then found **the fourth instance, one
layer up**: the `EmptyState` component accepts an action button, and 10 of its
12 usages don't pass one. *"Aún no hay fondos"* appears at the moment of maximum
attention and maximum ignorance and says nothing about what a fund is.

The pattern is not a bad label. It is that **capability gets built and never
announced**.

## What the discuss decided

Decided 2026-08-05 by the owner, after the evidence was put to him.

**Form: the permanent panel only.** Not a modal tour, not dismissible
"did you know" cards. He picked the smallest of the three layers proposed.

**Why not a tour**, verified before proposing: HubSpot's 12-step tour was
completed by 28% of users, and completers adopted barely more features than
skippers; context-triggered help draws 2–3× the engagement of static
alternatives. A tour arrives when the user's head is elsewhere. A permanent
panel waits until he comes looking.

**Scope: inside 010**, not a separate feature. The rule names and the panel say
the same thing, so they get written once. This is what expanded 010 from a
copy change into a help surface, and why the slug was renamed the same day.

## Scope

- **A `¿Cómo funciona esto?` control on the screens**, in the page header,
  discreet, never auto-opening. Opens a side panel.
- **The panel speaks about the owner's real data**, not generic examples. On
  Fondos it names his funds, what each asks this month, and why. Affordable
  precisely because Quaestor has exactly one user (CHARTER §4) — no
  segmentation, no analytics, no targeting to build.
- **The ten empty screens teach**, in one or two sentences, and offer the button
  that starts the thing. The shared component already accepts that button and
  ten of its twelve uses don't pass one.
- **The rule picker names the job, not the arithmetic**, with a one-line
  consequence carrying a number under each option.
- **The accumulate checkbox disappears.** Which of the two shapes is being made
  is the first thing the owner chooses, in his own words, and it decides the
  rollover for him.
- **The table shows the two shapes as two labelled groups**, so the owner can
  read his own setup back.
- **Out of scope:** every line of fund arithmetic — `domain/rules.py` and
  `services/funds.py` untouched, no migration, no schema change. The two layers
  the owner declined, plus the *"lo que todavía no usas"* section he cut at CP2.
  The assistant, excluded from the audit at his request.
  The audit's other findings, which stay there as their own candidates.

## What the panel looks like

Drafted with the sandbox's real figures, as the shape to build toward:

```
¿Cómo funciona esto?                                       [×]

Un PRESUPUESTO es un tope del mes: lo que no gastes, no se
guarda. Un FONDO va juntando: lo que sobre pasa al mes
siguiente.

LO QUE TIENES AHORA MISMO

Restaurantes · presupuesto · pide $89.000 este mes
  El tope sale del promedio de lo que gastaste antes.
  Si gastas $60.000, septiembre vuelve a $89.000.

Mercado · fondo · pide $10.000.000 este mes
  Va juntando para una fecha.
  ⚠️ Pide más de lo que entra al mes.
```

## What CP2 decided

Answered 2026-08-07 in `acs.md`, 21 ACs.

- **Two nouns**, *presupuesto* and *fondo* — recorded as product ADR-042,
  amending ADR-037 in vocabulary and upholding every mechanism in it.
- **The menu reads `Fondos y presupuestos`**, so the word is visible without a
  click.
- **All ten app screens** get the panel, not just Fondos.
- **The *"lo que todavía no usas"* section is cut** by the owner. It was the
  only part that spoke without being opened; what survives teaches at the start
  (the empty screen) and on demand (the panel).
- **The panel is in the same place with or without data**; with nothing of his
  own to quote it explains with worked examples, marked as examples.
- **The empty screens are in**, absorbing the audit's D13.
- **003's `spec.md` earns no AC** — the arithmetic does not move, and AC-18
  states that the 003 suite is what proves it.
- **The assistant does not learn the word**, and the gap is named rather than
  fixed. Roadmap material.

## Charter signals

- **Frontend-only.** The local test surface covers it fully: vitest plus 003's
  acceptance suite proving no behaviour moved.
- **No migration**, so CHARTER §7's data gate does not apply.
- **UI copy is Spanish** (CHARTER §3, ADR-0001) — this feature is almost
  entirely that copy, the surface ADR-0001 explicitly put out of scope and that
  no ADR has picked up since. Same gap as `id:error-contract`, from the client
  side.
- **`QueryBoundary` is the uniform async-state contract** (ADR-0029) and is what
  renders every `EmptyState` today — the panel must not invent a second pattern
  beside it.
- **Next.js here is not the one you know** (`frontend/AGENTS.md`): read the
  relevant guide in `node_modules/next/dist/docs/` before writing code.

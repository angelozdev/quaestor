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
relevant_adrs: [0001, 0002, 0029, 0043]
created: 2026-08-05
intake: discuss
---

# Every screen can explain itself, with the owner's own numbers

## Outcome

On every screen, a discreet **¿Cómo funciona esto?** opens a panel that explains
what that screen does — not in general, but **using what the owner actually has
there right now**. It never interrupts, it is always available, and it ends by
naming what the screen can do that he is *not* using yet, with a button that
starts it.

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
- **The panel ends with what is not being used**, and offers to start it. That
  section is the whole point: it is what was missing all four times.
- **The fund rule picker names the job, not the arithmetic**, with a one-line
  consequence carrying a number under each option.
- **The accumulate choice** stops being a bare checkbox; the screen says which
  of the two shapes is being created and what it means next month.
- **The funds table** says which shape each fund is, so the owner can read his
  own setup back.
- **A product decision** in `docs/decisions/product-decisions.md`: whether the
  two accumulate shapes get separate names (*presupuesto* / *fondo*) or stay one
  noun with a stated mode. This partly re-expands what ADR-037 collapsed, so it
  is argued, not assumed.
- **Out of scope:** every line of fund arithmetic — `domain/rules.py` and
  `services/funds.py` untouched, no migration, no schema change. The two layers
  the owner declined. The assistant, excluded from the audit at his request.
  The audit's other findings, which stay there as their own candidates.

## What the panel looks like

Drafted with the sandbox's real figures, as the shape to build toward:

```
¿Qué es un fondo?                                          [×]

Aparta plata todos los meses para una categoría, sin que
tengas que acordarte.

TUS FONDOS AHORA MISMO

Restaurantes · pide $89.000 este mes
  Es el promedio de lo que gastaste antes.
  No acumula: si gastas $60.000, los $29.000 que sobran
  NO pasan a septiembre.

Mercado · pide $10.000.000 este mes
  Va juntando para una fecha.
  ⚠️ Pide más de lo que entra al mes.

LO QUE TODAVÍA NO USAS

Pagar suscripciones mes a mes
  Netflix te cobra $35.000. Un fondo con esta regla lo
  aparta solo y se renueva cada ciclo sin que hagas nada.
  [ Crear ese fondo ]
```

## Open questions for CP2

- One noun with a stated mode, or two nouns (*presupuesto* / *fondo*)?
- All 12 screens in this feature, or screen by screen starting with Fondos?
- How does *"lo que todavía no usas"* decide what to show — a hand-written list
  per screen, or derived from what the data says is absent?
- Does the panel work on a phone, where a side panel becomes a full sheet? (The
  audit's D10 says mobile has bigger problems first.)
- Does anything in 003's `spec.md` earn an AC from the renamed rules?
- Does the assistant's vocabulary move too, or only the screens?

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

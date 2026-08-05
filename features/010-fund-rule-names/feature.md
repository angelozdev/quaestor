---
title: "Each fund rule says what job it does, not what arithmetic it runs"
slug: fund-rule-names
number: 010
status: ready
autonomy_level: medium
branch: fund-rule-names
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: fund-vs-budget-vocabulary
relevant_adrs: [0001, 0002, 0043]
created: 2026-08-05
intake: discuss
---

# Each fund rule says what job it does, not what arithmetic it runs

## Outcome

The owner opens the fund form and finds the tool he came for, by reading. Each
of the four rules states the job it does in his own words and with a number, so
"a monthly ceiling on Restaurantes", "a pot for the annual insurance" and
"paying a yearly subscription month by month" each land on the right option
without anyone explaining it to him. Nothing about how funds compute moves.

## The evidence, gathered in one session

On 2026-08-05, while discussing named goals, the owner asked for **three
capabilities that are already built, tested and running in production**. He did
not know any of them existed. He is the person who commissioned all three.

| What he asked for | What it already is | How it is labelled today |
|---|---|---|
| *"esos no son fondos sino presupuestos"* — a monthly ceiling that does not roll over | `accumulates=false` | an unexplained checkbox, *"Acumula lo que sobra cada mes"* |
| a pot that carries the leftover forward | `accumulates=true` | the same checkbox, ticked |
| *"ahorrar mes a mes para pagar una suscripción anual — ¿esto es posible?"* | the `from-recurring` rule | *"Lo que piden sus obligaciones"* |

The third is the sharpest. `from-recurring` does exactly what he described and
then some: with a 600.000 yearly charge due in March, from August it asks 85.715
a month, and the month the charge is settled it rolls straight on to the next
cycle (`_charge_month_for`, AC-11) — it renews itself forever with no action
from him. He asked whether it was *possible*.

## The diagnosis

This is not one bad checkbox. All four rules are named after **the arithmetic
they run**:

```
Monto fijo
Promedio de los últimos meses
Lo que piden sus obligaciones
Meta con fecha
```

None of them names **the job the owner came to do**. A person who wants a
spending limit does not think "fixed amount, non-accumulating" — he thinks
"I don't want to spend more than $100.000 a month on restaurants". The form
answers a question he is not asking.

The word *presupuesto* appears nowhere in the product, and nothing on the screen
says what ticking the accumulate checkbox changes.

## Scope

- **The rule picker.** Each of the four options states its job in the owner's
  words, with a one-line consequence carrying a number.
- **The accumulate choice.** Stops being a bare checkbox: whatever the two
  resulting shapes end up being called, the screen says which one you are
  creating and what it means next month.
- **The funds table.** Each existing fund says which shape it is, so the owner
  can read his own setup back.
- **A product decision** in `docs/decisions/product-decisions.md`: whether the
  two accumulate shapes get separate names in the product (*presupuesto* vs
  *fondo*) or stay one noun with a stated mode. This partly re-expands what
  ADR-037 deliberately collapsed, so it needs to be argued, not assumed.
- **Out of scope:** every line of fund arithmetic. `domain/rules.py` and
  `services/funds.py` are not touched. No migration, no schema change, no new
  API field. If this feature changes behaviour, it has gone wrong.

## Why this outranks building anything new

Raised to roadmap priority 1 during the discuss that promoted 009. New surfaces
inherit the same naming instinct and become invisible the same way — the metas
screen would have been the fourth. And that screen has to explain why a meta is
neither a presupuesto nor a fondo regardless, so the vocabulary is paid for once
here or twice later.

Feature 009 (`named-goals`) is promoted, `ready`, and deliberately waiting on
this.

## Open questions for CP2

- One noun with a stated mode, or two nouns (*presupuesto* / *fondo*)? The
  decision ADR-037's collapse makes non-obvious.
- Does the picker keep four options, or group them by job first and ask for the
  arithmetic second?
- Does an existing fund's shape need to be visible anywhere beyond the funds
  table — the money-available screen, the monthly report?
- Does anything in 003's `spec.md` earn a new AC from this? Its scenarios never
  state the ceiling/envelope difference in owner-facing words either.
- Does the assistant's vocabulary move too, or only the screens? (`mcp/` speaks
  its own text via `format.py`.)

## Charter signals

- **Frontend-only**, so the local test surface covers it fully: vitest plus the
  003 acceptance suite proving nothing moved.
- **No migration**, so CHARTER §7's data gate does not apply.
- **UI copy is Spanish** (CHARTER §3, ADR-0001) — this feature is almost
  entirely that copy, which is exactly the surface ADR-0001 put out of scope and
  no ADR has picked up since. Related to `id:error-contract`, which is the same
  gap seen from the server side.

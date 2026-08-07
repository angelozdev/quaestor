---
ac_count: 21
high_priority_count: 15
discovered: 2026-08-07
---

# Acceptance criteria — 010 self-explaining-screens

Discovered 2026-08-07 (Checkpoint 2), greenfield mode. Nothing specified here
exists: the app ships zero help text of any kind — no tooltip, no line under a
field, no empty state that teaches.

Source material: `feature.md` and the roadmap promotion it came from, the UX
audit of 2026-08-05 (`docs/ux/2026-08-audit.md`, 16 findings over 12 screens),
the shipped funds screen and its create form, the shared `EmptyState` and
`PageHeader`, and product ADR-037 — which this feature amends in vocabulary and
upholds in mechanism.

## Why these ACs exist

On 2026-08-05 the owner asked for **three capabilities that were already built,
tested and in production**, and did not know any of them existed. He had
commissioned all three. The audit then found a fourth instance one layer up: the
shared empty-state component accepts a "start here" button and ten of its twelve
uses do not pass one.

The pattern is not a bad label. **Capability gets built and never announced.**

## Decisions taken during discovery

**1. The two shapes get two names — `presupuesto` and `fondo`.** A ceiling that
resets each month is a *presupuesto*; a pot that carries what is left over is a
*fondo*. Put to the owner with the arithmetic spelled out: $100.000 a month on
Restaurantes, spend $60.000 — a presupuesto goes back to $100.000 in September
and the $40.000 are gone; a fondo opens September with $140.000.

He picked two names. The evidence that decided it is that he had already
produced the distinction unprompted, in the right words: *"esos no son fondos
sino presupuestos"*.

**This amends product ADR-037 in vocabulary only.** ADR-037 collapsed
*mechanisms* — three tables, a goals screen, a monthly assignment ritual — into
one. It did not require one word. After this change there is still one record
shape, one screen, one create form and zero monthly ritual; what splits is what
the owner is told he is making. Recording it as a product decision is part of
this checkpoint's output (see the handoff).

**2. The menu carries both words.** `Fondos y presupuestos`, not `Fondos`. The
menu is the only place the word is visible without a click, and being invisible
until clicked is the exact failure this feature exists to fix.

**3. The panel goes on every screen**, not only Fondos — all ten app screens the
owner selected: Fondos y presupuestos, Tablero, Recurrentes, Categorías,
Cuentas, Grupos, Etiquetas, Transacciones, Por pagar and Reportes.

**4. The section "LO QUE TODAVÍA NO USAS" is dropped.** `feature.md` called it
"the whole point" and staged an open question about how it would decide what to
show; the owner cut it outright — *"esto no lo necesitamos"*.

**The consequence is recorded rather than argued.** That section was the only
part of the design that would have spoken without being opened. What survives is
two doors the owner still has to walk through: the empty state, which teaches
once, at the beginning; and the panel, which teaches whenever he goes looking.
Neither speaks on its own to someone who already has data and does not know what
he is missing — which is the situation that produced all four instances.

**5. The empty screens teach.** Ten of twelve uses of the shared empty state say
a label and nothing else. They gain a sentence about what the thing is and a
button that starts it.

**6. The panel is in the same place whether or not there is data.** With no
figures of his own to quote, it explains with worked examples. Rejected: hiding
the control until data exists, which would make its location something to learn.

## What this feature must not do

**Not one line of the arithmetic moves.** `domain/rules.py` and
`services/funds.py` are untouched, no migration, no schema change. AC-18 is the
statement of that, and 003's acceptance suite is what proves it.

**The assistant is out of scope**, excluded by the owner during the audit. The
risk this leaves is named rather than fixed: after this feature the screens say
*presupuesto* and the assistant does not know the word. Filed for the roadmap,
not for here.

**The audit's other findings are out of scope** — D1 through D4, D6 through D12,
D16 stay in `docs/ux/2026-08-audit.md` as their own candidates. D5 (the form
explains nothing), D13 (empty states teach nothing) and D15 (the accumulate
control is unnamed to a screen reader) are the three this feature absorbs.

## Coverage checklists

Step 3b ran and matched nothing. The feature is a UI surface for humans, which
points at `accessibility.md` — that checklist is listed as *(when written)* and
does not exist in the plugin yet. No auth, no deploy surface, no public web page
(the app is local-only, ADR-0026), no schema change. Accessibility ACs below
(AC-19, AC-20) were written from the audit's own findings instead, and the
missing checklist is flagged in the handoff.

---

## AC-1: The two shapes have two names, and the menu carries both

- **Priority:** high
- **Type:** happy-path

A monthly ceiling whose leftover money disappears is called a **presupuesto**. A
pot that carries its leftover money forward is called a **fondo**.

Both words appear in the navigation — `Fondos y presupuestos` — so the owner
looking for either one finds it without opening anything.

## AC-2: Each list says what its shape does, in the heading

- **Priority:** high
- **Type:** happy-path

The screen shows the two shapes as two labelled groups, and each label states
the behaviour rather than naming it: presupuestos are *topes del mes*, fondos
*van juntando*.

An owner who reads only the two headings can already tell which one he wants.

## AC-3: Every row says what happens to leftover money next month, with its own number

- **Priority:** high
- **Type:** happy-path

Each entry states the consequence using its own figures, not a generic
description. A presupuesto on Restaurantes asking $89.000 that has been spent
down to $60.000 says September goes back to $89.000 and the rest is not kept. A
fondo in the same position says September opens with the difference added.

This is the audit's D4: the table showed *Regla / Pide / Tiene / Estado* and
nowhere said whether the money accumulated — the one thing that separates the
two shapes.

## AC-4: Creating starts from the job, with one entry point per shape

- **Priority:** high
- **Type:** happy-path

There are two ways in — one that makes a presupuesto and one that makes a fondo
— and choosing between them is the first decision, made in the owner's own
words, before any rule or amount is asked for.

Today there is a single *Nuevo fondo* button leading to a form that asks for the
mechanism first.

## AC-5: The rule picker names the job and carries a worked number

- **Priority:** high
- **Type:** happy-path

Each option says what it is for and shows one worked consequence with a figure,
not the calculation it performs.

*"Lo que piden sus obligaciones"* becomes something closer to *"Pagar
suscripciones y cuotas que ya tengo registradas — Netflix cobra $600.000 en
marzo; desde agosto aparto $85.715 al mes, y cuando se paga empieza sola para el
año siguiente."*

This is the option the owner asked to have built while it already existed.

## AC-6: The accumulate checkbox disappears

- **Priority:** high
- **Type:** happy-path

Whether money carries forward is decided by which of the two things the owner
said he was making. He is never shown a bare checkbox for it.

Every combination reachable today stays reachable: the two rules that offer the
choice reach both shapes, and the two that must carry money forward reach only
the fondo.

## AC-7: Every screen carries the same "¿Cómo funciona esto?" control, in the same place

- **Priority:** high
- **Type:** happy-path

All ten screens put it in the page header, in the same position, looking the
same. Opening it opens a panel about that screen.

The screens: Fondos y presupuestos, Tablero, Recurrentes, Categorías, Cuentas,
Grupos, Etiquetas, Transacciones, Por pagar, Reportes.

## AC-8: The panel explains the screen using the owner's own figures

- **Priority:** high
- **Type:** happy-path

It names what is actually on that screen and what each thing is doing, not a
generic description of the feature.

On Fondos: *"Restaurantes es un presupuesto — pide $89.000 este mes porque es el
promedio de lo que gastaste antes. Lo que sobre no pasa a septiembre."* On the
Tablero, where the money available is negative: what came in, what each fund
asks by name, and which one asks for more than the month brings in.

Affordable precisely because the app has exactly one user (CHARTER §4) — there
is no segmentation or targeting to build.

## AC-9: The panel never opens by itself

- **Priority:** high
- **Type:** happy-path

It appears only when the owner asks for it, and closing it does not make it
appear again later. Nothing pops up, nothing steps through the screen, nothing
reappears after being dismissed.

Verified before proposing: a well-known 12-step product tour was completed by
28% of users, and the completers adopted barely more than the people who
skipped it, while help triggered by the user in context draws two to three times
the engagement.

## AC-10: An empty screen teaches and offers the way in

- **Priority:** high
- **Type:** edge-case

A screen with nothing on it yet says in one or two sentences what the thing is
and what it is good for, then offers a button that starts creating one.

*"Aún no hay fondos"* becomes *"Todavía no tienes fondos ni presupuestos. Un
fondo aparta plata todos los meses para una categoría, sin que tengas que
acordarte — para juntar lo del mantenimiento del carro, o para pagar una
suscripción anual mes a mes. Un presupuesto es un tope: lo que no gastes no se
guarda."* with a button.

This is the moment of maximum attention and maximum ignorance. Ten of twelve
empty screens currently spend it on a label.

## AC-11: With nothing of his own to quote, the panel explains with worked examples

- **Priority:** high
- **Type:** edge-case

When the screen holds no data, the panel still opens and still explains, using
figures from an example instead of the owner's — and says they are an example,
so a number on the panel is never mistaken for one of his.

## AC-12: A shape that must carry money forward is never offered as a presupuesto

- **Priority:** high
- **Type:** edge-case

Two of the four rules always accumulate — the one that reads the owner's
recurring charges and the one that saves toward a date. Neither appears when he
is making a presupuesto, and he is never able to reach a combination the app
would then refuse.

## AC-13: Everything created before the split keeps working, under the right heading

- **Priority:** high
- **Type:** edge-case

Nothing already created is edited, migrated or asked about. Each existing entry
appears under the heading that matches what it already does, and asks and holds
exactly what it asked and held the day before.

## AC-14: The panel is readable on a phone without scrolling sideways

- **Priority:** medium
- **Type:** edge-case

At 390px the panel takes the width it needs and its text wraps; nothing is cut
off and nothing requires horizontal scrolling to read.

The audit's D10 records that tables on this app already fail that test; the
panel must not add a second instance.

## AC-15: A category still holds exactly one of these, and the screen says so before the attempt

- **Priority:** medium
- **Type:** edge-case

Two names do not mean two per category. When a category already carries one, the
create form makes that visible while choosing the category, and the reason is
stated in the new words rather than left to a refusal after submitting.

## AC-16: If the screen's figures cannot be loaded, the panel still opens and still explains

- **Priority:** medium
- **Type:** error

The explanation of what a screen does never depends on that screen's data having
arrived. When the figures are missing, it falls back to the example form of
AC-11 rather than disappearing or showing blanks.

## AC-17: A refusal is stated in the new vocabulary

- **Priority:** medium
- **Type:** error

Wherever the app already refuses something about these — a second one on the
same category, a rule missing its amount — what the owner reads uses the same
two words the rest of the screen uses.

Bounded by what the screen can say on its own: the server's own wording is
English today and is tracked separately as the roadmap's `id:error-contract`.

## AC-18: Nothing about what a fondo asks or holds changes

- **Priority:** high
- **Type:** cross-cutting

Every figure the app computes is identical before and after. What each entry
asks for this month, what it holds, whether it is on track, and the money
available — all unchanged.

This is the feature's own falsification test: if any of it moves, the feature
went wrong. 003's acceptance suite is what proves it.

## AC-19: The panel can be opened, read and closed with the keyboard alone

- **Priority:** medium
- **Type:** cross-cutting

Reachable by tabbing, opens without a mouse, closes the way panels close, and
puts the reader back where he was when it closes.

## AC-20: Every control that decides whether money accumulates is named out loud

- **Priority:** medium
- **Type:** cross-cutting

Anything that determines the shape announces what it is to a screen reader.

The audit's D15: today the accumulate control announces itself as an unnamed
checkbox — every other field in that form names itself correctly, and this is
the one that matters most.

## AC-21: One vocabulary, everywhere

- **Priority:** high
- **Type:** cross-cutting

The menu, the headings, the create buttons, the rule options, the rows, the
empty screens and the panel all use the same two words for the same two things.
No screen calls a presupuesto a fondo, and no screen introduces a third word for
either.

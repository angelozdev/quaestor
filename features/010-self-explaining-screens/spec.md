# Acceptance specs — 010 self-explaining-screens

Formalizes `acs.md` (21 ACs, approved 2026-08-07) as standard Gherkin.

**Third draft.** The first (51 scenarios) was audited and returned *not fit as
contract*, 25 findings. The second (93) was audited twice — once by the same
reviewer checking its own findings, once independently and blind — and returned
17 addressed, 7 partial, and 12 more defects. This draft answers both. The
corrections are named rather than quietly applied, because two of them changed
what the feature is.

Amounts are plain decimals (`100000.00 COP`), no thousands separators, chosen to
divide cleanly. Category names are plain rather than the emoji ones production
carries, matching the other suites.

**Two nouns, decided at CP2 and recorded as product ADR-042.** A *presupuesto*
is a monthly ceiling: what is not spent is not kept. A *fondo* carries what is
left over into the next month. One record shape underneath, one screen, one
form, zero monthly ritual — ADR-037's collapse stands, and only the vocabulary
splits.

## Three figures are new, and that is a deliberate scope change

`feature.md` originally declared this feature frontend-only. **It is not, and
the owner decided so at CP3 with the flow in front of him.** A fund reports
three figures it has never reported:

- **what the category spent this month** — `_Month.spent`, computed on every
  fold and dropped at the boundary
- **what it carries into next month** — one more evaluation of
  `fund_next_opening_calc`, which the fold already runs for every month *before*
  the one being asked about and returns before running for that one
- **what it will have to spend next month** — that carry plus next month's ask,
  which is the fold advancing one month

None is new arithmetic and no existing figure moves, which is what AC-18 and
003's suite exist to prove. The third was found late: AC-3's presupuesto row
asserts *"$40.000 no se guardan"*, and `ask − spent` is derivable from nothing
the screen receives today.

## The three streams

**Untagged — the screen.** Bound to frontend tests per ADR-0045.

**`@backend` — what a fund reports.** Thirteen scenarios. The observable is a
reported figure, so a mocked frontend would prove nothing. **These reuse 003's
step vocabulary wherever it fits** — `a fund on "X" that asks a fixed …`, `the
fund on "X" asks N COP this month`, `holds N COP`, `is behind`, `a recorded
expense of N COP in category "X" this month`, `the money available this month is
N COP`. Nine step families are new rather than the three first estimated: three
for the new figures, and six because **this feature renames all four rules into
plain language**, which is the whole point of it. They say **fund**, not *fondo*
or *presupuesto*, because their subject is the record and not the screen — AC-21
governs what a screen says.

**`@browser` — what a DOM emulator cannot see.** jsdom and happy-dom have no
layout engine and report every element as zero-sized, so anything about width,
overflow, wrapping or position lives here, verified against the running stack
with the observation recorded in the handoff.

ADR-0045 named only `@browser`; it is amended by this feature to define
`@backend`, because leaving thirteen scenarios exempt from every gate is the "prose
nobody executes" outcome that ADR exists to prevent.

## Not every scenario is red

**Eight are green by design** — AC-18's seven `@backend` scenarios and AC-13's
one — because their entire job is to assert that untouched behaviour is
untouched. The five that start red are AC-3's, which carry the new figures.
003's spec made the same distinction for the same reason. Everything else is red:
the app ships zero help text of any kind, and `¿Cómo funciona esto?` exists
nowhere.

## Two things the audits proved false, corrected here

**`Excluir del presupuesto` does not exclude anything.** `services/categories.py`
says so in its own docstring — *"Stored and read by nothing since feature 003
took the envelope out"*. The live setting is `Excluir de los totales`, a
different checkbox. An earlier draft asserted the word meant "a category left
out of a calculation"; it means nothing. **The owner decided to remove the dead
checkbox and its `no-presup.` badge from the screen**, which is AC-21's last two
scenarios. Nothing stored is deleted.

**`Fondo` already labels presupuestos on two screens** — the Dashboard and
Reportes both render every fund as `Fondo · <name>`. **The owner decided AC-21
reaches every site found**: those two, the toasts, the delete dialog and its
label, the empty screen, and Ajustes' surviving mention of *metas*.

**Screen names are quoted as the product labels them today**, with one
exception: `Fondos y presupuestos` is the label AC-1 exists to create. `Dashboard`
stays English — that is the audit's D6 and is out of scope here; `acs.md` calls
it *Tablero*, and the spec follows the product rather than the AC.

**The panel's exact wording is not pinned.** `states that …` asserts that a named
fact is present, with its figure where the scenario gives one.

**Order is not pinned.** Nothing here decides how entries are sorted.

**Amended after approval, 2026-08-07, on the owner's explicit permission.** He
used the running app and asked that clicking outside the panel close it — the
affordance people reach for first in a sheet, whose absence makes the panel feel
like it has trapped them. AC-9 gains two scenarios: the close itself, asserting
focus returns to the trigger so all three close paths must share one route; and
the case that betrays a naive implementation, where a press begins inside the
panel and is released outside while selecting text.

```gherkin
Feature: Every screen can explain itself, with the owner's own numbers
```

## AC-1 — The two shapes have two names, and the menu carries both

```gherkin
Scenario: The navigation names both shapes
  When the owner looks at the navigation
  Then the navigation offers "Fondos y presupuestos"

Scenario: The two shapes are told apart on one screen
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then "Restaurantes" appears under the presupuestos heading
  And "Tecnologia" appears under the fondos heading
```

## AC-2 — Each list says what its shape does, in the heading

```gherkin
Scenario: The presupuestos heading states that leftover money is not kept
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then the presupuestos heading states that what is not spent is not kept

Scenario: The fondos heading states that leftover money is carried forward
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then the fondos heading states that what is left over passes to the next month

Scenario: Both headings are shown with one shape under each
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then exactly 1 entry appears under the presupuestos heading
  And exactly 1 entry appears under the fondos heading
```

## AC-3 — Every row says what happens to leftover money next month, with its own number

```gherkin
@backend
Scenario: A fund reports what the category spent this month
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Tecnologia" this month
  Then the fund on "Tecnologia" spent 60000.00 COP this month

@backend
Scenario: An accumulating fund reports what it carries and what next month holds
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Tecnologia" this month
  Then the fund on "Tecnologia" carries 40000.00 COP into next month
  And the fund on "Tecnologia" will have 140000.00 COP to spend next month

@backend
Scenario: A resetting fund reports that it carries nothing
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 100000.00 COP each month without accumulating, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Restaurantes" this month
  Then the fund on "Restaurantes" carries 0.00 COP into next month
  And the fund on "Restaurantes" will have 100000.00 COP to spend next month

@backend
Scenario: An untouched accumulating fund carries its whole month forward
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  Then the fund on "Tecnologia" carries 100000.00 COP into next month
  And the fund on "Tecnologia" will have 200000.00 COP to spend next month

@backend
Scenario: A fund whose rule recomputes next month reports next month's own figure
  Given today is 2026-08-15
  And the app has recorded movements since 3 months ago
  And an expense category "Mercado"
  And a recorded expense of 300000.00 COP in category "Mercado" 3 months ago
  And a recorded expense of 300000.00 COP in category "Mercado" 2 months ago
  And a recorded expense of 300000.00 COP in category "Mercado" 1 month ago
  And a fund on "Mercado" that asks what the category averaged over the last 3 months, starting 2026-08
  And a recorded expense of 100000.00 COP in category "Mercado" this month
  Then the fund on "Mercado" asks 300000.00 COP this month
  And the fund on "Mercado" carries 200000.00 COP into next month
  And the fund on "Mercado" will have 433333.34 COP to spend next month

Scenario: A fondo's row states what is kept, with its figure
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And 60000.00 COP was spent on "Tecnologia" this month
  When the owner opens the "Fondos y presupuestos" screen
  Then the row for "Tecnologia" states that 60000.00 COP was spent
  And the row for "Tecnologia" states that 40000.00 COP is kept

Scenario: A fondo's row states what next month will have to spend
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And 60000.00 COP was spent on "Tecnologia" this month
  When the owner opens the "Fondos y presupuestos" screen
  Then the row for "Tecnologia" states that next month has 140000.00 COP to spend

Scenario: A presupuesto's row states that the leftover money is lost, with its figure
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  And 60000.00 COP was spent on "Restaurantes" this month
  When the owner opens the "Fondos y presupuestos" screen
  Then the row for "Restaurantes" states that 60000.00 COP was spent
  And the row for "Restaurantes" states that 40000.00 COP is not kept
  And the row for "Restaurantes" states that next month restarts at 100000.00 COP

Scenario: A fondo in its first month says why it is holding nothing yet
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And 60000.00 COP was spent on "Tecnologia" this month
  When the owner opens the "Fondos y presupuestos" screen
  Then the row for "Tecnologia" states that it holds 0.00 COP
  And the row for "Tecnologia" states that it holds nothing yet because it started this month
```

## AC-4 — Creating starts from the job, with one entry point per shape

```gherkin
Scenario: The screen offers one way in for each shape
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen offers to create a presupuesto
  And the screen offers to create a fondo

Scenario: The single old way in is gone
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen offers no way in that does not name a shape

Scenario: No rule is asked for until a shape has been chosen
  When the owner opens the "Fondos y presupuestos" screen
  And the owner asks to create something
  Then a shape is asked for
  And no rule is asked for
  And no amount is asked for

Scenario: The form that opens already knows which shape it is making
  When the owner starts creating a presupuesto
  Then the form states that it is making a presupuesto
```

## AC-5 — The rule picker names the job and carries a worked number

```gherkin
Scenario: Three rules are offered for a fondo
  Given an expense category "Servicios"
  When the owner starts creating a fondo
  Then 3 rules are offered

Scenario: Every rule offered says what it is for
  Given an expense category "Servicios"
  When the owner starts creating a fondo
  Then every rule offered states what it is for

Scenario: No rule is named after the arithmetic it runs
  Given an expense category "Servicios"
  When the owner starts creating a fondo
  Then no rule is called "Monto fijo"
  And no rule is called "Promedio de los últimos meses"
  And no rule is called "Lo que piden sus obligaciones"
  And no rule is called "Meta con fecha"

Scenario: The subscription rule says what it does with a real charge
  Given today is 2026-08-15
  And an expense category "Servicios"
  And a recurring charge "Netflix" on "Servicios" of 600000.00 COP every year, next due 2027-02
  When the owner starts creating a fondo on "Servicios", starting 2026-08
  Then the rule that reads recurring charges states that it asks 100000.00 COP each month

Scenario: The subscription rule says that it starts again on its own
  Given today is 2026-08-15
  And an expense category "Servicios"
  And a recurring charge "Netflix" on "Servicios" of 600000.00 COP every year, next due 2027-02
  When the owner starts creating a fondo on "Servicios", starting 2026-08
  Then the rule that reads recurring charges states that it starts again when the charge is paid

Scenario: The averaging rule works its figure from what the category cost
  Given today is 2026-08-15
  And the app has recorded movements since 1 month ago
  And an expense category "Restaurantes"
  And a recorded expense of 89000.00 COP in category "Restaurantes" 1 month ago
  When the owner starts creating a fondo on "Restaurantes", starting 2026-08
  Then the rule that averages what the category cost states that it asks 89000.00 COP each month

Scenario: The subscription rule says so when the category has none
  Given today is 2026-08-15
  And an expense category "Servicios"
  And "Servicios" has no recurring charges
  When the owner starts creating a fondo on "Servicios", starting 2026-08
  Then the rule that reads recurring charges states that it would ask 0.00 COP

Scenario: A category with no recurring charges is offered the way to register one
  Given today is 2026-08-15
  And an expense category "Servicios"
  And "Servicios" has no recurring charges
  When the owner starts creating a fondo on "Servicios", starting 2026-08
  Then the screen offers a way to register a recurring charge
```

## AC-6 — The accumulate checkbox disappears

```gherkin
Scenario: Making a presupuesto never asks whether money accumulates
  When the owner starts creating a presupuesto
  Then no control asks whether money accumulates

Scenario: Making a fondo never asks whether money accumulates
  When the owner starts creating a fondo
  Then no control asks whether money accumulates

Scenario: A presupuesto with a fixed amount is filed as a presupuesto
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  When the owner creates a presupuesto on "Restaurantes" asking a fixed 100000.00 COP each month, starting 2026-08
  Then "Restaurantes" appears under the presupuestos heading

Scenario: A fondo with a fixed amount is filed as a fondo
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  When the owner creates a fondo on "Tecnologia" asking a fixed 100000.00 COP each month, starting 2026-08
  Then "Tecnologia" appears under the fondos heading

Scenario: A presupuesto from the category average is filed as a presupuesto
  Given today is 2026-08-15
  And the app has recorded movements since 1 month ago
  And an expense category "Restaurantes"
  And a recorded expense of 90000.00 COP in category "Restaurantes" 1 month ago
  When the owner creates a presupuesto on "Restaurantes" asking what the category averaged over the last 1 month, starting 2026-08
  Then "Restaurantes" appears under the presupuestos heading

Scenario: A fondo from the category average is filed as a fondo
  Given today is 2026-08-15
  And the app has recorded movements since 1 month ago
  And an expense category "Mercado"
  And a recorded expense of 90000.00 COP in category "Mercado" 1 month ago
  When the owner creates a fondo on "Mercado" asking what the category averaged over the last 1 month, starting 2026-08
  Then "Mercado" appears under the fondos heading

Scenario: A fondo that reads recurring charges is filed as a fondo
  Given today is 2026-08-15
  And an expense category "Servicios"
  And a recurring charge "Netflix" on "Servicios" of 600000.00 COP every year, next due 2027-02
  When the owner creates a fondo on "Servicios" asking what its recurring charges need, starting 2026-08
  Then "Servicios" appears under the fondos heading

Scenario: The Dashboard offers to explain itself
  When the owner opens the "Dashboard" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Dashboard" screen does

Scenario: Transacciones offers to explain itself
  When the owner opens the "Transacciones" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Transacciones" screen does

Scenario: Fondos y presupuestos offers to explain itself
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Fondos y presupuestos" screen does

Scenario: Recurrentes offers to explain itself
  When the owner opens the "Recurrentes" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Recurrentes" screen does

Scenario: Por pagar offers to explain itself
  When the owner opens the "Por pagar" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Por pagar" screen does

Scenario: Categorías offers to explain itself
  When the owner opens the "Categorías" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Categorías" screen does

Scenario: Grupos offers to explain itself
  When the owner opens the "Grupos" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Grupos" screen does

Scenario: Etiquetas offers to explain itself
  When the owner opens the "Etiquetas" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Etiquetas" screen does

Scenario: Cuentas offers to explain itself
  When the owner opens the "Cuentas" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Cuentas" screen does

Scenario: Reportes offers to explain itself
  When the owner opens the "Reportes" screen
  Then the screen offers "¿Cómo funciona esto?"
  And opening it explains what the "Reportes" screen does

@browser
Scenario: The control sits in the same place on every screen
  When the owner opens each of the ten screens in turn
  Then "¿Cómo funciona esto?" is in the same position on every one
  And it looks the same on every one
```

## AC-8 — The panel explains the screen using the owner's own figures

```gherkin
Scenario: The panel names what is on the screen
  Given today is 2026-08-15
  And the app has recorded movements since 1 month ago
  And an expense category "Restaurantes"
  And a recorded expense of 89000.00 COP in category "Restaurantes" 1 month ago
  And a presupuesto on "Restaurantes" that asks what the category averaged over the last 1 month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel names "Restaurantes"

Scenario: The panel states the figure the screen is showing
  Given today is 2026-08-15
  And the app has recorded movements since 1 month ago
  And an expense category "Restaurantes"
  And a recorded expense of 89000.00 COP in category "Restaurantes" 1 month ago
  And a presupuesto on "Restaurantes" that asks what the category averaged over the last 1 month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that "Restaurantes" asks 89000.00 COP this month

Scenario: The panel states why the figure is that figure
  Given today is 2026-08-15
  And the app has recorded movements since 1 month ago
  And an expense category "Restaurantes"
  And a recorded expense of 89000.00 COP in category "Restaurantes" 1 month ago
  And a presupuesto on "Restaurantes" that asks what the category averaged over the last 1 month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that the figure is what the category averaged

Scenario: The panel states what came in and what each fund asked for
  Given today is 2026-08-15
  And an income of 3000000.00 COP is due this month
  And an expense category "Mercado"
  And a fondo on "Mercado" saving 10000000.00 COP by 2026-09, starting 2026-08
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 89000.00 COP each month, starting 2026-08
  When the owner opens the "Dashboard" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that 3000000.00 COP comes in this month
  And the panel states that "Mercado" asks 10000000.00 COP
  And the panel states that "Restaurantes" asks 89000.00 COP

Scenario: The panel singles out the one fund asking more than the month brings in
  Given today is 2026-08-15
  And an income of 3000000.00 COP is due this month
  And an expense category "Mercado"
  And a fondo on "Mercado" saving 10000000.00 COP by 2026-09, starting 2026-08
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 89000.00 COP each month, starting 2026-08
  When the owner opens the "Dashboard" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel names exactly 1 entry as asking more than comes in
  And the entry it names is "Mercado"

Scenario: Every screen's panel speaks about what that screen holds
  Given today is 2026-08-15
  And a recurring charge "Netflix" on "Servicios" of 35000.00 COP every month, next due 2026-09
  When the owner opens the "Recurrentes" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel names "Netflix"
  And the panel states that "Netflix" charges 35000.00 COP every month
```

## AC-9 — The panel never opens by itself

```gherkin
Scenario: The control is offered and nothing is open until it is used
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen offers "¿Cómo funciona esto?"
  And no panel is open

Scenario: Closing the panel closes it and leaves the way back
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  And the owner closes the panel
  Then no panel is open
  And the screen offers "¿Cómo funciona esto?"

Scenario: A panel that was closed does not come back on the next visit
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  And the owner closes the panel
  And the owner opens the "Recurrentes" screen
  And the owner opens the "Fondos y presupuestos" screen
  Then no panel is open

Scenario: Clicking outside the panel closes it
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  And the owner clicks outside the panel
  Then no panel is open
  And "¿Cómo funciona esto?" holds the keyboard's place again

Scenario: Selecting text in the panel and releasing outside does not close it
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  And the owner presses inside the panel and releases outside it
  Then a panel explains what the "Fondos y presupuestos" screen does
```

## AC-10 — An empty screen teaches and offers the way in

```gherkin
Scenario: An empty Fondos screen says what a fondo is for
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen states that a fondo keeps what is left over each month

Scenario: An empty Fondos screen says what a presupuesto is for
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen states that a presupuesto is a ceiling that does not keep what is left over

Scenario: An empty Fondos screen offers to create the first one
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen offers to create the first one

Scenario: An empty Recurrentes screen teaches and offers the way in
  Given no recurring charges exist
  When the owner opens the "Recurrentes" screen
  Then the screen states that a recurring charge is one that comes back on its own
  And the screen offers to create the first one

Scenario: An empty Categorías screen teaches and offers the way in
  Given no categories exist
  When the owner opens the "Categorías" screen
  Then the screen states that a category is what a movement was for
  And the screen offers to create the first one

Scenario: An empty Cuentas screen teaches and offers the way in
  Given no accounts exist
  When the owner opens the "Cuentas" screen
  Then the screen states that an account is where money sits
  And the screen offers to create the first one

Scenario: An empty Grupos screen teaches and offers the way in
  Given no category groups exist
  When the owner opens the "Grupos" screen
  Then the screen states that a group gathers categories that belong together
  And the screen offers to create the first one

Scenario: An empty Etiquetas screen teaches and offers the way in
  Given no tags exist
  When the owner opens the "Etiquetas" screen
  Then the screen states that a tag marks movements across categories
  And the screen offers to create the first one

Scenario: An empty Transacciones screen teaches and offers the way in
  Given no movements exist
  When the owner opens the "Transacciones" screen
  Then the screen states that a movement is money coming in or going out
  And the screen offers to record the first one

Scenario: An empty Dashboard teaches where its figures come from
  Given no movements exist
  When the owner opens the "Dashboard" screen
  Then the screen states that its figures come from the movements recorded
  And the screen offers to record the first one

Scenario: An empty Por pagar screen teaches what it would show
  Given nothing is due this month
  When the owner opens the "Por pagar" screen
  Then the screen states that it lists charges that are due and not yet paid

Scenario: An empty Reportes screen teaches what it would show
  Given no movements exist
  When the owner opens the "Reportes" screen
  Then the screen states that it shows where the month's spending went
```

## AC-11 — With nothing of his own to quote, the panel explains with worked examples

```gherkin
Scenario: The panel still says what a fondo is when the screen holds nothing
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that a fondo keeps what is left over each month

Scenario: The panel still says what a presupuesto is when the screen holds nothing
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that a presupuesto is a ceiling that does not keep what is left over

Scenario: The panel works an example with figures and says they are an example
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel shows at least 1 figure
  And the panel says in words that its figures are an example
```

## AC-12 — A shape that must carry money forward is never offered as a presupuesto

```gherkin
Scenario: Exactly two rules are offered for a presupuesto
  Given an expense category "Servicios"
  When the owner starts creating a presupuesto
  Then 2 rules are offered

Scenario: The rule that reads recurring charges is not offered for a presupuesto
  Given an expense category "Servicios"
  When the owner starts creating a presupuesto
  Then the rule that reads recurring charges is not offered

Scenario: Every rule offered to a presupuesto is one it can use
  Given an expense category "Servicios"
  When the owner starts creating a presupuesto
  Then every rule offered is one a presupuesto can use

Scenario: The rule that must carry money forward is offered for a fondo
  Given an expense category "Servicios"
  When the owner starts creating a fondo
  Then the rule that reads recurring charges is offered

Scenario: Switching to a presupuesto leaves a rule a presupuesto can use
  Given an expense category "Servicios"
  When the owner starts creating a fondo
  And the owner chooses the rule that reads recurring charges
  And the owner switches to creating a presupuesto
  Then the rule that reads recurring charges is not chosen
  And a rule a presupuesto can use is chosen
```

## AC-13 — Everything created before the split keeps working, under the right heading

```gherkin
Scenario: A pre-split fund that does not carry money forward reads as a presupuesto
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a fund created before the split on "Restaurantes" that does not carry money forward, asking a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then "Restaurantes" appears under the presupuestos heading

Scenario: A pre-split fund that carries money forward reads as a fondo
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fund created before the split on "Tecnologia" that carries money forward, asking a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then "Tecnologia" appears under the fondos heading

@backend
Scenario: A pre-split fund asks and holds exactly what it did before
  Given today is 2026-09-15
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Tecnologia" 1 month ago
  Then the fund on "Tecnologia" asks 100000.00 COP this month
  And the fund on "Tecnologia" holds 40000.00 COP

Scenario: Nothing created before the split is asked about, and it still shows
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a fund created before the split on "Restaurantes" that does not carry money forward, asking a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then the row for "Restaurantes" states that it asks 100000.00 COP this month
  And nothing asks the owner to choose a shape for "Restaurantes"
```

## AC-14 — The panel is readable on a phone without scrolling sideways

```gherkin
@browser
Scenario: The panel wraps instead of running off a phone screen
  Given today is 2026-08-15
  And the screen is 390 pixels wide
  And an expense category "Mantenimiento del carro"
  And a fondo on "Mantenimiento del carro" that asks a fixed 1250000.00 COP each month, starting 2026-08
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  And an expense category "Servicios"
  And a fondo on "Servicios" saving 10000000.00 COP by 2027-02, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then no text in the panel is clipped
  And no part of the panel extends past 390 pixels
  And the page does not scroll sideways
```

## AC-15 — A category still holds exactly one of these, and the screen says so before the attempt

```gherkin
Scenario: A category that already holds one says so in the list, before it is chosen
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner starts creating a presupuesto
  And the owner looks at the categories offered
  Then "Tecnologia" is listed as already holding a fondo

Scenario: A category holding nothing can be chosen and used
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And no fondos and no presupuestos exist
  When the owner creates a presupuesto on "Restaurantes" asking a fixed 100000.00 COP each month, starting 2026-08
  Then "Restaurantes" appears under the presupuestos heading
```

## AC-16 — If the screen's figures cannot be loaded, the panel still opens and still explains

```gherkin
Scenario: The panel opens when the month's figures never arrive
  Given the month's figures cannot be loaded
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then a panel explains what the "Fondos y presupuestos" screen does

Scenario: The panel still says what both shapes are when the figures never arrive
  Given the month's figures cannot be loaded
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel states that a fondo keeps what is left over each month
  And the panel states that a presupuesto is a ceiling that does not keep what is left over

Scenario: A panel with no figures to quote shows worked examples, not blanks
  Given the month's figures cannot be loaded
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel shows at least 1 figure
  And the panel says in words that its figures are an example
  And no figure in the panel is blank
```

## AC-17 — A refusal is stated in the new vocabulary

```gherkin
Scenario: Refusing a second one on the same category uses the noun of the one already there
  Given today is 2026-08-15
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner tries to create a presupuesto on "Tecnologia"
  Then the refusal calls what is already there a fondo
  And the refusal names "Tecnologia"

Scenario: A presupuesto with no amount is refused in the words the screen uses
  Given an expense category "Restaurantes"
  When the owner tries to create a presupuesto on "Restaurantes" with no amount
  Then the refusal calls what is being made a presupuesto

Scenario: The refusal that the vanished checkbox existed for is gone
  Given an expense category "Mercado"
  When the owner starts creating a fondo
  And the owner chooses the rule that reads recurring charges
  Then nothing refuses it for not accumulating
```

## AC-18 — Nothing about what a fondo asks or holds changes

```gherkin
@backend
Scenario: A fund asks and holds what it asked and held before
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 100000.00 COP each month without accumulating, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Restaurantes" this month
  Then the fund on "Restaurantes" asks 100000.00 COP this month
  And the fund on "Restaurantes" holds 0.00 COP

@backend
Scenario: An accumulating fund carries its leftover money and a resetting one does not
  Given today is 2026-09-15
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 100000.00 COP each month without accumulating, starting 2026-08
  And an expense category "Tecnologia"
  And a fund on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Restaurantes" 1 month ago
  And a recorded expense of 60000.00 COP in category "Tecnologia" 1 month ago
  Then the fund on "Tecnologia" holds 40000.00 COP
  And the fund on "Restaurantes" holds 0.00 COP

@backend
Scenario: A fund that reads its recurring charges asks what it asked before
  Given today is 2026-08-15
  And an expense category "Servicios"
  And a recurring charge "Netflix" on "Servicios" of 600000.00 COP every year, next due 2027-02
  And a fund on "Servicios" that asks what its recurring charges need, starting 2026-08
  Then the fund on "Servicios" asks 100000.00 COP this month

@backend
Scenario: Whether a fund is behind is what it was before
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 100000.00 COP each month without accumulating, starting 2026-08
  And a recorded expense of 160000.00 COP in category "Restaurantes" this month
  Then the fund on "Restaurantes" is behind

@backend
Scenario: A fund inside its month is on track, as it was before
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 100000.00 COP each month without accumulating, starting 2026-08
  And a recorded expense of 60000.00 COP in category "Restaurantes" this month
  Then the fund on "Restaurantes" is on track

@backend
Scenario: The money available is what it was before
  Given today is 2026-08-15
  And an income of 3000000.00 COP is due this month
  And an expense category "Restaurantes"
  And a fund on "Restaurantes" that asks a fixed 100000.00 COP each month without accumulating, starting 2026-08
  Then the money available this month is 2900000.00 COP
```

## AC-19 — The panel can be opened, read and closed with the keyboard alone

```gherkin
Scenario: The panel opens without a mouse
  When the owner opens the "Fondos y presupuestos" screen
  And the owner reaches "¿Cómo funciona esto?" with the keyboard
  And the owner activates it with the keyboard
  Then a panel explains what the "Fondos y presupuestos" screen does

Scenario: The keyboard stays inside the panel while it is open
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  And the owner reaches "¿Cómo funciona esto?" with the keyboard
  And the owner activates it with the keyboard
  And the owner moves through the panel with the keyboard
  Then the keyboard never leaves the panel
  And the keyboard reaches the panel's close control

Scenario: Escape closes the panel and gives the reader back their place
  When the owner opens the "Fondos y presupuestos" screen
  And the owner reaches "¿Cómo funciona esto?" with the keyboard
  And the owner activates it with the keyboard
  And the owner presses Escape
  Then no panel is open
  And "¿Cómo funciona esto?" holds the keyboard's place again
```

## AC-20 — Every control that decides whether money accumulates is named out loud

```gherkin
Scenario: A screen reader hears which shape each way in makes
  When the owner opens the "Fondos y presupuestos" screen
  Then a screen reader hears the way into a presupuesto as making a presupuesto
  And a screen reader hears the way into a fondo as making a fondo

Scenario: A screen reader hears every rule by the job it does
  Given an expense category "Servicios"
  When the owner starts creating a fondo
  Then 4 rules are offered
  And a screen reader hears every rule offered by the job it does

Scenario: A screen reader hears the two ways in and nothing unnamed beside them
  When the owner opens the "Fondos y presupuestos" screen
  Then exactly 2 controls decide the shape
  And a screen reader hears both of them by name
```

## AC-21 — One vocabulary, everywhere

```gherkin
Scenario: A presupuesto's own row never calls it a fondo
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  Then the row for "Restaurantes" never calls it a fondo

Scenario: The panel uses the same two words the rows use
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  And an expense category "Tecnologia"
  And a fondo on "Tecnologia" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Fondos y presupuestos" screen
  And the owner opens "¿Cómo funciona esto?"
  Then the panel calls "Restaurantes" a presupuesto
  And the panel calls "Tecnologia" a fondo

Scenario: The empty screen uses the same two words
  Given no fondos and no presupuestos exist
  When the owner opens the "Fondos y presupuestos" screen
  Then the screen calls one shape a presupuesto
  And the screen calls the other shape a fondo

Scenario: The two ways in use the same two words
  When the owner opens the "Fondos y presupuestos" screen
  Then one way in names a presupuesto
  And the other way in names a fondo

Scenario: The Dashboard breakdown calls a presupuesto a presupuesto
  Given today is 2026-08-15
  And an income of 3000000.00 COP is due this month
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner opens the "Dashboard" screen
  Then the breakdown never calls "Restaurantes" a fondo

Scenario: The Reportes breakdown calls a presupuesto a presupuesto
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  And 60000.00 COP was spent on "Restaurantes" this month
  When the owner opens the "Reportes" screen
  Then the breakdown never calls "Restaurantes" a fondo

Scenario: Creating a presupuesto is confirmed as a presupuesto
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  When the owner creates a presupuesto on "Restaurantes" asking a fixed 100000.00 COP each month, starting 2026-08
  Then the confirmation calls what was created a presupuesto

Scenario: Deleting a presupuesto is asked about and confirmed as a presupuesto
  Given today is 2026-08-15
  And an expense category "Restaurantes"
  And a presupuesto on "Restaurantes" that asks a fixed 100000.00 COP each month, starting 2026-08
  When the owner asks to delete "Restaurantes"
  Then what is being deleted is called a presupuesto
  And the way to delete it is named as deleting a presupuesto

Scenario: Ajustes no longer speaks of a feature that was removed
  When the owner opens the "Ajustes" screen
  Then nothing on the screen says "metas"

Scenario: The dead setting that used the word is gone from Categorías
  Given an expense category "Restaurantes"
  When the owner opens the "Categorías" screen
  And the owner starts editing "Restaurantes"
  Then nothing offers to exclude the category from a presupuesto

Scenario: The badge for the dead setting is gone from the category list
  Given an expense category "Restaurantes"
  When the owner opens the "Categorías" screen
  Then no category is marked as excluded from a presupuesto

Scenario: The setting that does work keeps working and keeps its name
  Given an expense category "Restaurantes"
  When the owner opens the "Categorías" screen
  And the owner starts editing "Restaurantes"
  Then the screen still offers to exclude the category from the totals
```

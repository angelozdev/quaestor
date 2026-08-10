---
name: Quaestor
description: A dense, restrained money instrument — the category standard executed at Linear and Stripe fidelity.
colors:
  ink: "oklch(0.96 0.003 265)"
  ink-muted: "oklch(0.68 0.008 265)"
  ink-faint: "oklch(0.55 0.008 265)"
  ground: "oklch(0.17 0.005 265)"
  surface: "oklch(0.205 0.005 265)"
  surface-raised: "oklch(0.235 0.006 265)"
  hairline: "oklch(1 0 0 / 0.08)"
  hairline-strong: "oklch(1 0 0 / 0.14)"
  mint: "oklch(0.78 0.12 165)"
  income: "oklch(0.78 0.13 158)"
  expense: "oklch(0.7 0.17 22)"
  ground-light: "oklch(0.995 0.001 265)"
  surface-light: "oklch(1 0 0)"
  ink-light: "oklch(0.21 0.01 265)"
  hairline-light: "oklch(0.9 0.004 265)"
  mint-light: "oklch(0.62 0.13 165)"
typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.02em"
    fontFeature: "'tnum' 1"
  headline:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0"
  figure:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    fontFeature: "'tnum' 1"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
spacing:
  hair: "2px"
  tight: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.mint}"
    textColor: "{colors.ground}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
    typography: "{typography.label}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "28px"
    typography: "{typography.label}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "28px"
  input-text:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  table-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "0 12px"
    height: "36px"
  nav-item-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 8px"
    height: "28px"
---

# Design System: Quaestor

## Direction contract

Recorded here rather than in an artifact comment: `CLAUDE.md` prohibits code
comments project-wide, and that instruction outranks the skill's default
placement.

**THESIS.** A money instrument, not a money dashboard. Every figure this app
shows is arithmetic the owner can follow to its terms, so the surface spends
itself on figures and on the rules between them — and refuses the arrangement
this category always ships: a wall of same-size cards, each with a tracked
uppercase eyebrow and one number inside it.

**OWN-WORLD.** One typeface (Inter, tabular figures on everywhere a
number appears), a near-neutral cool ramp with almost no chroma, 1px hairlines
doing all the dividing, flat surfaces at rest, and a single mint accent held
under 10% of any screen. Recognizable with all content removed by three things:
the hairline that separates a total from its terms, figures that never
jitter between rows, and section labels that are quiet sentence-case text rather
than tracked capitals.

**STORY.** The owner opens the app to learn whether he can spend. He reads the
month's available money first, then — without a click, a hover or a tab — the
terms it was computed from: what came in, what every fund and meta asks, what
nothing covers. He believes the figure because the sheet shows its work, and he
acts on the obligations sitting directly under it.

**FIRST VIEWPORT (Dashboard).** Month label, then the available figure at
display scale, then immediately its liquidation as a ruled list of terms ending
in a hairline and the total again. Under that, what is owed, with the overdue
items named and their action on the right at row scale. No card contains the
headline; no chart appears above the fold.

**FORM.** The category standard, played straight, at Linear + Stripe fidelity —
the standing exit taken by the owner on 2026-08-10 over two dealt directions
(seed key `0d04e567`, assigned index 4, "Extracto"). No staging was carried from
the roll: the canon supplies its own composition, and mixing a dealt staging
into it would be the smuggled quirk the exit exists to refuse.

## Overview

**Creative North Star: "The Instrument"**

An instrument is trusted because it is legible, consistent and unadorned: it
shows a reading, and next to the reading, the scale that produced it. Quaestor
is read at a desk on a Mac, by the one person who owns every figure in it, and
its job in the first three seconds is to answer *how much can I spend*. So the
system is built to make figures comparable and hierarchy obvious, and to spend
nothing on ornament.

Density is a requirement, not a taste: Transacciones must keep showing many rows
per screen, and the fund rows keep all three of their explanation lines visible.
Minimal here means **ranked**, never **hidden** — the owner explicitly refused
moving visible numbers behind a disclosure. Where this system removes something,
it removes decoration: gradients on text, the radial glow behind the headline,
the hover lift on cards, the staggered entrance on every block.

Confirmed rejections, stated by the owner: it must not look like a consumer bank
app (cards everywhere, gradients, decorative charts), it must not cost one extra
click to see a number that is visible today, and it must not trade dense tables
for air.

**Key Characteristics:**

- One typeface, tabular figures everywhere a number appears
- Hairlines instead of card walls; flat at rest
- Sentence-case quiet labels, never tracked capitals as page grammar
- A single accent under 10% of any screen
- Dark by default, light fully authored (ADR-0004)
- A 4px spacing grid, and 28/32/36px control heights

## Colors

A near-neutral cool ramp with almost no chroma, so the only saturated things on
screen are the three that carry meaning: the accent, money in, money out.

### Primary

- **Instrument Mint** (`{colors.mint}`): the one accent. It marks the primary
  action, the focus ring, and the active navigation item. Nothing decorative
  ever takes it.

### Tertiary

- **Ledger Green** (`{colors.income}`): money coming in, on the figure only.
- **Ledger Red** (`{colors.expense}`): what is wrong — an overdue date, a
  negative net, a refusal, a fund spent past what it had. On the figure or the
  word, never as a filled background. **Not** money going out: spending is the
  default case here, so tinting it would colour almost every figure on every
  screen and discriminate nothing.

### Neutral

- **Ground** (`{colors.ground}`): the page. Near-black, faintly cool.
- **Surface** (`{colors.surface}`): panels and the sidebar, one step up from
  ground. No shadow.
- **Surface Raised** (`{colors.surface-raised}`): popovers, dialogs, menus —
  the only surfaces that leave the page plane.
- **Ink** (`{colors.ink}`): figures and primary text.
- **Ink Muted** (`{colors.ink-muted}`): labels, secondary text, the explanation
  lines under a fund row.
- **Ink Faint** (`{colors.ink-faint}`): a value that is structurally zero or
  not applicable. Never used for anything a person must read.
- **Hairline** (`{colors.hairline}`): every divider and every control edge.
- **Hairline Strong** (`{colors.hairline-strong}`): the rule under a total, and
  a table's header rule.

### Named Rules

**The Ten Percent Rule.** The mint accent covers at most 10% of any screen.
Its rarity is what makes the primary action findable.

**The Meaning Rule.** Green, red and mint are the only chromatic colours, and
each has exactly one job: in, out, act. A colour used for emphasis, decoration,
category or variety is a bug.

**The No Fill Rule.** Money direction is said on the figure, never by filling
its row or cell. A red row means the row is broken, not that it is an expense.

**The Default Case Rule.** Colour marks the exception, never the norm. Money out
is the norm on every screen here, so it carries no colour; money in does. A
column where nine of ten figures share a colour has spent the colour on nothing.

## Typography

**Display / Body / Label Font:** Inter (with `ui-sans-serif, system-ui`)
**Figure Font:** Inter with `tnum` enabled

**Character:** One neutral grotesque doing every job, chosen for its numerals
rather than its personality: tabular figures lock every column to one width, so
`$ 0` and `$ 5.681.641` stack without a pixel of drift and comparing two rows
costs nothing. The pairing has no display face on purpose — a second, expressive
family is what makes a money app look like a brand exercise. Inter's slashed
zero (`zero`, or the `ss02` disambiguation set) is deliberately left off: it
reads as engineering, and this surface is finance.

### Hierarchy

- **Display** (600, 2.5rem, 1.05, -0.02em, tnum): the month's available
  figure, and nothing else on the page.
- **Headline** (600, 1.25rem, 1.3, -0.01em): a screen's title, a section that
  opens a new subject.
- **Title** (600, 0.9375rem, 1.4): a group heading inside a screen, a row's
  subject when it needs weight.
- **Body** (400, 0.875rem, 1.5): sentences. Measure 65–75ch.
- **Label** (500, 0.75rem, 1.4, no tracking): section labels, column heads,
  control text. Sentence case.
- **Figure** (500, 0.875rem, tnum): every amount, count and rate. Right
  aligned in any column of amounts.

### Named Rules

**The Tabular Rule.** Any element that can contain a number carries `tnum`. A
figure that shifts by a pixel between two rows is a defect, not a nuance.

**The Quiet Label Rule.** Section labels are sentence-case 12px medium in
muted ink. Tracked uppercase is not page grammar here; it survives in exactly
one place — a table's column heads — and nowhere else.

**The One Family Rule.** No second typeface is added for display, and no
monospace is loaded as a font dependency. Where code or a tool name must read
as machine text, the system `ui-monospace` stack is used.

## Layout

A single reading column, not a grid of tiles. The page is a vertical sequence of
sections separated by 32px and, where a subject genuinely changes, by a
hairline. Related rows sit 4–8px apart; a heading takes more space above it than
below it.

**One container, 1152px, for every screen.** Measure is then controlled by the
content that needs it — a term list caps at 32rem, prose at 65–75ch — never by a
per-screen container width. One rule in one place beats a list of wide routes
that drifts from the navigation it duplicates. Content is left-aligned to the
column; nothing centres except an empty state.

A form control never spans the container: a single-line field and its submit cap
at 28rem, so a text input is never 1100px of empty box.

Spacing runs on a 4px grid: `2 / 4 / 8 / 12 / 16 / 24 / 32`. Control heights are
fixed at four steps — 24px inside a compact container, 28px for row and panel
actions, 32px for header actions and inputs, 36px for a table row and the chat
send. Nothing else.

Responsive: the sidebar collapses to a top bar and a drawer under 768px. Tables
keep their columns and scroll horizontally inside their own container rather
than reflowing into stacked cards — the row is the unit of comparison and
breaking it up destroys the comparison. The page body never scrolls sideways.

## Elevation & Depth

**Flat.** Surfaces sit on the page plane and are told apart by one step of
tonal difference and a 1px hairline. There is no card shadow, and there is no
hover lift. Depth exists only where an element genuinely leaves the plane:
popovers, dialogs, menus and the help sheet.

### Shadow Vocabulary

- **Overlay** (`box-shadow: 0 16px 40px -12px oklch(0 0 0 / 0.55), 0 0 0 1px oklch(1 0 0 / 0.08)`):
  popovers, dropdowns, dialogs, the help sheet. Offset and blur, plus a hairline
  edge so it reads against a dark ground.

### Named Rules

**The Flat Surface Rule.** A panel is a tonal step plus a hairline. Reaching for
a shadow on a panel means the hierarchy failed and the shadow is covering for it.

**The No Halo Rule.** A glow with no offset is decoration. Emphasis comes from
size, weight and position — and the headline figure gets no background
treatment of any kind.

## Shapes

Corners are tight and consistent: 6px on controls and rows (`{rounded.md}`),
8px on panels and overlays (`{rounded.lg}`), 4px on the smallest chips
(`{rounded.sm}`). Nothing is pill-shaped except a status badge, and nothing is
square.

Borders are always exactly 1px. A thicker or coloured left border to signal
state is not part of this system; state is said by the figure's colour, a badge,
or the word itself.

## Components

### Buttons

- **Shape:** tight corners (6px), 1px edge where the variant has one.
- **Heights:** 24px `xs` inside a compact container · 28px `sm` for row and
  panel actions · 32px `default` for header actions · 36px `icon-lg` for the
  chat send, which matches its textarea.
- **Primary:** mint fill, ground-coloured text, 32px, used once per screen at
  most.
- **Outline:** transparent fill, hairline edge, ink text. The default for row
  actions (*Marcar pagado*, *Confirmar*, *Eliminar*, *Reintentar*).
- **Ghost:** no edge, muted ink, ink on hover. Navigation-adjacent and icon
  actions.
- **Hover / Focus:** background steps one tonal level; focus shows a 3px mint
  ring at 50% opacity outside a mint border. No transform, no lift.

### Chips

- **Style:** 4px corners, hairline edge, transparent fill, 12px label.
- **State:** selected takes the outline treatment; unselected is ghost with
  muted ink. A segmented control is two 24px chips inside a surface track.

### Cards / Containers

Used for panels, not as page structure. Surface background, 1px hairline, 8px
corners, 16px internal padding, no shadow. A page must never be a grid of
equal-size cards each holding one number; that arrangement is what this system
replaced.

### Inputs / Fields

- **Style:** transparent fill, 1px hairline edge, 6px corners, 32px tall.
- **Focus:** mint border plus a 3px mint ring at 50%.
- **Error:** red border and ring; the message names the problem and the recovery.
- **Optional fields** are marked *(opcional)*; the required ones are not marked,
  because nearly all of them are.

### Tables

The primary content form. 36px rows, 12px horizontal cell padding, a
hairline-strong rule under the column heads and a hairline between rows. Column
heads are the one place tracked uppercase survives, at 12px. Amount columns are
right aligned and tabular. Rows do not stripe and do not lift; hover steps the
row background one tonal level.

Explanation lines under a row's subject are 12px muted ink at 1.4, and they stay
visible. They are ranked below the subject by size and colour, never hidden
behind a disclosure.

### Navigation

The sidebar is a surface panel with 12px sentence-case group labels in faint
ink and 28px ghost items. The active item takes a surface-raised background and
ink text — not a mint fill, because the accent is spent on actions. On mobile it
becomes a 48px top bar with a drawer.

### The Liquidation (signature)

The block that makes a headline figure trustworthy, and the one composition this
system considers its own: a term list where each row is a label and a signed
amount, the terms in muted ink, then a hairline-strong rule, then the total
repeated in ink at title weight. It appears under the available money on the
Dashboard, under the net in Reportes, and anywhere else a number is a fold over
other numbers. It is never collapsed, never behind a tab, and never a chart.

## Do's and Don'ts

### Do:

- **Do** put `tnum` on every element that can hold a number, and right-align
  columns of amounts.
- **Do** separate subjects with a 1px hairline and 32px of space instead of
  wrapping each one in a card.
- **Do** show a total's terms next to it, as the Liquidation, with nothing to
  click.
- **Do** keep all three explanation lines on a fund row visible, ranked below
  the subject by size and colour.
- **Do** hold the mint accent to the primary action, the focus ring and the
  active nav item.
- **Do** keep table rows at 36px and let a wide table scroll inside its own
  container.
- **Do** write control text in sentence case, in the app's Spanish.

### Don't:

- **Don't** build a page as a grid of same-size cards each holding one figure.
- **Don't** use gradient text, a zero-offset glow, or a hover lift. All three
  existed in the previous system and were removed on purpose.
- **Don't** put a tracked uppercase eyebrow over every section. Column heads
  only.
- **Don't** hide a visible number behind a hover, a tooltip, a tab or an
  accordion.
- **Don't** fill a row or a cell with red or green to say direction; colour the
  figure.
- **Don't** add a second typeface, a display face, or a loaded monospace.
- **Don't** stagger an entrance animation across every block on the page.
- **Don't** abbreviate money. `$ 5.681.641`, never `5,7M`.

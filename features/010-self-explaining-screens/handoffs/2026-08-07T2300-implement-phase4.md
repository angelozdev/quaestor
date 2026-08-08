---
skill: implement
agent_id: implementer-phase4
feature: 010-self-explaining-screens
started: 2026-08-07T2100
ended: 2026-08-07T2300
checkpoint: 5
artifacts:
  - frontend/components/screen-help.tsx
  - frontend/components/screen-help.test.tsx
  - frontend/components/page-header.tsx
  - frontend/components/empty-state.tsx
  - frontend/components/data-table.tsx
  - frontend/app/(app)/page.tsx
  - frontend/app/(app)/page.test.tsx
  - frontend/app/(app)/funds/page.tsx
  - frontend/app/(app)/funds/page.test.tsx
  - frontend/app/(app)/transactions/page.tsx
  - frontend/app/(app)/transactions/page.test.tsx
  - frontend/app/(app)/recurring/page.tsx
  - frontend/app/(app)/recurring/page.test.tsx
  - frontend/app/(app)/to-pay/page.tsx
  - frontend/app/(app)/to-pay/page.test.tsx
  - frontend/app/(app)/categories/page.tsx
  - frontend/app/(app)/categories/page.test.tsx
  - frontend/app/(app)/category-groups/page.tsx
  - frontend/app/(app)/category-groups/page.test.tsx
  - frontend/app/(app)/tags/page.tsx
  - frontend/app/(app)/tags/page.test.tsx
  - frontend/app/(app)/accounts/page.tsx
  - frontend/app/(app)/accounts/page.test.tsx
  - frontend/app/(app)/reports/page.tsx
  - frontend/app/(app)/reports/page.test.tsx
exit_criteria:
  - criterion: Every untagged scenario in the spec is bound by a vitest test and green
    verified_by: tool
    met: true
    evidence: "`python3 acceptance/spec_coverage.py features/010-self-explaining-screens frontend` → `scenarios 115 / bound to tests 100 / @browser 2 / @backend 13 / unbound 0`. Phase 3 left `bound to tests 60 / unbound 38`; all 38 are bound and none moved the other way. The 38: AC-7 10, AC-8 6, AC-9 3, AC-10 9, AC-11 3, AC-16 3, AC-19 3, AC-21 1. THE SPEC GREW UNDER ME, WITH THE OWNER'S PERMISSION AND BY THE COORDINATOR'S HAND, NOT MINE: AC-9 gained `Clicking outside the panel closes it` and `Selecting text in the panel and releasing outside does not close it` — 113 scenarios became 115 and `unbound` went 0 → 2 → 0. Both are bound verbatim in `app/(app)/funds/page.test.tsx`, on the real Fondos screen, because both scenarios name it. NOTE ON THE BRIEF'S ARITHMETIC: the brief expected unbound to fall to 1, counting `The panel wraps instead of running off a phone screen` among the 38. It is `@browser`, so `spec_coverage.py` puts it in the exempt set and never counted it — the floor was always 0. The two `@browser` scenarios remain unbound-by-design and are the team lead's; they report having verified the 390px one."
  - criterion: The acceptance pipeline is green and now exits 0
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh > /tmp/acc.out 2>&1; echo $?` → **`ACC_EXIT=0`**, `361 passed, 1 warning in 17.14s`. This is the first time the runner has exited 0 for this feature: phases 1–3 all exited 1 on `spec-coverage failed: a scenario has no test`, and that reason is gone. No backend file was touched, so 003's 348 regression scenarios plus 010's 13 are the same run phases 1–3 recorded."
  - criterion: The backend unit suite is untouched and green
    verified_by: tool
    met: true
    evidence: "`cd backend && SESSION_SECRET=$(python3 -c \"print('x'*64)\") uv run pytest -q` → `992 passed, 1 warning in 34.67s`, identical to the phase 3 baseline. `git status --short backend` prints nothing."
  - criterion: The frontend suite is green and grew
    verified_by: tool
    met: true
    evidence: "`cd frontend && pnpm vitest run` → `Test Files 53 passed (53)` / `Tests 358 passed (358)`, exit 0. Baseline was `48 passed (48)` / `310 passed (310)`. Five new files — `components/screen-help.test.tsx` (7), `app/(app)/recurring/page.test.tsx` (3), `app/(app)/to-pay/page.test.tsx` (2), `app/(app)/category-groups/page.test.tsx` (2), `app/(app)/tags/page.test.tsx` (2) = 16. Six grown — funds 55→75 (+20), dashboard 4→8 (+4), transactions 9→11 (+2), categories 3→5 (+2), accounts 2→4 (+2), reports 1→3 (+2) = +32. 310 + 16 + 32 = 358."
  - criterion: The panel closes on an outside press, without losing the reader's place or their selection
    verified_by: tool
    met: true
    evidence: "Added after the owner asked for it mid-task, and after he gave the coordinator permission to put it in `spec.md` — AC-9's two new scenarios are bound verbatim. HOW: `close()` is a `useCallback`, and the close control, Escape and the backdrop all call it, so focus return cannot diverge between them. Dismissal requires the press to BOTH begin and end on the backdrop, tracked in a ref, so selecting text in the panel and releasing outside keeps it open. The backdrop has NO role, NO tab stop and no handlers of its own: the listeners are on `document`, which is how Base UI — the library this app already depends on — does outside-press dismissal. That choice was forced by lint and is better for it: `a11y/noStaticElementInteractions` rejects a handler on a div, `role=\"presentation\"` does not satisfy it (tried, still red), and the only role that would is an interactive one the backdrop must not have. VERIFIED BY BREAKING, four ways: (1) delete the dismissal effect → **2 fail**, `Clicking outside the panel closes it` and the component's `stops listening for an outside press once it is closed`. (2) ignore where the press began — the naive `onClick` bug — → **1 fail**, exactly `Selecting text in the panel and releasing outside does not close it`. (3) let the backdrop call `setOpen(false)` instead of `close()` → **1 fail**, `Clicking outside the panel closes it`, which is the focus-return assertion catching a divergent close path. (4) strip the focus return from the shared `close` → **3 fail** together: the component's `gives the reader their place back however the panel is closed`, `Clicking outside the panel closes it` AND AC-19's `Escape closes the panel and gives the reader back their place` — one broken path failing every close at once, which is the whole point of routing them through one place. CONFIRMED IN THE REAL BROWSER at `http://localhost:3001/funds`: dispatching mousedown on the panel then mouseup on the backdrop left `[role=dialog]` present; mousedown+mouseup on the backdrop moved `document.activeElement` to `¿Cómo funciona esto?` and the next screenshot shows the panel gone."
  - criterion: Lint is clean across both halves
    verified_by: tool
    met: true
    evidence: "GREEN NOW, AND IT WAS REPORTED GREEN ONCE WHILE IT WAS RED — the correction matters more than the appearance, so both runs are recorded. FINAL RUN: `just lint` → `ruff check` `All checks passed!`; `ruff format --check` `212 files already formatted`; `pnpm biome check .` `Checked 185 files. Found 4 warnings. Found 1 info.` (the four pre-existing `noExplicitAny` in `lib/filter-schemas.ts` and `lib/use-url-filters.ts`, plus a deprecation notice on `biome.json`'s `recommended` field — none of them mine); `pnpm tsc --noEmit` → **`JUST_LINT_EXIT=0`**. Separately, `cd frontend && pnpm tsc --noEmit; echo $?` → **`TSC_EXIT=0`**. THE FALSE REPORT: the DRY pass described in findings (7) landed AFTER the first version of this criterion was written, and it left `HELP_LABEL` used but not imported in ten test files. The coordinator ran the gate in that window and got biome format-red on `funds/page.tsx` plus **18 `TS2304: Cannot find name 'HELP_LABEL'`**. The criterion as first written was therefore false for the tree as it then stood, and is corrected here rather than quietly re-run. Nothing was weakened to recover it: the imports were added, the formatter was allowed to format, no rule was disabled and no assertion was deleted."
  - criterion: The lint recipe's ordering is understood and reported rather than silently changed
    verified_by: judgment
    met: true
    evidence: "`justfile:82-87` runs four commands as four lines, and `just` stops at the first non-zero exit. `pnpm biome check .` is line 86 and `pnpm tsc --noEmit` is line 87, so **whenever biome is red the typecheck does not run at all**. That is how a codebase that did not typecheck could sit behind a gate everyone reads as one signal — and vitest never typechecks either, so 355 passing tests said nothing about it. MY READ, ASKED FOR AND NOT ACTED ON: the recipe should run BOTH and report BOTH, because the two answer different questions and a formatting nit should not be able to hide a type error. The cheap form is `set -e`-free sequencing that records each exit code and fails at the end — four lines of shell in the recipe, no new tooling. I did NOT make the change: `justfile` is shared tooling used by every feature and by CI, ADR-0040 is the decision that put lint where it is, and changing how the project's gate reports is an architecturally-significant decision that wants an ADR and the owner, not a phase-4 implementer's side effect."
  - criterion: The tests genuinely assert, rather than being vacuously green
    verified_by: tool
    met: true
    evidence: "Six deliberate breakages, each reverted immediately afterwards, counted against the full 353/355-test run unless noted. (1) THE AUTO-OPEN GUARD — `useState(false)` → `useState(true)` in `ScreenHelp`: `17 failed | 336 passed`, across 9 files. (2) THE FOCUS RETURN — `trigger.current?.focus()` deleted from `close()`: `2 failed | 351 passed` — `gives the reader their place back however the panel is closed` and AC-19's `Escape closes the panel and gives the reader back their place`, and NOTHING ELSE, which is the right blast radius for that one line. (3) THE FOCUS TRAP — an early `return` before the Tab branch: `3 failed | 350 passed` — the two `ScreenHelp` trap tests and AC-19's `The keyboard stays inside the panel while it is open`. (4) FONDOS' DATA QUOTING — the live branch of `FundsHelp` forced to the worked example: `4 failed | 67 passed (71)` in the funds file — AC-8's three and AC-21's `The panel uses the same two words the rows use`. THIS ONE CAUGHT A WEAK TEST AND IT WAS FIXED: on the first attempt only 3 failed, because `The panel names what is on the screen` was satisfied by the worked example, which also says \"Restaurantes\". It now asserts the name inside the `Lo que tienes en esta pantalla` list AND that the panel does not say `son un ejemplo`, and re-running the same breakage failed 4. (5) THE DASHBOARD'S DATA QUOTING — same treatment: `2 failed | 6 passed (8)`, AC-8's two Dashboard scenarios. (6) THE EMPTY SECTION'S TEACHING LINE — the `nothingYet` paragraph replaced with `null`: `2 failed | 71 passed (73)`, the two new AC-2 tests. Also, as a check on the header slot rather than on one screen: deleting `{help}` from `PageHeader` → `28 failed | 327 passed`, across all 10 screens."
  - criterion: The panel sits outside QueryBoundary and opens when the figures never arrive
    verified_by: tool
    met: true
    evidence: "AC-16's three scenarios are bound in `app/(app)/funds/page.test.tsx` with `moneyAvailable.mockRejectedValue(new Error(\"boom\"))`, and each waits for `No se pudieron cargar los fondos y presupuestos` — the `ErrorState` the boundary renders — BEFORE opening the panel, so the test only passes if the trigger and the panel live outside the boundary that is currently showing the error. `<ScreenHelp>` is passed to `PageHeader`'s `help` slot, which is rendered above `<QueryBoundary>` in every one of the ten pages. It reads `view.data?.funds`, which is `undefined` on failure, and falls to the worked example."
  - criterion: No backend change, no schema change, no migration
    verified_by: tool
    met: true
    evidence: "`git status --short` → 19 modified and 6 new files, every one under `frontend/`. Nothing under `backend/`, nothing under `backend/src/quaestor/migrations/`. CHARTER §7's data gate does not apply. (`docker-compose.yml` also shows modified — `${QUAESTOR_WEB_PORT:-3000}` — but that is the sandbox's own port override and predates this checkpoint; it is not mine and I left it.)"
  - criterion: The spec was not modified by me
    verified_by: tool
    met: true
    evidence: "`git status --short features/010-self-explaining-screens/spec.md` prints nothing from my side — I never opened it for writing. It DID change during this checkpoint: the owner gave explicit permission and the COORDINATOR amended it, adding AC-9's two outside-press scenarios, and told me what to bind. That is the rule working as intended rather than an exception to it. Nothing under `.build/generated/` was hand-edited; the runner regenerated it."
  - criterion: Structure and shared vocabulary are written once; only the sentences differ per screen
    verified_by: tool
    met: true
    evidence: "WHAT WAS EXTRACTED, after the owner's standing DRY instruction arrived mid-task. (a) `lib/funds.ts` gained `whatItIs(shape)` and `shapeSentence(shape)` — the two-shape explanation was being made in THREE places with three different wordings (the empty screen, the empty heading, the panel). One clause now, three sites building on it, plus a local `ShapeIs` in `funds/page.tsx` that picks the noun out in bold and is used six times. (b) `screen-help.tsx` gained `HelpSection` (a lead sentence plus the list it backs) and `HelpExample` (the same shape with the fixed `Las cifras de abajo son de un ejemplo, no tuyas.`). That sentence was written THREE times across Fondos, Dashboard and Recurrentes, once in the singular by accident; it is written once now and `HelpList` stopped being exported so nobody can rebuild the shape by hand. Six `<p>…</p><HelpList>` pairs collapsed into six `HelpSection`s. (c) `tests/factories.tsx` gained `openHelpPanel(screenName, user?)` — ten test files were each declaring `const HELP = \"¿Cómo funciona esto?\"` and three were each writing their own three-line `openHelp`. The constant is now imported from `screen-help.tsx` where the component defines it, so the label has ONE definition shared by the component and every test. (d) `transactions/page.tsx`'s panel now opens with the same `WHAT_A_MOVEMENT_IS` node its empty state uses, instead of restating it. WHAT WAS DELIBERATELY LEFT PER-SCREEN: the sentences. Plan §C rejects a route-keyed registry and AC-8 requires the panel to quote figures only that screen has loaded, so each page still writes its own copy and its own `…Help` component. That is cohesion, not duplication — no two screens say the same sentence. VERIFIED, not asserted: inverting `whatItIs` fails **8 tests in 6 describes**, which is the blast radius a single source of truth should have; blanking `AN_EXAMPLE` fails exactly the **2** scenarios that require the panel to say its figures are an example. `grep -rn 'accumulates ?' app/ components/` → none, so nothing re-derives the two nouns outside `lib/funds.ts`, and no page copies the panel's open/close/focus wiring."
  - criterion: No code comments; docstrings only
    verified_by: tool
    met: true
    evidence: "`git diff -- frontend | grep -E '^\\+' | grep -E '^\\+\\s*//|\\{/\\*'` → `no code comments added`. Docstrings are on `ScreenHelp`, `HelpList`, `PageHeader`, `focusablesIn`, `whyItAsks`, `panelLine`, `FundsHelp`, `DashboardHelp`, `RecurringHelp` and the test helper `figuresIn`."
  - criterion: AC-14's @browser scenario verified at 390px with recorded evidence
    verified_by: tool
    met: true
    evidence: "VERIFIED BY THE TEAM LEAD, 2026-08-07, per ADR-0045's evidence rule. URL http://localhost:3001/funds with the sandbox holding one presupuesto (Transporte) and two fondos (Mercado, Restaurantes). VIEWPORT: a real 390 CSS px — `resize_window` to 390 was refused by macOS, which clamps Chrome at innerWidth 547, so the page was loaded in a 390px-wide same-origin iframe, whose layout engine, CSS and media queries are the browser's own. Confirmed before measuring: `iframeInnerWidth 390`, `matchMedia('(max-width: 640px)').matches true`. OBSERVED with the panel open: panel rect left 0, right 375, width 375, height 844 — a full-height sheet; elements extending past 390px: 0 (every descendant measured); leaf nodes whose scrollWidth exceeds clientWidth, i.e. clipped text: 0; documentElement.scrollWidth 375 against innerWidth 390, so no sideways scrolling. Panel content was the live Fondos copy quoting real figures, not a fallback."
  - criterion: AC-7's @browser scenario verified across the ten screens
    verified_by: tool
    met: true
    evidence: "VERIFIED BY THE TEAM LEAD, 2026-08-07. All ten screens loaded in turn at 1280px and the trigger measured on each. FOUND ON 10/10. Size and typography IDENTICAL on every screen: 167x30 at 12px. Vertical position within 2px (top 32, 33 or 34) — sub-pixel rounding. Horizontal position takes exactly two values, 1237 and 1244, and the split is fully explained rather than left as variance: right=1237 on precisely the four screens that report `scrollbar: 15` because their content is taller than the viewport (Dashboard, Transacciones, Categorias, Reportes), and right=1244 on the six that report `scrollbar: 0`. The browser's scrollbar narrows the viewport, and a centred max-width column shifts by half of it. The app places the control identically on all ten; the difference is the scrollbar, not the layout. Separately verified with real mouse input on /funds: pressing the backdrop dismissed the panel AND returned focus to the trigger (document.activeElement was the ¿Cómo funciona esto? button), while a press begun inside the panel and released outside selected text and left the panel OPEN."
findings_summary: "Plan phase 4 is done: all 38 remaining scenarios are bound and green, `unbound` is 0, and `./run-acceptance-tests.sh` exits 0 for the first time in this feature. SIX THINGS WORTH THE OWNER'S ATTENTION, ALL NAMED RATHER THAN QUIETLY APPLIED. (1) THE DASHBOARD HAD NO PAGE HEADER AND NOW HAS ONE. AC-7 says the control goes in the page header on all ten screens; nine had a `PageHeader` and the Dashboard did not — it opened straight into the hero. It now opens with `Dashboard` as an h1 and the control beside it. That is a visible design change to the screen the owner sees most, made because the alternative was putting the control somewhere different on one screen out of ten, which is exactly what AC-7's `@browser` scenario forbids. (2) THE CONTROL SITS LAST, FLUSH RIGHT — A DESIGN CHOICE, NOT AN ACCIDENT. It is to the RIGHT of the screen's primary action, so `+ Nuevo fondo` is no longer the right-most thing on the Fondos screen. Reason: AC-7's `@browser` scenario asks for the same POSITION on every screen, and the right edge of the content column is the only anchor whose x does not move with the width of that screen's own buttons. If the owner would rather the primary action stayed flush right, swapping the two lines in `page-header.tsx` does it and costs one scenario's strictness. (3) THE PANEL IS HAND-ROLLED, NOT THE SHARED `Dialog`. `ui/components/dialog.tsx` wraps Base UI, which brings its own focus trap and Escape handling — but user-event's `tab()` moves focus itself unless a keydown handler prevents it, so a trap implemented through `inert`/`aria-hidden` is invisible to the test and AC-19's `the keyboard never leaves the panel` would have been vacuously green. `ScreenHelp` therefore handles Tab itself: it collects the panel's focusables, preventDefaults, and moves focus by one with wraparound. Breakage (3) in the exit criteria proves the test bites. The cost is ~60 lines of mechanics this app now owns twice; whether they should be folded back into `ui/` is a refine question. (4) A HEADER REGRESSION I CAUSED AND FIXED, FOUND IN THE BROWSER AND NOT IN A TEST. My first `PageHeader` added `min-w-0` to the title block so a long title could shrink. On a narrow viewport that let `Fondos y presupuestos` shrink to a three-line column UNDERNEATH the month picker — the title and the controls visibly overlapped. jsdom and happy-dom have no layout engine, so all 355 tests stayed green through it; I only saw it because I opened the sandbox. Before my change the header did not overlap, it just ran off the right edge (the audit's D10). The header now STACKS below `sm`: title on its own row, controls wrapping under it. Neither the old nor the new behaviour is covered by a test — this is the class of defect ADR-0045 created the `@browser` stream for, and it is a live argument that the stream earns its keep. (5) ONE PHASE-3 TEST HAD TO BE LOOSENED, AND ONLY ONE. `names a shape in every way in it offers, and adds no third word` asserted that EVERY button on the empty Fondos screen matches /presupuesto|fondo/i. `¿Cómo funciona esto?` is a button and names neither, so the feature's own control broke it. It now excludes that one control by its exact label and keeps the loop over everything else, so a future unnamed button still fails it. No other existing assertion was weakened; the other 309 phase-1-to-3 tests are untouched. (6) THE EMPTY-SECTION CHANGE THE OWNER ASKED FOR DOES NOT FIGHT ANY SCENARIO — CHECKED, NOT ASSUMED. Both headings now always render, with a teaching line under an empty one. AC-2's `Both headings are shown with one shape under each` has one entry of each shape and is untouched. AC-10's three Fondos scenarios are all `Given no fondos and no presupuestos exist`, which takes the `QueryBoundary` empty branch and never reaches the sections at all, so the two paths do not meet. The two new teaching lines are longer strings than the two `says` lines they sit near, so `getByText` exact matching keeps telling them apart. Two new tests pin it and breakage (6) shows they bite. (7) THE DRY PASS, AND WHAT IT COST. The owner's standing don't-repeat-yourself instruction arrived mid-task and it was right to: I had written the two-shape explanation in three places with three wordings, the \"these figures are an example\" sentence three times (once accidentally in the singular), `const HELP = \"¿Cómo funciona esto?\"` in ten test files and three copies of a three-line `openHelp`. All of it is collapsed — see the dedicated exit criterion for exactly what moved where and what was deliberately left per-screen. THE COST, STATED: the pass left `HELP_LABEL` used but not imported across ten test files, and vitest does not typecheck, so 355 tests passed over a tree that did not compile. That is finding (8). (8) `just lint` STOPS AT THE FIRST FAILURE, SO BIOME BEING RED HIDES THE TYPECHECK ENTIRELY. `justfile:82-87` is four commands on four lines; `just` aborts at the first non-zero exit; `pnpm biome check .` is line 86 and `pnpm tsc --noEmit` is line 87. While biome was red the typecheck never ran at all — and neither vitest nor the acceptance pipeline typechecks, so nothing else would have caught it either. The coordinator found this by running the gate himself, which is the only reason it is in this handoff instead of in the next agent's lap. My read, since it was asked for: the recipe should run both and report both. I did NOT change it — `justfile` is shared with CI and every other feature, ADR-0040 is the decision that put lint where it is, and how the project's gate reports is an ADR-shaped decision for the owner, not a side effect of a phase-4 implementer's cleanup. (9) THE BACKDROP CLOSE, AND THE LINT RULE THAT IMPROVED IT. The owner asked for click-outside-to-close mid-task; the coordinator then got his permission and amended `spec.md` with two AC-9 scenarios, so it is contract now and not a nicety. My first implementation put `onMouseDown`/`onMouseUp` on the overlay container, and `a11y/noStaticElementInteractions` refused it: a div with handlers must carry a role, `role=\"presentation\"` does not satisfy the rule (I tried), and the only roles that do are interactive ones the backdrop must not have. The rule was right and the fix is better than what it rejected — the listeners moved to `document`, which is how Base UI, already a dependency of this app, does outside-press dismissal, and the backdrop stays genuinely inert: no role, no tab stop, `aria-hidden`. Breakage (4) in that criterion is the one worth reading: strip the focus return from the shared `close` and the backdrop test and the Escape test fail TOGETHER."
human_action_needed: yes
human_action_kind: review
recommended_next: "/engineer.refine, then verification (CP7/CP8 with a different agent_id). THREE THINGS FOR THE OWNER, IN ORDER OF HOW MUCH THEY CHANGE. (1) READ THE TEN PANELS. They are gathered in this handoff's body so you do not have to open ten files. Two are rich and quote your own figures — Fondos y presupuestos and Dashboard; eight are two sentences. If any of the eight is too thin or too thick, it is one string in one file. (2) THE DASHBOARD NOW HAS A TITLE. `just dev-local`, or the sandbox at :3001 — it is the first thing you will see. (3) THE PRIMARY ACTION IS NO LONGER FLUSH RIGHT, see findings (2). FOR THE TEAM LEAD: both `@browser` scenarios are still open and both are yours. AC-14 needs a REAL 390px viewport — Chrome's window resize is clamped by macOS at ~547, so use devtools device emulation or a headless viewport; my sanity look at 547 is recorded above and is not the verification. FOR REFINE, NOT FOR HERE: `funds/page.tsx` grew from 293 to ~390 lines with the panel content in it, and `funds/create-form.tsx` is still 370; the per-screen help copy is co-located by design (plan §C rejects a registry) but the Fondos and Dashboard content could each be its own module beside its page. Also still open from phase 3: the two preview-query sharp edges, and the mutation sweep on `services/funds.py`, which verification owns and which no phase has run."
tracker_update: "local — 010 stays at checkpoint 5; plan phases 1, 2, 3 and 4 all complete. Backend acceptance 361 (unchanged, no backend file touched) and the runner now EXITS 0; backend unit 992 (unchanged); vitest 53 files / 358 tests (was 48 / 310); `just lint` exit 0 and `tsc --noEmit` exit 0, both re-verified after the DRY pass and the backdrop change. spec-coverage: 115 scenarios, 100 bound, 0 unbound, 2 @browser and 13 @backend exempt — spec.md grew by AC-9's two outside-press scenarios, amended by the coordinator on the owner's permission. The mutation sweep on services/funds.py is the only work item left before verification; the team lead reports both @browser scenarios verified."
status: complete
---

# implement — resumen del handoff

**Checkpoint 5, fase 4 del plan: el panel y las pantallas vacías.** Los **38**
escenarios que quedaban sin ligar están ligados y en verde. `unbound` es **0** y
`./run-acceptance-tests.sh` **sale 0 por primera vez** en este feature.

## Un componente sabe abrir y cerrar; ninguno sabe de qué habla

`frontend/components/screen-help.tsx`, ~135 líneas. Tiene el botón, la hoja, el
foco y nada más: **pinta lo que la pantalla le entregue y no sabe el nombre de
ninguna**. Cada pantalla escribe su propio contenido y se lo pasa a
`PageHeader` por una ranura nueva, `help`, al lado de `action`.

**El panel está FUERA del `QueryBoundary`**, que es lo que pide el AC-16: si las
cifras del mes no llegan, el panel igual abre y igual explica. Los tres tests
del AC-16 rechazan la consulta a propósito y **esperan a ver el mensaje de error
en pantalla antes de abrir el panel**, así que sólo pasan si el panel vive
afuera.

**La trampa de foco es a mano, no la del `Dialog` compartido.** Base UI la
resuelve marcando lo de afuera como inerte, y `user-event` mueve el foco por su
cuenta salvo que un `keydown` lo impida — con la trampa de Base UI el test del
AC-19 habría pasado sin comprobar nada. `ScreenHelp` maneja `Tab` él mismo.

## El encabezado se apila en pantalla angosta — y eso salió de mirar, no de correr tests

Mi primera versión de `PageHeader` dejaba encoger el título. En angosto,
*Fondos y presupuestos* se encogió a tres líneas **debajo** del selector de mes:
el título y los botones se **encimaban**. Los 355 tests siguieron en verde —
jsdom y happy-dom no tienen motor de layout. Lo vi abriendo el sandbox.

Ahora el encabezado se **apila** debajo de `sm`: título en su fila, controles
envolviéndose abajo. Antes de mi cambio no se encimaba, simplemente se salía por
el borde derecho (el D10 de la auditoría). **Ninguno de los dos comportamientos
tiene test**, y eso es exactamente para lo que el ADR-0045 creó el flujo
`@browser`.

## La copia de las diez pantallas, en un solo lugar

### 1. Dashboard *(rica — cita tus cifras)*

> Esta pantalla resume el mes: lo que entra, lo que cada fondo y cada
> presupuesto pide, y lo que queda libre después de eso.
>
> Este mes entran **$ 3.000.000**.
>
> Cada uno pide:
> - Mercado (fondo) — pide $ 10.000.000
> - Restaurantes (fondo) — pide $ 89.000
> - Transporte (presupuesto) — pide $ 150.000
>
> Pide más de lo que entra este mes:
> - Mercado — pide $ 10.000.000 y este mes entran $ 3.000.000.

Sin cifras tuyas: *«Aquí no hay cifras tuyas todavía, así que las de abajo son
un ejemplo, no las tuyas.»* + un ejemplo trabajado.

### 2. Transacciones *(corta)*

> Aquí queda registrado cada movimiento: lo que entra, lo que sale y lo que pasa
> de una cuenta a otra. La categoría de cada uno es lo que alimenta los reportes
> y lo que un fondo o un presupuesto vigila.
>
> Los filtros de arriba se guardan en la dirección del navegador, así que la
> lista que estás viendo se puede volver a abrir tal cual.

### 3. Fondos y presupuestos *(rica — cita tus cifras)*

> Un **fondo** aparta plata cada mes y guarda lo que sobra. Un **presupuesto**
> es un tope: lo que no gastes no se guarda.
>
> Lo que tienes en esta pantalla:
> - Mercado es un fondo — pide $ 10.000.000 este mes porque es lo que falta,
>   repartido entre los meses que quedan. Lo que sobre pasa a septiembre.
> - Restaurantes es un fondo — pide $ 89.000 este mes porque es el promedio de
>   lo que gastaste antes. Lo que sobre pasa a septiembre.
> - Transporte es un presupuesto — pide $ 150.000 este mes porque ese es el tope
>   que pusiste. Lo que sobre no pasa a septiembre.

El *porqué* sale de la regla: `Yo pongo el tope` → «porque ese es el tope que
pusiste»; `monto fijo` de fondo → «porque ese es el monto que decidiste
apartar»; promedio → «porque es el promedio de lo que gastaste antes»;
suscripciones → «porque es lo que piden sus cobros registrados»; fecha → «porque
es lo que falta, repartido entre los meses que quedan».

Sin nada que citar (o si las cifras no llegan):

> Aquí no hay cifras tuyas todavía, así que las de abajo son un ejemplo, no las
> tuyas.
> - Por ejemplo: Restaurantes, un presupuesto de $ 100.000 al mes. Si gastas
>   $ 60.000, septiembre vuelve a empezar en $ 100.000 y los $ 40.000 que
>   sobraron no se guardan.
> - Por ejemplo: Tecnología, un fondo de $ 100.000 al mes. Si gastas $ 60.000,
>   septiembre abre con $ 140.000 porque los $ 40.000 que sobraron se quedan.

### 4. Recurrentes *(corta + cita lo que tienes)*

> Un cobro recurrente es uno que vuelve solo — cada mes, cada año o cada cuantos
> días le digas. Lo registras una vez y la app lo espera por ti en **Por pagar**.
>
> Los que tienes registrados:
> - Netflix — cobra $ 35.000 cada mes.

### 5. Por pagar *(corta)*

> Aquí aparecen los cobros que ya vencieron o vencen dentro del periodo y
> todavía no has pagado.
>
> Salen de dos sitios: los cobros recurrentes que registraste, y los pagos
> sueltos que planeas con **Planear pago**. Confirmas uno cuando lo pagas y lo
> omites cuando ese cobro no llegó.

### 6. Categorías *(corta)*

> Una categoría dice para qué fue un movimiento — mercado, arriendo, salario.
> Cada gasto y cada ingreso lleva una.
>
> Es la unidad con la que trabaja el resto de la app: los reportes reparten el
> mes por categoría, y un fondo o un presupuesto vigila exactamente una.

### 7. Grupos *(corta)*

> Un grupo junta categorías que van juntas — «Casa» puede reunir arriendo,
> servicios y mercado.
>
> Sirve para leer el mes de más lejos: los reportes suman por grupo además de
> por categoría, así que ves cuánto se fue en «Casa» sin sumar tres líneas a
> mano.

### 8. Etiquetas *(corta)*

> Una etiqueta marca movimientos que van juntos aunque estén en categorías
> distintas — un viaje, una reforma, un regalo.
>
> Un movimiento tiene una sola categoría, pero puede llevar varias etiquetas. En
> **Transacciones** puedes filtrar por una y ver todo lo que costó eso.

### 9. Cuentas *(corta)*

> Una cuenta es donde está la plata — el banco, la tarjeta de crédito, el
> efectivo, los ahorros.
>
> Cada movimiento sale de una cuenta o entra a una, y el saldo se mueve solo:
> aquí no se edita a mano. El saldo inicial se pone al crearla.

### 10. Reportes *(corta)*

> Este reporte muestra a dónde se fue el gasto del mes, repartido por categoría
> y por grupo.
>
> Debajo del reparto están el resultado del mes —ingresos contra gastos— y de
> dónde sale el disponible. Cambia el mes arriba a la derecha para leer
> cualquier otro.

## Las nueve pantallas vacías que ahora enseñan

| pantalla | frase | puerta |
|---|---|---|
| Recurrentes | «Un cobro recurrente es uno que **vuelve solo**…» | `Crear el primero` |
| Categorías | «Una categoría dice **para qué fue** un movimiento…» | `Crear la primera` |
| Cuentas | «Una cuenta es **donde está la plata**…» | `Crear la primera` |
| Grupos | «Un grupo **junta categorías que van juntas**…» | `Crear el primero` |
| Etiquetas | «Una etiqueta marca movimientos **aunque estén en categorías distintas**…» | `Crear la primera` |
| Transacciones | «Un movimiento es **plata que entra o que sale**…» | `Registrar el primero` |
| Dashboard | «Las cifras de esta pantalla **salen de los movimientos que registres**…» | `Registrar el primero` |
| Por pagar | «…cobros que ya **vencieron o vencen** y todavía **no has pagado**.» | — (el AC-10 no pide puerta) |
| Reportes | «Este reporte muestra **a dónde se fue el gasto del mes**…» | `Registrar un movimiento` |

`EmptyState` no cambió salvo por exportar su tipo `Action`; `data-table.tsx`
ganó `emptyDescription` y `emptyAction`, que es lo único que Transacciones
necesitaba porque su vacío pasa por ahí (plan §D).

## Los dos encabezados se muestran siempre

Con cero presupuestos, la sección PRESUPUESTOS **desaparecía entera** — en un
feature cuyo propósito es que esa palabra se encuentre. Ahora los dos títulos
están siempre, y debajo del vacío:

> Todavía no tienes presupuestos. Un presupuesto es un tope: lo que no gastes no
> se guarda.

> Todavía no tienes fondos. Un fondo aparta plata cada mes y guarda lo que sobra
> para el mes que viene.

**No choca con ningún escenario, y lo comprobé en vez de suponerlo.** El AC-2
(`Both headings are shown with one shape under each`) tiene una entrada de cada
forma, así que no lo toca. Los tres escenarios del AC-10 son `Given no fondos
and no presupuestos exist`: ahí manda la rama vacía del `QueryBoundary` y las
secciones **ni se pintan**. Los dos caminos no se cruzan.

## Un solo sitio dice qué es cada cosa

La instrucción de **no repetirse** llegó a mitad del trabajo y llegó con razón:
yo había escrito la explicación de las dos formas en **tres sitios con tres
redacciones**, la frase «esto es un ejemplo» **tres veces** (una en singular por
descuido), `const HELP = "¿Cómo funciona esto?"` en **diez** archivos de test y
**tres** copias de un `openHelp` de tres líneas.

| qué se repetía | dónde vive ahora | usos |
|---|---|---|
| qué hace cada forma | `lib/funds.ts` → `whatItIs` / `shapeSentence` | 6 |
| «las cifras son un ejemplo» | `screen-help.tsx` → `HelpExample` | 3 |
| párrafo + lista del panel | `screen-help.tsx` → `HelpSection` | 6 |
| abrir el panel en un test | `tests/factories.tsx` → `openHelpPanel` | 10 |
| la etiqueta del botón | `screen-help.tsx` → `HELP_LABEL` | 11 |

**Lo que se queda por pantalla, a propósito: las frases.** El plan §C rechaza un
registro por ruta y el AC-8 exige que el panel cite **las cifras que esa
pantalla ya cargó**. Que cada pantalla escriba su copia no es repetición, es
cohesión — no hay dos pantallas diciendo la misma frase.

Medido: invertir `whatItIs` rompe **8 tests en 6 grupos**; vaciar la frase del
ejemplo rompe **exactamente los 2** escenarios que la exigen.

## Cerrar tocando afuera

El dueño lo pidió, dio permiso, y el coordinador **metió dos escenarios al
`spec.md`** (yo no lo toqué). El botón, `Escape` y el fondo pasan **todos por el
mismo `close`**, así que el foco vuelve al disparador se cierre como se cierre.

Cierra sólo si el clic **empezó y terminó** en el fondo: seleccionar texto del
panel y soltar afuera **no** lo cierra, que es justo lo que un `onClick` ingenuo
hace mal. El fondo **no es un control**: sin rol, sin tabulación, `aria-hidden`
— los oyentes están en el `document`, igual que lo resuelve Base UI, que ya es
dependencia de esta app.

Esa última decisión **me la forzó el linter y quedó mejor**:
`noStaticElementInteractions` no acepta manejadores en un `div`, y
`role="presentation"` tampoco lo calla; el único rol que sirve es uno
interactivo que el fondo no debe tener.

## Dos defectos míos que el coordinador encontró corriendo la compuerta

1. **Reporté `just lint` en verde cuando estaba en rojo.** La pasada de DRY dejó
   `HELP_LABEL` usado y **sin importar** en diez archivos de test: biome en rojo
   por formato y **18 `TS2304`**. Corregido, y el criterio de salida lo dice con
   esas palabras en vez de disimularlo.
2. **`just lint` se para en el primer fallo**, y biome va **antes** que `tsc`
   (`justfile:86-87`). Con biome en rojo **el typecheck no corre**. Vitest
   tampoco tipa: por eso 355 tests pasaban sobre un árbol que no compilaba.
   **Mi lectura, que se me pidió:** la receta debería correr **las dos** y
   reportar **las dos**. **No la cambié** — el `justfile` es de todo el proyecto
   y de CI, el ADR-0040 es la decisión que puso ahí el lint, y cambiar cómo
   reporta la compuerta es una decisión de ADR y del dueño, no un efecto
   secundario de mi limpieza.

## Verificado rompiendo, no leyendo verde

| lo que rompí | falla |
|---|---|
| `useState(false)` → `useState(true)` (el panel se abre solo) | **17** en 9 archivos |
| borrar `trigger.current?.focus()` del cierre | **2**, y sólo esas 2 |
| cortar la rama de `Tab` (sin trampa de foco) | **3** |
| forzar el ejemplo en el panel de Fondos | **4** de 71 |
| forzar el ejemplo en el panel del Tablero | **2** de 8 |
| quitar la frase de la sección vacía | **2** de 73 |
| quitar `{help}` de `PageHeader` | **28** en las 10 pantallas |
| invertir `whatItIs` (la fuente única del vocabulario) | **8** en 6 grupos |
| vaciar la frase «es un ejemplo» | **2** |
| borrar el cierre por el fondo | **2** |
| ignorar dónde empezó el clic (el bug del `onClick` ingenuo) | **1**, justo el del arrastre |
| que el fondo cierre sin pasar por `close` | **1**, el del foco |
| quitarle el retorno de foco al `close` compartido | **3 juntos**: fondo, `Entendido` y `Escape` |

La cuarta **encontró un test flojo**: la primera vez fallaron 3, no 4, porque
`The panel names what is on the screen` se conformaba con que apareciera
«Restaurantes» — y el **ejemplo** también lo dice. Ahora exige el nombre dentro
de la lista *«Lo que tienes en esta pantalla»* **y** que el panel no diga «son un
ejemplo». Repetida la misma rotura, fallan 4.

## Lo que NO hice, dicho explícitamente

- **Los dos escenarios `@browser`.** Son del líder del equipo, que ya verificó
  el de 390 px. Mi mirada de cordura fue a **547 px reales, no 390** — macOS no
  deja encoger la ventana de Chrome más allá de eso — y **no era evidencia del
  AC-14**.
- **Nada del backend.** Ni un archivo bajo `backend/`. Sin migración.
- **El `spec.md` no lo toqué yo.** Creció durante este checkpoint: el dueño dio
  permiso y **el coordinador** le añadió los dos escenarios del cierre por
  fuera. Nada bajo `.build/generated/` se editó a mano.
- **El `justfile` no lo toqué**, aunque encontré el problema de orden. Ver
  arriba.
- **Sin registro central de contenido por ruta** — el plan §C lo rechaza y el
  AC-8 exige citar las cifras que **esa** pantalla ya cargó.
- **Sin refactor de fondo.** `create-form.tsx` sigue en 370 líneas; es de
  *refine*.
- **La barrida de mutación** sobre `services/funds.py` sigue sin correrse. Es de
  verificación y este checkpoint no tocó Python.

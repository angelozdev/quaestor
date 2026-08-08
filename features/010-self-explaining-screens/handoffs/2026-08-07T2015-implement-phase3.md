---
skill: implement
agent_id: implementer-phase3
feature: 010-self-explaining-screens
started: 2026-08-07T1810
ended: 2026-08-07T2015
checkpoint: 5
artifacts:
  - frontend/lib/funds.ts
  - frontend/lib/date.ts
  - frontend/lib/date.test.ts
  - frontend/lib/query.ts
  - frontend/components/empty-state.tsx
  - frontend/components/app-shell.tsx
  - frontend/components/app-shell.test.tsx
  - frontend/app/(app)/funds/page.tsx
  - frontend/app/(app)/funds/create-form.tsx
  - frontend/app/(app)/funds/rules.ts
  - frontend/app/(app)/funds/funds.schema.ts
  - frontend/app/(app)/funds/page.test.tsx
  - frontend/app/(app)/page.tsx
  - frontend/app/(app)/page.test.tsx
  - frontend/app/(app)/reports/page.tsx
  - frontend/app/(app)/reports/page.test.tsx
  - frontend/app/(app)/settings/page.tsx
  - frontend/app/(app)/settings/page.test.tsx
  - frontend/app/(app)/categories/page.tsx
  - frontend/app/(app)/categories/page.test.tsx
exit_criteria:
  - criterion: Every untagged scenario in plan phase 3's ACs is bound by a vitest test and green
    verified_by: tool
    met: false
    evidence: "60 of 61. Not marked true, because one scenario the brief assigned to this phase is not bound and cannot be. `python3 acceptance/spec_coverage.py features/010-self-explaining-screens frontend` → `scenarios 113 / bound to tests 60 / @browser 2 / @backend 13 / unbound 38`. Baseline before this checkpoint was `bound to tests 0 / unbound 98`, so 60 scenarios moved from unbound to bound and none moved the other way. The 38 that remain are ALL plan phase 4: AC-7 (10), AC-8 (6), AC-9 (3), AC-10's other nine screens (9), AC-11 (3), AC-16 (3), AC-19 (3) — and ONE that the brief assigned to phase 3 but cannot be built without the panel, named in findings: `The panel uses the same two words the rows use` (AC-21). The arithmetic of the 60: AC-1 2, AC-2 3, AC-3 4 untagged, AC-4 4, AC-5 9, AC-6 8, AC-12 5, AC-13 3 untagged, AC-15 2, AC-17 3, AC-20 3, AC-21 11 of 12 — that is 57 — plus AC-10's three Fondos scenarios, which the brief assigned to this phase."
  - criterion: The acceptance pipeline still reports 361 and the unbound count has fallen
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh` → `collected 361 items` / `361 passed, 1 warning in 16.82s`. Exit code is still 1 and the printed reason is still the expected one: `spec-coverage failed: a scenario has no test — see the UNBOUND list above`, now with `unbound 38` instead of the 98 phase 1/2 left behind. No backend file was touched at all, so the 348 regression scenarios plus 010's 13 are byte-for-byte the same run as the phase 1/2 handoff recorded."
  - criterion: The backend unit suite is untouched and green
    verified_by: tool
    met: true
    evidence: "`cd backend && SESSION_SECRET=$(python3 -c \"print('x'*64)\") uv run pytest -q` → `992 passed, 1 warning in 32.39s`, identical to the phase 1/2 baseline. `git status --short` lists zero files under `backend/`."
  - criterion: The frontend suite is green and grew
    verified_by: tool
    met: true
    evidence: "`cd frontend && pnpm vitest run` → `Test Files 48 passed (48)` / `Tests 310 passed (310)`, exit 0. Baseline was `44 passed (44)` / `253 passed (253)`. Four new test files (`components/app-shell.test.tsx`, `app/(app)/categories/page.test.tsx`, `app/(app)/reports/page.test.tsx`, `app/(app)/settings/page.test.tsx`); `app/(app)/funds/page.test.tsx` went from 10 tests to 55. Arithmetic: 253 − 10 + 55 + 4 (date) + 1 (dashboard) + 1 (empty-state) + 1 + 3 + 1 + 1 = 310. It was 307 at the first pass of this checkpoint; the addendum's empty-screen change added 3."
  - criterion: Lint is clean across both halves
    verified_by: tool
    met: true
    evidence: "`just lint` → exit 0 (captured with `just lint > /tmp/lint.out 2>&1; echo $?` → `EXIT=0`). `ruff check` → `All checks passed!`; `ruff format --check` → `212 files already formatted`; `pnpm biome check .` → `Checked 179 files. Found 4 warnings. Found 1 info.` — the same four pre-existing `noExplicitAny` warnings in `lib/use-url-filters.ts` and `lib/api/types.ts` that the phase 1/2 handoff recorded, none in a file this checkpoint changed; `pnpm tsc --noEmit` → exit 0."
  - criterion: The tests genuinely assert, rather than being vacuously green
    verified_by: tool
    met: true
    evidence: "Three deliberate breakages, each reverted immediately afterwards. (1) `shapeOf` inverted (`accumulates ? \"presupuesto\" : \"fondo\"`) → `19 failed | 34 passed (53)`. (2) `keptLine`'s fondo branch stripped to `Gastaste ${spent}` and `nextMonthLine`'s figure removed → `2 failed | 51 passed`. (3) `ruleConsequence` forced to return the worked example always, never the live figure → `4 failed | 49 passed`. After restoring each, `53 passed (53)`."
  - criterion: No backend behaviour change, no schema change, no migration
    verified_by: tool
    met: true
    evidence: "`git status --short` → 13 modified and 7 new files, every one under `frontend/`. Nothing under `backend/`, nothing under `backend/src/quaestor/migrations/`. CHARTER §7's data gate does not apply."
  - criterion: Nothing stored is lost by removing the dead category checkbox
    verified_by: tool
    met: true
    evidence: "`exclude_from_budget` is optional on both `CategoryCreate` and `CategoryUpdate` (`frontend/lib/api/types.ts:350,357`) and `services/categories.py:272` updates it only `if exclude_from_budget is not None`. `toBody` in `categories/page.tsx` now omits the key entirely, so a PATCH leaves the stored column exactly as it was. The column, the SQLModel field, the REST schema and the MCP tool are all untouched — `grep -rn exclude_from_budget backend/` is unchanged from before this checkpoint."
  - criterion: The two nouns are derived, never stored
    verified_by: judgment
    met: true
    evidence: "`frontend/lib/funds.ts` is 24 lines and holds the only derivation: `shapeOf({accumulates})`, its inverse `accumulatesAs(shape)` for the create path, and `nounOf(shape)` for a label. Every screen that names a shape imports it — the funds page, the create form, the Dashboard and Reportes. No field named `shape` is stored, sent or read; `FundCreate.accumulates` is filled from the entry point that was used and nothing else. Product ADR-037's one record shape stands."
  - criterion: No code comments; docstrings only
    verified_by: tool
    met: true
    evidence: "`grep -n '^\\s*//\\|{/\\*'` over every file this checkpoint created or changed returns nothing. The one comment-shaped edit is a DELETION: the stale `{/* Fondos */}` JSX comment in `reports/page.tsx`, which after the section rename disagreed with the title one line below it. Docstrings are on `shapeOf`/`accumulatesAs`/`nounOf`, `nextYearMonth`/`monthNameOf`, `rulesFor`/`ruleLabel`/`ruleConsequence`, `previewBody`, `keptLine`/`nextMonthLine` and `EmptyState`."
  - criterion: The owner's empty-screen decision is delivered, and AC-4 stopped disagreeing with AC-10
    verified_by: tool
    met: true
    evidence: "Added after `04d58a2`, on the owner's decision — see the dated addendum in the body. The empty Fondos screen now offers `Crear mi primer presupuesto` and `Crear mi primer fondo` instead of `Crear el primero`. Measured with a temporary probe, since removed: the EMPTY screen's buttons are `['+ Nuevo presupuesto', '+ Nuevo fondo', 'Crear mi primer presupuesto', 'Crear mi primer fondo']` and the POPULATED screen's are `['+ Nuevo presupuesto', '+ Nuevo fondo', 'Eliminar']`. AC-4's `the screen offers no way in that does not name a shape` was FALSE on the empty screen before this change and is now TRUE on both — findings (2)'s tension is gone. AC-20's `exactly 2 controls decide the shape` is 2 on the populated screen and 4 on the empty one, so it holds under the 'two decisions' reading and not under a literal control count; the empty screen now REPEATS the pair rather than contradicting it, and AC-20's scenario has no Given so its test runs on the populated screen unchanged. `EmptyState.action` widened to `Action | Action[]`, all 11 existing call sites untouched. Verified non-vacuous by rendering only the first action → `2 failed | 57 passed (59)`, restored → `59 passed (59)`."
  - criterion: AC-14 and AC-7's @browser scenarios verified with Chrome MCP
    verified_by: tool
    met: false
    evidence: "NOT DONE, and not in scope. Both `@browser` scenarios (`The control sits in the same place on every screen`, `The panel wraps instead of running off a phone screen`) are about the `¿Cómo funciona esto?` panel, which plan phase 4 builds. There is nothing to observe yet. The plan's Collaboration schedule puts the 390px observation at phase 4 and ADR-0045's evidence rule applies there, not here."
findings_summary: "Plan phase 3 is done and green: 60 of the 98 unbound scenarios are now bound and passing, and the two nouns exist everywhere the brief said they must. FOUR THINGS THE BRIEF DID NOT ANTICIPATE, ALL DECIDED AND NAMED RATHER THAN QUIETLY APPLIED. (1) ONE AC-21 SCENARIO CANNOT BE BUILT IN THIS PHASE. The brief lists AC-21 as mine and its expected end state says every untagged AC-21 scenario is bound. But AC-21's second scenario is `The panel uses the same two words the rows use`, whose When is `the owner opens \"¿Cómo funciona esto?\"` — the panel the brief explicitly forbids me to build. It is left unbound and belongs to phase 4 with the rest of the panel. That is 11 of AC-21's 12, not 12. (2) SETTLED BY THE OWNER AFTER `04d58a2` — SEE THE DATED ADDENDUM, WHICH SUPERSEDES THIS PARAGRAPH'S OUTCOME BUT NOT ITS FINDING. THE EMPTY SCREEN'S BUTTON AND AC-4/AC-20 ARE IN TENSION, AND THE SPEC ITSELF RESOLVES IT. AC-10's owner-approved copy ends with `[ Crear el primero ]`, a way in that does not name a shape; AC-4 says `the screen offers no way in that does not name a shape` and AC-20 says `exactly 2 controls decide the shape`. Every AC-4 and AC-20 scenario has NO Given at all, while all three AC-10 Fondos scenarios are `Given no fondos and no presupuestos exist`. So the ACs describe two different screens: AC-4/AC-20 the populated one, AC-10 the empty one. The tests are set up that way — AC-4's and AC-20's with an entry present, AC-10's with none — and `Crear el primero` opens the fondo form (the shape the empty-state paragraph leads with). RESOLVED: the owner replaced it with two buttons, one per shape — his reasoning and the measured effect on AC-4 and AC-20 are in the addendum. (3) THE RULE PICKER'S LIVE FIGURES COME FROM `POST /funds/preview`, NOT FROM ARITHMETIC ON THE SCREEN. AC-5 requires the subscription rule, the averaging rule and the dated rule each to state their real monthly figure for the chosen category. The screen never computes it: it previews, through the endpoint feature 003 already built for exactly this, with `useQueries` — one query per offered rule, `enabled` only once that rule has the figure it is made of. Two consequences worth naming. The `average` preview 400s for a category that never spent before the start month (`services/funds.py:580`), which is correct behaviour and lands the picker back on the worked example — but it is a failed request on a common path. And the dated rule re-previews per keystroke of the target amount, because the query key carries it. Both are cheap on a local single-user app and both are debounce/`select`-shaped work for refine. (4) THE ROW NEEDED THE FUND'S START MONTH, WHICH `FundStatus` DOES NOT CARRY. `Tiene $0 porque empezó este mes.` is a claim about the start month, and no combination of `asks`/`holds`/`spent`/`carries` distinguishes a first month from a month that spent its whole opening — a presupuesto holds 0 forever, so guessing would have printed the sentence every month of its life. The page therefore also reads `listFunds()`, which already returns `start_month`, and the note renders only when it equals the month on screen. The list is NOT gated behind the QueryBoundary: if it fails the note simply does not appear and nothing else on the screen moves. COPY: WRITTEN AS THE OWNER APPROVED IT, WITH TWO STATED DEVIATIONS. Every heading, entry point, rule label, worked example, row line, empty-state sentence and refusal is the owner's string verbatim. The two deviations are both about money formatting. Live figures render through `formatCents`, which is `$ 60.000` with a space — the owner wrote `$60.000`. Using two formats on one screen would have been worse than either, so computed figures follow the app and the literal examples keep the owner's exact characters, including `Tiene $0 porque empezó este mes.` where the zero is a constant and not a computed figure. The second: the averaging rule's line names its window (`Los últimos 3 meses…`, `El último mes…`) because the window is an editable field and the owner's copy hard-codes 3; the default is now 3, which is what makes the approved sentence the one he actually sees. TWO EXTRA VOCABULARY SITES, ONE FIXED AND ONE LEFT. Reportes' fund table was headed `Fondos` and now lists both shapes, so a presupuesto sat under a heading calling it a fondo — renamed to `Fondos y presupuestos`, the same decision the navigation made, one string. LEFT ALONE and named here: the Dashboard and Reportes both still say `Sin fondo que lo cubra` for spending nothing covers. It names no entry and no category, it was not in the brief's list, and rewording it is a judgement about a third sentence rather than about the two nouns."
human_action_needed: yes
human_action_kind: review
recommended_next: "Plan phase 4 — `ScreenHelp`, the header slot, ten screens' content and the remaining nine empty states — then /engineer.refine, then verification. PHASE 4 INHERITS ONE SETTLED PRECEDENT: the empty screen names both shapes in its ways in, and `EmptyState.action` already takes an array, so the other nine empty screens have the component they need. TWO THINGS STILL WANT THE OWNER (the third is now decided — see the addendum). (1) THE COPY IS NOW ON A SCREEN AND CAN BE READ IN PLACE. The plan's Collaboration schedule says the owner reviews phase 3's Spanish before phase 4 quotes it; it is all live now — two headings, two entry points, six rule labels with their consequence lines, three row lines and two refusals. Nothing about the app is running in a browser yet for this checkpoint (no @browser scenario applies to phase 3), so `just dev-local` plus the Fondos y presupuestos screen is the fastest read. (2) THE ROW'S `Regla` COLUMN NOW USES THE JOB LABELS. A presupuesto's fixed rule reads `Yo pongo el tope` and a fondo's reads `Aparto un monto fijo cada mes`, rather than `Monto fijo`. That is what keeps AC-21's `a presupuesto's own row never calls it a fondo` true and keeps one vocabulary between the picker and the list, but the labels are sentences in a narrow table column and the owner may want them shorter. FOR REFINE, NOT FOR PHASE 4: the two preview-query sharp edges in findings (3), and `funds/create-form.tsx` at 370 lines is the largest thing this checkpoint produced."
tracker_update: "local — 010 stays at checkpoint 5; plan phases 1, 2 and 3 complete, phase 4 not started. Backend acceptance 361 (unchanged, no backend file touched), backend unit 992 (unchanged), vitest 48 files / 310 tests (was 44 / 253), lint exit 0. spec-coverage: 60 bound, 38 unbound, down from 98. The runner still exits 1 and will until phase 4 lands. Mutation sweep on services/funds.py still not run — verification owns it, and this checkpoint changed no Python."
status: complete
---

# implement — resumen del handoff

**Checkpoint 5, fase 3 del plan: los dos sustantivos.** De 98 escenarios sin
ligar quedaron **38**, y las 38 son del panel y de las pantallas vacías que le
tocan a la fase 4.

## Un solo lugar decide cuál de los dos es

`frontend/lib/funds.ts`, 24 líneas. `accumulates == false` es un
**presupuesto**; `true` es un **fondo**. **No se guarda ningún campo nuevo** —
el registro sigue siendo uno solo, que es lo que decidió el ADR-037 de producto
y lo que el ADR-042 sostiene. Lo importan la pantalla de fondos, el formulario,
el Tablero y Reportes; nadie más deriva nada por su cuenta.

Y al revés: **la puerta por la que entraste decide si acumula**. La casilla
`Acumula lo que sobra cada mes` desapareció, y con ella el defecto D15 de la
auditoría — el control más importante del formulario ya no existe para tener
nombre o no tenerlo.

## Las seis combinaciones siguen siendo alcanzables

| Regla | Presupuesto | Fondo |
|---|---|---|
| Yo pongo el tope / Aparto un monto fijo | ✅ | ✅ |
| El tope sale de lo que ya gastabas / Aparto lo que suelo gastar | ✅ | ✅ |
| Pago mis suscripciones mes a mes | — | ✅ |
| Junto una cantidad para una fecha | — | ✅ |

Las dos que **tienen** que acumular no se ofrecen para un presupuesto, así que
ya no existe la combinación que la app aceptaba mostrar y después rechazaba. El
AC-6 tiene un escenario por cada casilla ✅ de esa tabla, y los seis crean de
verdad a través del formulario y comprueban bajo cuál de los dos títulos
aparece la entrada.

## Las cifras de las reglas salen del servidor, no de la pantalla

El AC-5 pide que cada regla diga su cifra real. La pantalla **no hace la
cuenta**: pregunta por `POST /funds/preview`, el endpoint que la 003 ya había
construido justo para eso, una consulta por regla ofrecida y sólo cuando esa
regla ya tiene el dato del que está hecha.

Dos bordes filosos, dichos en vez de escondidos:

- la regla del promedio **falla con 400** en una categoría que nunca gastó
  antes del mes de inicio (`services/funds.py:580`). Es el rechazo correcto, y
  la pantalla cae de vuelta en el ejemplo trabajado — pero es una petición
  fallida en un camino común;
- la regla con fecha vuelve a preguntar **en cada tecla** del objetivo, porque
  la llave de la consulta lo lleva.

Los dos son baratos en una app local de un solo usuario y los dos son trabajo
de *refine*, no de aquí.

## Lo que la fila del mes dice ahora

Un fondo: `Gastaste $ 60.000 · se guardan $ 40.000` y
`Septiembre tendrá $ 140.000 para gastar.`

Un presupuesto: `Gastaste $ 60.000 · los $ 40.000 que sobran no se guardan` y
`Septiembre vuelve a $ 100.000.`

Las tres cifras son las que la fase 1 puso en el camino (`spent`, `carries`,
`next_month_has`); la única aritmética que hace la pantalla es
`asks − spent` para lo que un presupuesto **no** guarda, y eso es derivable
justo porque la fase 1 mandó `spent`.

## Una frase necesitaba un dato que `FundStatus` no lleva

`Tiene $0 porque empezó este mes.` es una afirmación sobre el mes de inicio, y
**ninguna combinación** de `asks`/`holds`/`spent`/`carries` distingue un primer
mes de un mes que se gastó todo lo que tenía: un presupuesto tiene $0 **para
siempre**, así que adivinar habría impreso la frase todos los meses de su vida.

La pantalla lee entonces también `listFunds()`, que ya devolvía `start_month`.
No está dentro del `QueryBoundary`: si esa lista falla, la nota simplemente no
aparece y nada más se mueve.

## Los otros sitios del vocabulario

- **Tablero y Reportes**: `Fondo · X` pasó a `Presupuesto · X` cuando lo es.
- **Menú**: `Fondos` → `Fondos y presupuestos`.
- **Avisos, diálogo de borrar y el `aria-label` de la fila**: los tres dicen el
  sustantivo de lo que se está tocando.
- **Ajustes**: se fue la mención a *metas* (ADR-037 las quitó). Queda
  «Cuenta usada como origen de las transferencias planeadas», que es lo que
  `services/planned.py:242` efectivamente hace con ese ajuste.
- **Categorías**: se fue la casilla `Excluir del presupuesto` y su etiqueta
  `no-presup.`. **Sólo de la pantalla.** La columna, el campo del esquema, el
  REST y la herramienta MCP siguen intactos, y el `PATCH` ya no manda el campo,
  así que lo guardado queda exactamente como estaba. `Excluir de los totales`,
  que sí trabaja, no se tocó.
- **Reportes** tenía además una sección titulada `Fondos` que lista los dos.
  Pasó a `Fondos y presupuestos` — la misma decisión que tomó el menú.

## Lo que NO hice, dicho explícitamente

- **El panel `¿Cómo funciona esto?`**: ni una línea. Es la fase 4.
- **Las otras nueve pantallas vacías**: intactas. Sólo la de Fondos, que es la
  que piden los tres escenarios del AC-10 que me tocaban.
- **Un escenario del AC-21 que el brief me asignó**: `The panel uses the same
  two words the rows use` **necesita el panel**. Queda sin ligar y es de la
  fase 4. Son 11 de 12, no 12.
- **Nada del backend.** `git status` no lista un solo archivo bajo `backend/`.
  Sin migración, sin cambio de esquema, sin cambio de comportamiento.
- **Ningún escenario `@browser`.** Los dos son del panel; no hay nada que mirar
  todavía.
- **Sin refactor de fondo.** `create-form.tsx` quedó en 370 líneas y es lo más
  grande que salió de aquí; eso es de *refine*.
- **El spec no se tocó.**

## Dónde no seguí la copia al pie de la letra

Dos veces, y las dos son formato de plata:

1. Las cifras **calculadas** salen por `formatCents` (`$ 60.000`, con espacio);
   el dueño escribió `$60.000`. Dos formatos en una misma pantalla habrían sido
   peor que cualquiera de los dos, así que lo calculado sigue a la app y los
   ejemplos literales conservan sus caracteres exactos — incluido
   `Tiene $0 porque empezó este mes.`, donde el cero es una constante.
2. La regla del promedio **nombra su ventana** (`Los últimos 3 meses…`,
   `El último mes…`) porque la ventana es un campo editable y la copia fija 3.
   El valor por defecto ahora **es 3**, que es lo que hace que la frase
   aprobada sea la que se ve.

## Lo que quiero que mire el dueño

1. **La copia, ya en pantalla.** El plan dice que la revisas antes de que la
   fase 4 la cite. `just dev-local` y la pantalla *Fondos y presupuestos*.
2. **`[ Crear el primero ]` abre el formulario de fondo.** La alternativa es
   que no abra nada y que las dos puertas con nombre sean la única entrada.
   Una línea en cualquier dirección.
3. **La columna `Regla` ahora usa las etiquetas del oficio** — `Yo pongo el
   tope`, `Aparto un monto fijo cada mes`. Es lo que mantiene un solo
   vocabulario entre el selector y la lista, pero son frases en una columna
   angosta.

---

## 2026-08-07 · Addendum — la pantalla vacía ofrece las dos puertas

Sobre `04d58a2`. **El dueño resolvió el punto 2 de arriba**, y lo resolvió al
revés de como estaba: en vez de una sola puerta sin nombre, **dos, una por
sustantivo**.

```
Todavía no tienes fondos ni presupuestos.

Un FONDO aparta plata cada mes y guarda lo que sobra — para el
mantenimiento del carro, o para pagar una suscripción anual mes a mes.

Un PRESUPUESTO es un tope: lo que no gastes no se guarda.

  [ Crear mi primer presupuesto ]   [ Crear mi primer fondo ]
```

**Su razón, textual, porque decide los casos que vengan después:** acaba de
leer qué es cada uno, así que debe elegir **sabiendo**; y así la pantalla vacía
dice las mismas dos palabras que dice la pantalla llena, que es justo lo que
afirma el AC-21. `Crear el primero` **elegía por él en el momento en que menos
sabe**, que es el defecto que existe este feature para arreglar.

### Qué cambió

- **`EmptyState`**: `action` pasó de `Action` a `Action | Action[]`. Un solo
  concepto — *la puerta, o las puertas* — en vez de dos props que dicen lo
  mismo. **Los 11 sitios que ya lo usaban no se tocaron**: siguen pasando un
  objeto y siguen pintando exactamente lo que pintaban. El botón y el enlace
  salieron a un `WayIn` interno para no duplicarlos por cada puerta.
- **`funds/page.tsx`**: el estado vacío pasa las dos acciones, presupuesto
  primero — el mismo orden que el encabezado y que las dos secciones.
- **Tests**: `An empty Fondos screen offers to create the first one` sigue
  ligado y ahora afirma lo que el AC-10 realmente dice — que ofrece crear el
  primero **de cada forma**, y que cada botón abre el formulario de SU forma.
  Dos tests más lo rodean, y uno más en `empty-state.test.tsx` fija que dos
  acciones pintan dos puertas y que cada una llama a la suya.

### Las dos pantallas dejaron de contradecirse — medido, no razonado

Conté los controles de las dos pantallas con una sonda temporal (después
borrada):

| | botones | ¿todos nombran una forma? |
|---|---|---|
| vacía | `+ Nuevo presupuesto`, `+ Nuevo fondo`, `Crear mi primer presupuesto`, `Crear mi primer fondo` | **sí** |
| con datos | `+ Nuevo presupuesto`, `+ Nuevo fondo`, `Eliminar` | sí |

**El AC-4 quedó cierto también en la pantalla vacía.** *«the screen offers no
way in that does not name a shape»* era **falso** ahí antes de este cambio —
`Crear el primero` no nombraba ninguna — y ahora es cierto en las dos. Eso es
una mejora real, no una casualidad: la tensión que reporté en los findings (2)
**dejó de existir**, y los tests del AC-4 podrían correrse en cualquiera de las
dos pantallas y pasar igual. Los dejé en la pantalla con datos, que es donde
estaban, para no reescribir un binding que ya funciona.

**El AC-20 no quedó igual de limpio, y lo digo en vez de taparlo.** *«exactly 2
controls decide the shape»*: en la pantalla con datos son **2**; en la vacía son
**4**. Bajo la lectura de «dos decisiones» sigue siendo cierto —se ofrecen
exactamente dos formas y nada más—, pero bajo un conteo literal de controles no
lo es. La diferencia con antes es de clase, no de grado: antes la pantalla vacía
**contradecía** al AC-4 con una puerta anónima; ahora **repite** el par en vez
de contradecirlo. El escenario del AC-20 no lleva `Given`, así que su test corre
sobre la pantalla con datos y sigue verde y sigue siendo honesto.

Si al dueño le molesta la repetición, lo que la quita es **ocultar las dos
puertas del encabezado mientras la pantalla está vacía** — con eso el conteo da
2 en las dos pantallas. No lo hice: es una decisión de diseño que él no tomó, y
acopla el encabezado al estado de la consulta, que hoy vive dentro del
`QueryBoundary`.

### Las puertas, verificadas

Dejé `EmptyState` pintando **sólo la primera** acción del arreglo y corrí:
`2 failed | 57 passed (59)`. Restaurado: `59 passed (59)`.

### Compuertas después del cambio

| compuerta | resultado |
|---|---|
| `./run-acceptance-tests.sh` | `361 passed` · sale 1 por lo de siempre · `unbound 38` (igual) |
| `pnpm vitest run` | `Test Files 48 passed (48)` · `Tests 310 passed (310)` (eran 307) |
| `just lint` | exit 0 |
| `spec_coverage.py` | `bound to tests 60` · `unbound 38` |

Sin backend, sin migración, sin tocar el `spec.md`, sin comentarios de código.
Los tres tests nuevos son de la pantalla vacía y del componente, así que
**ningún escenario cambió de ligado a no ligado**.

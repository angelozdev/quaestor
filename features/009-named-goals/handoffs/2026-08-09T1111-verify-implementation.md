---
skill: verify-implementation
agent_id: subagent-verify-cp5
feature: 009-named-goals
started: 2026-08-09T1030
ended: 2026-08-09T1111
checkpoint: 5
artifacts:
  - features/009-named-goals/handoffs/2026-08-09T1111-verify-implementation.md
exit_criteria:
  - criterion: Every acceptance scenario is bound and green
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh` from the repo root → `472 passed, 1 warning in 28.78s`; 009 contributes 125 scenarios over 45 ACs (counted from spec.md: 112 `@backend`, 13 frontend). Green confirmed independently. GREEN IS NOT THE SAME AS SATISFIED — see the next criterion."
  - criterion: Every AC is genuinely reachable and correct
    verified_by: judgment
    met: false
    evidence: "32 of 45 verified end to end. 13 are NOT: AC-11, 14, 16, 19, 24, 26, 27, 29, 34, 36, 39, 41, 42. Three are WRONG BEHAVIOUR reproduced against the REST surface (AC-27, AC-39, AC-14); the rest are service-and-wire-only with no path from anything the owner can do. This criterion is not one CP5 asserted; it is the question the checkpoint exists to answer and it is added here."
  - criterion: The unit suite is green
    verified_by: tool
    met: true
    evidence: "`cd backend && SESSION_SECRET=$(python3 -c \"print('x'*64)\") uv run pytest -q` → `1042 passed, 1 warning in 50.34s`. CP5 recorded 1010; the delta is CP6/CP7/CP8 work, not a disagreement."
  - criterion: The lint gate is green
    verified_by: tool
    met: true
    evidence: "`just lint` → exit 0. Ruff check, ruff format --check, `biome check` (`Checked 195 files in 26ms. No fixes applied. Found 4 warnings. Found 1 info.` — all `noExplicitAny` in `lib/use-url-filters.ts`, pre-existing, not this feature) and `pnpm tsc --noEmit` clean."
  - criterion: The frontend suite is green
    verified_by: tool
    met: true
    evidence: "`cd frontend && pnpm vitest run` → `Test Files 55 passed (55)`, `Tests 397 passed (397)`. Matches CP5's figure."
  - criterion: The bounded query count holds
    verified_by: tool
    met: true
    evidence: "`uv run pytest -q -k bounded_query_count` → `1 passed, 1041 deselected`. `tests/services/test_month_aggregate.py:83` asserts `BOUNDED_LOADS = 13`, which is plan.md's post-CP6 corrected figure, not the 14 CP5 recorded."
  - criterion: Migrations rehearsed before any touch real data
    verified_by: human
    met: partial
    evidence: "NOT VERIFIABLE BY ME AND NOT ATTEMPTED. `runbook.md` records 0013 and 0014 applied 2026-08-08 behind a fresh backup; 0015 (destructive) and 0016 remain `owner: human` and unapplied. I did not touch `.dev-data/`, `migrations/**` or anything named `dev-real`, per CHARTER §7 and my brief. The head of `migrations/versions/` is 0016 and the in-memory SQLite suite upgrades cleanly through it, which is all a host-side run can show."
  - criterion: Verification independence (Principle 7)
    verified_by: judgment
    met: true
    evidence: "SATISFIED BY CONSTRUCTION. `agent_id: subagent-verify-cp5`, distinct from the CP5 implementer's `main-session`. I wrote none of this code, ran all four streams myself rather than reading their numbers from a handoff, and reproduced every defect below against the running REST surface before reporting it."
findings_summary: "THE GREEN IS STILL NOT ENOUGH, AND NOW IT HIDES THREE WRONG NUMBERS RATHER THAN ONLY FOUR MISSING SCREENS. 32 of 45 ACs verified end to end. THREE ARE BEHAVIOURALLY WRONG, all reproduced against the REST surface: (1) AC-39/AC-27 — pressing `Cerrar {meta}` on /metas ARCHIVES THE META OUT OF EVERY MONTH, INCLUDING PAST ONES. An $8.000.000 phone bought in August against a meta holding $6.400.000 makes August read $3.400.000 free with $1.280.000 uncovered; closing makes August read $5.000.000 free with $0 uncovered — the purchase vanishes from the planning half of the app, which is the failure AC-39's own text says it exists to prevent. It also empties September retroactively: a meta that reported holding $3.200.000 and asking $1.600.000 reports NOTHING once it is closed in December, breaking AC-27's own worked figure. Cause: `load_month`'s meta query keeps a CANCELLED meta visible in earlier months via `cancelled_month` and has no equivalent for a CLOSED one. (2) AC-14 — `_room_left` trims a contribution against `meta.amount` instead of the amended amount every other read path uses, so after raising a meta from $8M to $12M, contributing the $9.600.000 that is actually missing silently puts in $5.600.000 and drops $4.000.000, with a toast that names no figure. (3) AC-29 — a CLOSED meta appears under the /metas screen's `Canceladas` heading with the copy 'lo que tenía guardado ya volvió a tu bolsillo', which is false, and its `Traer de vuelta` button succeeds: the meta comes back already complete and charges the month a fresh instalment plus the whole purchase as uncovered. EIGHT MORE ARE SERVICE-AND-WIRE-ONLY, THE SAME SHAPE CP5 ALREADY NAMED FOUR TIMES: AC-41 `counts_as_saving` is on the model, the service and the split arithmetic and is ABSENT FROM `CategoryCreate`, `CategoryUpdate` AND `CategoryOut` — POST /categories with it returns 201 and drops it silently, so the `📈 Inversión` case the AC was written for cannot be marked; AC-36 the monthly report carries NO metas field and NO combined total, its markdown names no meta, and /reports lists only funds — its three step handlers ignore `world.report` and re-derive `month_available` themselves; AC-42 `GET/DELETE /metas/contributions` work on the wire and `lib/api/metas.ts` HAS NEITHER FUNCTION and no screen lists a contribution; AC-34 `stated_opening` computes the AC's own figure over REST and the create form has no field for it; AC-26 a USD meta asks the AC's own USD 333,34 over REST and the create form hardcodes COP with no selector; AC-11/AC-16 a RUNNING meta's amount and month can only be edited from `MetaActions`' completed-meta branch and the name from nowhere at all; AC-19 the waiting meta is named on /metas, never on the dashboard the AC names; AC-24 is unreachable because AC-26 is. THE COMMON CAUSE IS UNCHANGED AND NOW MEASURED: of 125 scenarios, 112 are `@backend` and bound at the services layer, and every one of these thirteen ACs is covered only by those."
human_action_needed: yes
human_action_kind: decision
recommended_next: "The owner decides, in this order. (1) FIX THE THREE WRONG NUMBERS FIRST — AC-39/AC-27 is one line of query logic in `load_month` and it is money-visible on a button the owner will press; AC-14's `_room_left` is one expression; AC-29's list is one filter. None is a design question. (2) DECIDE WHAT THE EIGHT UNREACHABLE ACs ARE — three of them (AC-41, AC-36, AC-42) are high priority and have no screen at all, so they are unbuilt rather than untested; AC-34, AC-26, AC-11/16 are one form field each. (3) ONLY THEN 0015 AND 0016 — they are outstanding and human-owned, and nothing here changes that. CP5 SHOULD NOT BE RECORDED COMPLETE until (1) is done: `exit_criteria` above carries one `false` and one `partial`, and `dae_handoff.py --through 5` fails on the implementer's own handoff regardless."
tracker_update: "local — 009 stays at checkpoint 5, status in-progress. CP5 independently attested by a distinct agent: four streams re-measured and matching (1042 / 55 files·397 / 472 / lint 0), 32 of 45 ACs verified end to end, 13 not, 3 of those behaviourally wrong and reproduced. Migrations 0015/0016 still outstanding and human-owned."
status: complete
---

# verify-implementation — 009 named-goals

Agente fresco. No escribí nada de este código y no le debo nada.

```
backend      1042 passed
vitest       55 archivos · 397 passed
aceptación   472 passed
lint         exit 0
ACs          32 de 45 verificados de punta a punta
```

Los cuatro números coinciden con lo que CP5 dijo, corregidos por CP6/7/8. **Y no
prueban lo que hay que probar.**

## Lo que el verde sigue sin ver

De 125 escenarios, **112 son `@backend`** y se atan en la capa de servicios. Los
trece ACs que fallan abajo están cubiertos **solo** por esos.

### Tres números están mal, y los reproduje

**AC-39 y AC-27 — cerrar una meta le devuelve el mes al dueño en silencio.**

```
A. meta abierta, $6.400.000 ya guardados   disponible 4.680.000   sin cubrir 0
B. celular de $8.000.000 comprado          disponible 3.400.000   sin cubrir 1.280.000
C. el dueño oprime "Cerrar Celular"        disponible 5.000.000   sin cubrir 0
```

Agosto vuelve a leerse como si no hubiera pasado nada. Es exactamente lo que el
propio AC-39 dice que existe para impedir: *"una compra real desaparecería del
mes y su plata reaparecería"*.

Y borra hacia atrás:

```
septiembre antes de cerrar    Celular · lleva 3.200.000 · pide 1.600.000
se cierra en diciembre
septiembre después            (nada)
```

Esa es la cifra literal del primer escenario de AC-27. La causa es una línea:
`load_month` mantiene visible una meta **cancelada** en los meses anteriores por
`cancelled_month`, y no tiene equivalente para una **cerrada** — `archived=True`
con `cancelled_month=None` la saca de todos los meses.

El escenario de AC-39 pasa porque cierra en enero una compra de diciembre: en
enero la meta no pedía nada y la compra no era de ese mes, así que cerrar no
mueve la cifra. Nunca cierra en el mes de la compra.

**AC-14 — el recorte usa el monto viejo.**

```
meta $8.000.000 → sube a $12.000.000   pide 2.400.000 · lleva 2.400.000
falta de verdad                        9.600.000
el dueño aporta                        9.600.000
entra                                  5.600.000     ← 4.000.000 se pierden
```

`_room_left` (services/metas.py:322) calcula `meta.amount - holds` con el monto
guardado, no con el enmendado que usa `_wanted_in` en todo el resto del camino.
El toast dice *"Le pusiste plata a Celular"* sin cifra, así que el dueño no se
entera.

**AC-29 — una meta cerrada se lista como cancelada, con un botón que cobra.**

`list_archived` filtra `Meta.archived` sin excluir `closed`, así que una meta
que el dueño **cerró** aparece bajo *Canceladas* con el texto *"lo que tenía
guardado ya volvió a tu bolsillo el mes que la cancelaste"* — falso, cerrar no
devuelve nada. Y *Traer de vuelta* funciona: vuelve ya cumplida, pidiendo
$1.600.000 otra vez y cargando los $6.400.000 de la compra como sin cubrir.

### Ocho no tienen por dónde llegarle

La misma forma que CP5 ya nombró cuatro veces.

```
AC-41  counts_as_saving   modelo + servicio + aritmética del reparto
                          NO está en CategoryCreate, CategoryUpdate ni CategoryOut
                          POST /categories con el campo → 201, y lo bota
AC-36  el reporte         MonthlyReport no tiene metas ni total conjunto
                          el markdown no nombra ninguna, /reports solo lista fondos
                          los tres handlers ignoran world.report y recalculan
AC-42  aportes            GET/DELETE andan por REST · lib/api/metas.ts no los tiene
AC-34  stated_opening     da la cifra exacta del AC por REST · el form no lo pide
AC-26  dólares            pide USD 333,34 por REST · el form es COP fijo
AC-11  editar corriendo   monto y mes solo en la rama de meta cumplida
AC-16  bajar el monto     necesita ese mismo camino que no existe
AC-19  la que espera      la nombra /metas, no el dashboard que dice el AC
AC-24  sin tasa           depende de AC-26: no se puede crear una meta en dólares
```

## Lo que sí quedó verificado de punta a punta

Los 32 restantes, trazados pantalla → cliente → endpoint → servicio → regla:
AC-1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 17, 18, 20, 21, 22, 23, 25, 28,
30, 31, 32, 33, 35, 37, 38, 40, 43, 44, 45.

El selector de meta sí está en los dos diálogos de movimiento, los tres botones
sí tienen `onClick` y la prueba sí los oprime, el desglose sí llega al navegador
y suma, y el reparto consumo/ahorro/libre sí se pinta en el dashboard. AC-43
llega en dos pasos —`POST /planned` bota el `meta_id` en silencio, pero editar
el movimiento después sí lo pega—, y AC-40 está limpio: `FundRule` tiene tres
valores en los dos lados.

## Human action needed?

**Sí — decisión.** Tres cifras mal en código que el dueño va a tocar, y ocho
comportamientos que existen en Python y en ninguna pantalla. Yo verifico; él
decide qué se arregla. No toqué nada.

## Recommended next step

Arreglar los tres números primero: ninguno es una pregunta de diseño. Después
decidir qué son los ocho — tres de ellos (AC-41, AC-36, AC-42) son de prioridad
alta y no tienen pantalla, o sea que están **sin construir**, no sin probar.
CP5 no debería quedar `complete` hasta eso.

## La compuerta, tal como respondió

```
$ python3 …/engineer/0.19.0/scripts/dae_handoff.py features/009-named-goals --through 5
verifier-independence violated: CP6 handoff 2026-08-09T0758-refine.md shares
agent_id main-session with the CP5 implement handoff (Principle 7)
EXIT=1
```

Correcto, y no se debe rodear. `dae_handoff.py` toma el **primer** handoff de
CP5 por orden de nombre como el del implementador, así que `main-session` sigue
siendo el implementador registrado y el de CP6 —también `main-session`, porque
el implementador aplicó sus propios hallazgos de refine— seguirá fallando
Principio 7 sin importar lo que diga este documento. Este handoff hace que
**CP5** quede atestiguado de forma independiente; no lava CP6 ni debe hacerlo.

## Tracker update

009 sigue en checkpoint 5, `in-progress`. CP5 queda atestiguado por un agente
distinto del implementador, con un `false` y un `partial` en `exit_criteria`.

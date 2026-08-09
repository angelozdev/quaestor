---
skill: close-findings
agent_id: main-session
feature: 009-named-goals
started: 2026-08-09T1115
ended: 2026-08-09T1230
checkpoint: 5
artifacts:
  - docs/adr/0048-a-purchase-stops-the-meta-and-closing-it-moves-no-figure.md
  - docs/decisions/product-decisions.md (ADR-044)
  - features/009-named-goals/handoffs/2026-08-09T1230-close-findings.md
exit_criteria:
  - criterion: Every acceptance scenario is bound and green
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh` → `472 passed, 1 warning`. 009 contributes 112 `@backend` scenarios; the three AC-36 step handlers now read `world.report` instead of re-deriving the figures from the month, so they exercise the report they name."
  - criterion: Every AC is genuinely reachable and correct
    verified_by: judgment
    met: true
    evidence: "The thirteen the verifier could not reach are closed. Three were wrong figures, each reproduced red before the fix and pinned by a named test: closing a bought meta (AC-39/AC-27), the trim against the stored rather than the amended amount (AC-14), and a closed meta listed as cancelled with a working restore (AC-29). Eight were unbuilt: `counts_as_saving` through all three category schemas and the category form (AC-41); the metas section, the combined total and the markdown of the monthly report, plus /reports (AC-36); the contributions list and its removal (AC-42); `stated_opening` and the currency selector on the create form, and the preview corrected to count what was already put by (AC-34, AC-26, AC-24); name, amount and month editable while a meta runs (AC-11, AC-16); the waiting meta named on the dashboard (AC-19). NOT VERIFIED BY AN AGENT OTHER THAN THE ONE THAT WROTE IT — this criterion is asserted by the implementer and is exactly the assertion Principle 7 exists to distrust."
  - criterion: The unit suite is green
    verified_by: tool
    met: true
    evidence: "`cd backend && SESSION_SECRET=… uv run pytest -q` → `1063 passed, 1 warning`. Up from 1042: eleven tests for the three defects and the preview, six HTTP round-trips over `PATCH /metas/{meta_id}` and the two new create fields, three for `counts_as_saving` over the wire, and three for the report's metas section and its total."
  - criterion: The frontend suite is green
    verified_by: tool
    met: true
    evidence: "`cd frontend && pnpm vitest run` → `Test Files 55 passed (55)`, `Tests 417 passed (417)`. Up from 397: four on the categories screen, four on /reports, nine on /metas, three on the dashboard."
  - criterion: The lint and boundary gates are green
    verified_by: tool
    met: true
    evidence: "`just lint` → exit 0. `Contracts: 2 kept, 0 broken`. `pnpm knip` → 0 findings after deleting `FundUpdate`, which nothing referenced. `just dup` → 43 clones, 1.96% — back to the figure before this work, after collapsing the two asks a running meta makes into one component and extracting the create form's second money field."
  - criterion: The bounded query count holds
    verified_by: tool
    met: true
    evidence: "`uv run pytest -q -k bounded_query_count` → passes. `BOUNDED_LOADS = 13` is unchanged: `_bought_in` reads the purchases the fold already loaded and issues no statement."
  - criterion: Architecturally significant decisions are recorded
    verified_by: judgment
    met: true
    evidence: "ADR-0048 accepted, superseding **one clause** of ADR-0046 — *'an instalment of zero happens only because nothing is missing, never because completing, cancelling or editing waived it'*. A purchase now ends the series from the following month. ADR-0046's `Superseded by` names the clause and says the rest stands; the index carries both. Product ADR-044 records the owner's decision in his own terms."
  - criterion: Mutation holds on the module that changed
    verified_by: tool
    met: true
    evidence: "`scripts/mutate.py --target backend/src/quaestor/services/metas.py` over a four-stage ladder (the module's unit file, its HTTP file, 009's generated acceptance tests, then the whole backend): **143 mutants, 138 killed, 5 survived — 96.5% raw, 100% adjusted.** Two of the seven the first sweep left alive were real and both were in `_bought_in`, the function this work added: `posted_only=False -> True` (a purchase owed and not yet paid stops the meta too — the month already charged the shortfall) and `min -> max` (the FIRST purchase stops it; the second, pointed at the meta later, cannot move that forward). The first attempt at the second test did not kill it — the aggregate for September has not seen an October purchase, so `min` and `max` agree there; it took reading November, where the fold has seen both. The remaining five are equivalent or unreachable: `frozen=True` on two dataclasses nothing mutates, `opening > amount` -> `>=` (the equal case produces identical figures down every branch), and twice `else 0` on a progress percentage guarded by an amount validation refuses to let reach zero."
  - criterion: Migrations rehearsed before any touch real data
    verified_by: human
    met: partial
    evidence: "NOT ATTEMPTED, AND NOT MINE. 0015 (destructive) and 0016 remain `owner: human`. Nothing in this work adds a migration — that was the deciding argument for the shape ADR-0048 chose."
  - criterion: Verification independence (Principle 7)
    verified_by: judgment
    met: false
    evidence: "NOT MET AND NOT WORKED AROUND. `agent_id: main-session` — the same agent that implemented CP5 and applied CP6's findings has now applied the verifier's. The findings were independent; the fixes are not. `dae_handoff.py --through 5` still exits 1 on `CP6 handoff 2026-08-09T0758-refine.md shares agent_id main-session with the CP5 implement handoff`, which is correct."
findings_summary: "THE VERIFIER'S THIRTEEN ARE CLOSED, AND THE ONE UNDERNEATH THEM WAS BIGGER THAN THE ONE REPORTED. Closing a bought meta erased it from every month because `load_month` kept an archived meta alive only through `cancelled_month`, which a closed meta does not carry. Making it visible again exposed why nobody had noticed: A META WENT ON ASKING ITS INSTALMENT EVERY MONTH AFTER THE THING WAS BOUGHT — a phone bought in October kept asking $1.600.000 in November and December — and closing, by erasing the meta, was the only thing that stopped it. The two defects were holding each other up, which is why four streams of green saw neither. THE OWNER DECIDED THE SHAPE: a purchase stops the meta the month after it is made, the purchase month still asks because what it asks is part of what covered the purchase, and closing only takes the meta off the screen. No migration, against an alternative that needed a fourth one while three are outstanding. Recorded as ADR-0048 (superseding one clause of ADR-0046) and product ADR-044. THE OTHER TWO FIGURES: `_room_left` trimmed against `meta.amount` while every other read path folds the amendments, so raising a meta from $8M to $12M and contributing the $9.600.000 actually missing dropped $4.000.000 in silence; and `list_archived` filtered `archived` without excluding `closed`, so a meta the owner closed appeared under Canceladas promising its money had come back, with a Traer de vuelta that charged the month the whole purchase again. THE EIGHT UNBUILT ARE BUILT, because the owner chose to close 009 only when all 45 ACs are reachable from the app rather than moving them to a new feature. That reverses this session's earlier decision to delete the contributions client. AND THE OPEN CRAP-ANALYZER FINDING IS CLOSED: `PATCH /metas/{meta_id}` had a tested screen above it and a tested rule below it and nothing in between; six round-trips now cover it at the ACs' own figures. WHAT THIS HANDOFF CANNOT SAY IS THAT ANY OF IT IS INDEPENDENTLY VERIFIED. The same agent wrote the code and is asserting it works."
human_action_needed: yes
human_action_kind: decision
recommended_next: "The owner decides. (1) `just backup && just migrate` for 0015 and 0016, then the merge to `main` — both charter §7 and neither is an agent's to do. (2) WHETHER TO SEND A SECOND FRESH VERIFIER. The first one's value was not the list it produced but that it was written by an agent with nothing invested in the answer; this handoff has the opposite property on every criterion it marks true. The 45 ACs are now claimed reachable by the agent that made them reachable. (3) CP6, CP7 and CP8 all ran against code that has since changed materially — refine has not seen the report's metas section or the contributions list, and the crap-analyzer's coverage figures predate 24 new tests."
tracker_update: "local — 009 stays at checkpoint 5, status in-progress. All thirteen of the verifier's findings closed. Backend 1042 → 1061, vitest 397 → 417, acceptance 472 unchanged and now exercising the report it names. Two decisions recorded: ADR-0048 and product ADR-044. Migrations 0015/0016 still outstanding and human-owned."
status: complete
---

# close-findings — 009 named-goals

El verificador encontró trece ACs que no se podían alcanzar. Están cerrados.
Este documento dice qué se hizo y qué **no** queda probado por haberlo hecho yo.

```
backend      1063 passed   (era 1042)
vitest       55 archivos · 417 passed   (era 397)
aceptación   472 passed
lint         exit 0 · contratos 2 kept, 0 broken
knip         0 findings
dup          43 clones · 1.96%
```

## Las tres cifras malas

**Cerrar una meta comprada le devolvía el mes al dueño.** `close_meta` archiva
sin mes de cancelación, y la consulta del mes solo mantenía viva una meta
archivada a través de `cancelled_month`. Una meta **cerrada** no calzaba con
ninguna rama y desaparecía de todos los meses, incluidos los pasados.

```
A. meta abierta, $6.400.000 guardados        disponible 4.680.000   sin cubrir 0
B. celular de $8.000.000 comprado en agosto  disponible 3.400.000   sin cubrir 1.280.000
C. el dueño oprime "Cerrar Celular"          disponible 5.000.000   sin cubrir 0
```

**Y debajo había una más grande.** Al volverla visible se vio por qué nadie lo
había notado: una meta seguía pidiendo su cuota todos los meses después de
comprada la cosa. Un celular comprado en octubre seguía pidiendo $1.600.000 en
noviembre y en diciembre. Cerrar era lo único que lo detenía — y cerrar era lo
que borraba el pasado. Los dos defectos se sostenían mutuamente.

El dueño decidió la forma: **la compra apaga la meta al mes siguiente**, el mes
de la compra sigue pidiendo porque lo que pide es parte de lo que cubrió la
compra, y cerrar solo la saca de la pantalla. Sin migración, contra una
alternativa que pedía una cuarta con tres pendientes. ADR-0048 y ADR-044.

**El recorte usaba el monto viejo.** `_room_left` calculaba contra `meta.amount`
mientras todo el resto del camino dobla las enmiendas: subir una meta de $8M a
$12M y aportar los $9.600.000 que de verdad faltaban metía $5.600.000 y botaba
$4.000.000 sin decir nada.

**Una meta cerrada se listaba como cancelada.** Con el texto *"lo que tenía
guardado ya volvió a tu bolsillo"*, que es falso, y un *Traer de vuelta* que
funcionaba: volvía ya cumplida y le cargaba al mes la compra entera otra vez.

## Los ocho sin pantalla

El dueño escogió cerrar 009 cuando los 45 ACs se puedan hacer desde la app, no
mover los ocho a una feature nueva. Eso revierte la decisión de esta misma
sesión de borrar el cliente de aportes.

```
AC-41  marcar una categoría como ahorro   3 esquemas + el formulario
AC-36  las metas en el reporte del mes    dominio + markdown + /reports
AC-42  ver y quitar aportes               cliente + pantalla
AC-34  decir cuánto llevaba al abrir      formulario + el preview, que mentía
AC-26  metas en dólares                   selector de moneda
AC-24  sin tasa                           alcanzable ahora que AC-26 lo es
AC-11  editar una meta corriendo          nombre, monto y mes
AC-16  bajar el monto                     el mismo camino
AC-19  la meta que espera                 nombrada en el dashboard
```

Los tres handlers de AC-36 ignoraban `world.report` y recalculaban las cifras
del mes. Por eso pasaban sobre un reporte vacío. Ahora leen el reporte.

## Lo que este documento no puede decir

Que algo de esto esté verificado de forma independiente. Los hallazgos fueron
de un agente sin nada invertido en la respuesta; los arreglos son míos, y el
criterio *"cada AC se alcanza de verdad"* lo firma arriba el mismo que escribió
el código. Es exactamente la afirmación que el Principio 7 existe para
desconfiar.

`dae_handoff.py --through 5` sigue en rojo por CP6, y debe seguirlo.

## Human action needed?

**Sí — decisión.** Migraciones 0015 y 0016 y el merge son del dueño (charter
§7). Y queda abierto si mandar un segundo verificador fresco: CP6, CP7 y CP8
corrieron todos contra código que ya cambió.

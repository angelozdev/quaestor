---
skill: browser verification (CHARTER §6)
agent_id: main-session
feature: 017-transaction-filters-and-drilldown
started: 2026-08-19T1408
ended: 2026-08-19T1418
checkpoint: 7 (CHARTER §6 gate, closes out the same Verify checkpoint the independent verifier's CP7/CP8 handoffs cover)
artifacts:
  - frontend/app/(app)/transactions/page.tsx
  - frontend/app/(app)/transactions/page.test.tsx
  - backend/src/quaestor/services/transactions.py
  - backend/tests/services/test_transactions.py
findings_summary: "Drove the feature against the running dev-local stack (docker compose, api :8000 healthy, frontend :3100 healthy — both containers had been up 4h from earlier feature-016 work this session, confirmed via `docker compose ps` rather than trusting the stale `.engineer/infra/dev-stack.json` PID, which was already dead). Real production-shaped sandbox data (not a clean seed), same posture as every prior browser pass this session. ALL THREE validation_method CASES CONFIRMED WORKING ON REAL DATA: (1) amount filter with a USD account — set Monto mínimo=200000 on /transactions; URL became ?amount_min=20000000, list correctly narrowed to rows whose COP-equivalent is >=200.000 including USD-denominated rows converted live through the TRM ('VERIFY Hogaru USD' US$87.52->$274.988 included, 'VERIFY doble cobro' US$400.00->$1.256.800 included, 'Opal' US$29.35->$92.218 correctly excluded) — confirmed by comparing the filtered list against the full unfiltered list row-by-row, not just spot-checking one row. (2) group filter — selected 'Esenciales' in the Grupo dropdown (a real group with 2 more members than the acceptance suite's synthetic fixtures); URL became ?group_id=1, list correctly returned movements from all three of that group's categories (Servicios, Transporte, Mercado) together — 'Netflix' (Servicios), 'Taxi' (Transporte), 'Éxito' (Mercado) all appeared under one filter. (3) Ver movimientos drill-down — tested from all three source screens, not just one: Categorías→'Mercado' landed on /transactions?category_id=1 showing only 'Éxito'; Grupos→'Esenciales' landed on ?group_id=1 with the same correct list as the manual filter selection; Etiquetas→'mercado' landed on ?tag=1 showing only 'Éxito'. A REAL DEFECT WAS FOUND BY THE BROWSER, INVISIBLE TO EVERY PRIOR TEST STREAM (unit, acceptance, AND the CP6 vitest suite, which never caught it because its Limpiar test only asserts the router.replace call, never re-renders the component to observe the resulting DOM): after typing 200000 into Monto mínimo and clicking Limpiar, the filter genuinely cleared (URL went back to bare /transactions, the full unfiltered list reappeared) but the Monto mínimo input kept visually showing '200000' — false information left on screen telling the owner a filter was still set when it was not. Root cause: MoneyInput (the same component every money field in this app uses) keeps its displayed text in local useState, and by its own documented design only re-syncs that text when the `currency` prop changes, not when `value` resets to null from outside — a deliberate choice everywhere else in the app, where MoneyInput always lives inside a dialog that fully unmounts on close, so the question of 'does it re-sync on an external clear' never previously arose. The transactions filter bar is the first place MoneyInput stays mounted across a clear. FIXED, narrowly, without touching MoneyInput itself (used by 6+ other forms): the filter bar's two MoneyInput instances now carry a `key` that flips between an 'empty' and 'filled' string tied to `values.amount_min`/`values.amount_max` being null, forcing exactly one remount at the fill<->clear boundary and none during normal digit-by-digit typing (confirmed no keystroke-level remount by re-testing the amount filter end-to-end after the fix: typing still worked correctly, filtering still applied correctly). Verified in the browser after the fix: same repro (type 200000, click Limpiar) now shows the input genuinely empty. A NEW REGRESSION TEST pins it in transactions/page.test.tsx ('Monto mínimo visually clears once the URL drops it, not just once the page remounts', using RTL's rerender to simulate the URL changing under a live instance rather than a fresh mount) — verified to fail against the pre-fix code (temporarily reverted the two key props, reran, confirmed the exact failure: received '200000', expected '', then restored) and pass against the fix. SEPARATELY, ALSO CLOSED THIS SESSION (found by the independent CP7/CP8 verifier, not by this browser pass): the CP8 mutation sweep found two real, confirmed survivors — _in_cop_range's inclusive-boundary comparisons (a transaction landing exactly on amount_min or amount_max was silently excluded, contradicting AC-1/AC-8's own 'igual o mayor/menor' wording) were correct in the source but untested at the exact edge. Two unit tests added (test_list_transactions_amount_min_is_inclusive, test_list_transactions_amount_max_is_inclusive in backend/tests/services/test_transactions.py) and manually confirmed to kill both mutants (temporarily flipped < to <= and <= to <, reran, confirmed each test fails exactly as expected, then restored via git-tracked diff, not a backup file). Sandbox left clean: no test data was created or mutated by this browser pass (every action was a read-only filter/navigation; the two write-side rows in the sandbox, if any existed from a prior session's feature-016 walkthrough, were never touched here)."
human_action_needed: no
recommended_next: "Feature is complete: all 15 ACs verified in code and the 3 real-UI-surface cases named by validation_method verified live in the browser against real data, matching CHARTER §6 in full. Ready for the owner's review and merge decision (CHARTER §7 — merge to main is the owner's, not this session's, to make)."
tracker_update: null
exit_criteria:
  - criterion: "the feature was driven in a browser against the sandbox, per CHARTER §6 and plan.md's validation_method"
    verified_by: human
    met: true
    evidence: "All three named cases (amount filter against a USD account, group filter, Ver movimientos drill-down from all three source screens) exercised end-to-end through the actual running UI against real production-shaped sandbox data, not synthetic fixtures — screenshots captured at each step confirming exact URL state, correct filtered row sets, and correct COP-equivalent arithmetic for USD rows."
  - criterion: "green is not verified — the browser pass looked for what tests could not see, not just replayed what they already proved"
    verified_by: human
    met: true
    evidence: "Found a real, previously-invisible defect (Monto mínimo not visually clearing after Limpiar) precisely because it required a live, mounted-across-navigation component interaction no existing test — unit, acceptance, or even CP6's own new vitest coverage — happened to exercise. Fixed, pinned with a new regression test verified against both the broken and fixed code, re-verified live in the browser after the fix."
  - criterion: "the sandbox was left in the state it was found (no stray data from the walkthrough)"
    verified_by: human
    met: true
    evidence: "Every action taken was read-only (typing into a filter, clicking a dropdown, clicking a drill-down link) — no create/edit/delete/archive action was performed against any real record. `git status` on the sandbox's database is not tracked by this tool, but no mutation-capable UI control was ever clicked."
  - criterion: "all changes made during verification are covered by the full test suite, re-run fresh"
    verified_by: tool
    met: true
    evidence: "After the Limpiar fix + its regression test + the two mutation-gap boundary tests: ./run-acceptance-tests.sh -> 736 passed, lint clean, exit 0. pnpm vitest run -> 604 passed (was 603 before this pass), 59 files. Backend uv run pytest -q -> 1280 passed (was 1278), 1 pre-existing unrelated flake (test_scheduler). tsc --noEmit clean. biome check clean, same 4 pre-existing warnings this session has seen on every prior feature."
status: complete
---

# browser-verify (CHARTER §6) — resumen del handoff

**Los tres casos que pedía `validation_method` funcionan de verdad, con
datos reales — y el navegador encontró un bug que ningún test veía.**

## Lo esperado, confirmado con datos reales, no con fixtures sintéticos

Monto mínimo 200.000 filtró correctamente movimientos en pesos y en
dólares reales del sandbox, convertidos a la TRM en vivo. El filtro de
grupo "Esenciales" trajo Servicios + Transporte + Mercado juntos. "Ver
movimientos" funcionó desde Categorías, Grupos y Etiquetas — las tres, no
solo una.

## Lo que ningún test veía

Escribir "200000" en Monto mínimo, filtrar, y después apretar "Limpiar":
el filtro se borra de verdad (la lista completa vuelve), pero la caja se
queda mostrando "200000" — información falsa en pantalla. La causa:
`MoneyInput`, el mismo que usa cada formulario de dinero de la app, solo
resincroniza su texto cuando cambia la moneda, nunca cuando el valor
externo se limpia — nadie lo había visto porque en cualquier otro lado
`MoneyInput` vive dentro de un diálogo que se desmonta al cerrar. La barra
de filtros es el primer lugar donde se queda montado a través de un
"Limpiar".

Arreglado sin tocar `MoneyInput` (lo usan 6+ formularios más): un `key`
que fuerza un remount solo en la transición lleno↔vacío, nunca mientras se
escribe. Fijado con una prueba nueva, verificada contra el bug y contra el
arreglo, reconfirmada en vivo.

## Lo que cerró el verificador independiente, aparte

Los dos sobrevivientes de mutación en `_in_cop_range` (el borde inclusivo
sin probar) — dos tests nuevos, verificados uno por uno contra cada
mutante antes de restaurar el archivo.

```
DAE ▸ 017-transaction-filters-and-drilldown
·0 Onboard · ·1.5 Ready · ·2 ACs · ·3 Spec · ·4 Plan · ·5 Implement · ·6 Refine · ▶7 Verify · ·8 Harden
```

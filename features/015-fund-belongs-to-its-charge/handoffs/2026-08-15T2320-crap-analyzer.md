---
skill: crap-analyzer
agent_id: cp7-verifier-independent + main-session (browser, fixes)
feature: 015-fund-belongs-to-its-charge
started: 2026-08-15T1940
ended: 2026-08-15T2320
checkpoint: 7
artifacts:
  - docs/adr/0058-el-pago-se-aplica-a-un-turno-no-se-deduce-del-mes.md
  - backend/src/quaestor/services/occurrences.py
  - backend/src/quaestor/services/month_aggregate.py
  - backend/src/quaestor/services/funds.py
  - backend/src/quaestor/services/transactions.py
  - backend/src/quaestor/services/bootstrap.py
  - backend/src/quaestor/api/routers/funds.py
  - backend/src/quaestor/api/routers/transactions.py
  - backend/src/quaestor/api/schemas.py
  - backend/src/quaestor/mcp/format.py
  - backend/src/quaestor/domain/report_markdown.py
  - backend/tests/services/test_funds.py
  - backend/tests/mcp/test_funds.py
  - acceptance/handlers/fund_per_charge.py
  - features/015-fund-belongs-to-its-charge/acs.md
  - features/015-fund-belongs-to-its-charge/spec.md
  - frontend/lib/date.ts
  - frontend/lib/available-breakdown.ts
  - frontend/components/settles-charge-field.tsx
  - frontend/components/transaction-create-dialog.tsx
  - frontend/components/transaction-edit-dialog.tsx
  - frontend/app/(app)/funds/page.tsx
findings_summary: "AN INDEPENDENT VERIFIER FOUND NINE DEFECTS AND ONE TEST-HOLE WORSE THAN ANY OF THEM, WITH ALL THREE SUITES GREEN. I reproduced the three most severe myself before acting on any of them. THE TEST-HOLE FIRST: `month.py`'s two AC-9 exclusions — the ones that stop the same peso leaving the month twice, which decide the owner's free money — could be deleted with 1213 tests still green. Pinning `MonthAggregate.funded_charges` to empty reddened exactly ONE test, and that one was `test_a_marked_charge_is_not_counted_twice_by_the_monthly_rate`, which exists only because the migration rehearsal forced it. Two tests added; the same perturbation now reddens three. My first two assertions were WRONG and I corrected them by measuring rather than by adjusting until green: a payment naming its charge does not leave `uncovered` at zero, it leaves the excess over what the fund had collected. The assertion is now the promise itself — `uncovered + Σ asks_cop == the payment`. F3, MONEY ON SCREEN: `_drained` returns the charge's native cents since this feature, so a dollar fund's overspill entered the peso `uncovered` term unconverted. Measured: US$ 523,91 counted as 523,91 pesos when it is worth 2.095.640 — the month told the owner he had 2.095.116,09 MORE free money than he had. Latent in production (the migration marked two peso charges), live the moment a dollar charge is marked, which the sandbox browser pass had already done. Converted at `fold`, where the excess stops being the fund's and becomes the month's. F1/F2, THE SAME DEFECT ON THREE MORE SURFACES: the Disponible column on two screens and the assistant's month card rendered a dollar fund's ask as pesos, so the column stopped adding to its own total. The meta line one row below was already converting in every one of them. F4/F5, THE ONES THAT NEEDED A DECISION: settlement was read one month at a time, so a charge paid in August was forgotten in September and billed again — 600.000 the owner did not owe, across two months — and a charge paid late read as a cycle skipped, showing a date a year wrong at less than half the figure. Both reproduced. Put to the owner as product behaviour; he chose that the payment name the turn it settled. ADR-0058 written and accepted. NO SCHEMA CHANGE AND NO MIGRATION: `RecurringOccurrence` was already one row per (charge, due date) with the movement that paid it and a unique key per turn — the shape the engine fills when a charge posts itself, and the industry's own answer (a payment is *applied* to an instalment, never inferred from amount and date). All that was missing was a hand-typed payment being able to attach to it. F9, A FALSE SENTENCE: a charge fund whose charge ran out told the owner the CATEGORY had no repeating charges and to delete the fund with a button that now says «Dejar de juntar». AND ONE THE BROWSER FOUND THAT NOTHING ELSE COULD: driving the app at 21:56 in Bogotá, the new-movement form proposed TOMORROW's date — three forms computed today in UTC. Pre-existing, not introduced here, and the same family as the Recurring month CP6 fixed; it only misfires between 7pm and midnight, and the pass happened to be inside that window."
human_action_needed: yes
recommended_next: "atdd:mutate for CP8 Harden, on a freshly migrated worktree (test_scheduler touches backend/quaestor.db on disk). Four CP7 findings are deliberately unfixed and listed below — the owner decides whether they belong to 015 or to the next feature."
tracker_update: "none — roadmap item already in-progress."
exit_criteria:
  - criterion: "CRAP was measured over the changed code"
    verified_by: tool
    met: true
    evidence: "Coverage taken with a stdlib `sys.monitoring` LINE tracer loaded from the scratchpad (`coverage` and `pytest-cov` are absent and nothing was installed), merged over `backend/tests` and `features/*/.build/generated`; backend 91.2% (7492/8213). Frontend via @vitest/coverage-v8 into the scratchpad. Threshold 20. Worst six: RecurringPage 44.9, migration 0020's `rejoin_charge_funds_into_category_funds` 42.0 (0% covered), EditTransactionForm 32.0, TransactionCreateDialog 30.0, EditChargeForm 20.1, load_month_aggregate 20.0. Only the second is actionable and it is a downgrade path; the rest are above threshold on complexity alone at ~100% coverage."
  - criterion: "the risk of a wrong figure was assessed by reproduction, not by argument"
    verified_by: tool
    met: true
    evidence: "Nine findings, each with a script that ran and printed its figures. I independently re-ran the three worst before touching code: F3 printed overspill 52391 entering `uncovered` as pesos when it is worth 2.095.640,00; F4 printed the five-month table where September walks back to the turn August paid; the AC-9 hole printed `1 failed, 1213 passed` under the perturbation. A 486-combination sweep (9 cadences × 6 costs × 3 start months × 3 currency/TRM pairs) came back with 0 violations on the month arithmetic — the divisor and the floor-at-one are sound."
  - criterion: "every AC is mapped to the stream that covers it, and gaps are named"
    verified_by: inspection
    met: true
    evidence: "All 11 mapped by the verifier. Real: AC-1, 2, 3, 4, 7, 10 and AC-6 (which also has production evidence in runbook.md). Repaired here: AC-5's create surface, its month-after and late-payment cases, and AC-9's month.py half. Still nominal and named below: AC-8's archive door (F6) and its edit warning (F7)."
  - criterion: "perturbation shows the suites can fail"
    verified_by: tool
    met: true
    evidence: "20 perturbations run as a scratchpad pytest plugin, no tracked file edited. `fund_ask_calc` +1 cent → 197 red; `months_to_fund` +1 month → 88; `mark_charge` raising → 41; `unmark_charge` → 34; currency pinned to COP → 4. One left everything green — month.py's AC-9 exclusions — and that is the finding. After the two tests added here the same perturbation reddens 3."
  - criterion: "the feature is driven in a browser (CHARTER §6)"
    verified_by: human
    met: true
    evidence: "Against the SQLite sandbox on localhost:3000, 2026-08-15. Production was running on those ports and was stopped first with the owner's explicit permission (`just dev-prod-down`, no -v, volume `quaestor_quaestor_pg_data` confirmed intact); the API was confirmed on `sqlite:////app/.dev-data/quaestor.db` BEFORE anything was written. Driven: the create-expense form now offers the marked charges of its category and only those; the new «¿Cuál vencimiento?» question appears with two turns open and not with one; choosing the September turn wrote the September turn and not the pre-selected June one; and the fund then read 2026-12 in August, September, October, November and December — the defect, gone on real rows. Reportes showed US$ 50.00 beside $ 21.429. The date box read 15/08 where it had read 16/08 an hour earlier. TWO THINGS READ IN CENTS RATHER THAN OFF THE SCREEN, and said so: the delete-releases-the-turn path (its «...» menu lives in a portal the accessibility tree does not expose) and the UTC month fix (only reproducible on the last day of a month)."
  - criterion: "both test streams are green and the tree is clean"
    verified_by: tool
    met: true
    evidence: "backend 1221 passed; ./run-acceptance-tests.sh 714 passed; frontend 58 files / 575 tests; spec-coverage for 015: 55 scenarios, 42 @backend, 13 bound, 0 unbound; `just lint` exit 0; `pnpm tsc --noEmit` exit 0; `uv run lint-imports` Contracts: 2 kept, 0 broken. The verifier finished with `git status --porcelain` empty; every probe lives in the scratchpad."
status: complete
---

# CP7 — Light Verify

Un verificador independiente, un paso por navegador, y **una decisión de
producto que salió de lo que encontraron**.

## Lo que se arregló

| | qué veía el dueño | dónde |
|---|---|---|
| F3 | 2.095.116 de plata libre que no existía | `funds.fold` |
| F1 | la columna Disponible dejaba de sumar | Dashboard y Reportes |
| F2 | lo mismo en la tarjeta del asistente | `mcp/format.py` |
| F4 | 600.000 reclamados dos meses seguidos | ADR-0058 |
| F5 | un pago atrasado leído un año adelante | ADR-0058 |
| F9 | una frase falsa sobre la categoría | Fondos |
| — | la fecha de hoy calculada en UTC | tres formularios |

## El agujero, que valía más que los nueve

Las dos exclusiones que impiden que el mismo peso salga del mes dos veces se
podían **borrar con 1.213 pruebas en verde**. La perturbación daba 1 rojo, y ese
rojo existía solo porque el ensayo de migración lo había forzado a escribir.

Mis dos primeras aserciones estuvieron mal. Las corregí **midiendo**, no
ajustándolas: un pago que nombra su cobro no deja «sin cubrir» en cero, deja el
exceso sobre lo que la caja había juntado.

## Lo que NO se arregló, a propósito

Cuatro hallazgos quedan vivos. Ninguno pierde plata; los cuatro son del AC-8 o
de cobertura, y son alcance que el dueño decide:

- **F6** — mudar un cobro marcado a otra categoría deja la caja apuntando a la
  vieja: la categoría donde ahora vive se archiva sin refusal y la caja le
  sobrevive pidiendo plata; la categoría vieja se refusa nombrando un cobro que
  ya no está.
- **F7** — editar la fecha de fin borra el fondo **sin el aviso** que el AC-8
  promete: la pantalla solo pregunta por la cadencia.
- **F8** — re-clasificar un pago saldado se rechaza por un campo que el dueño no
  ve. Mitigado en el diálogo de crear y en el de editar (los dos limpian el
  enlace al cambiar de categoría), no cerrado en el servicio.
- **Cobertura** — los cuatro endpoints de `/funds/charges` no los ejecuta
  ninguna prueba (los drivé a mano con TestClient y responden bien), y el
  `downgrade` de la migración 0020 está en 0%.

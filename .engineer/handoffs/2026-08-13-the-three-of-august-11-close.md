---
skill: fix (close)
agent_id: main-session
feature: 012-movement-corrections
fix_slugs:
  - 2026-08-11-expired-session-reports-a-saved-movement
  - 2026-08-11-a-foreign-currency-account-cannot-be-written-to
  - 2026-08-11-a-recurring-charge-cannot-live-in-a-dollar-account
started: 2026-08-13T2340
ended: 2026-08-14T0040
checkpoint: null
branch: main
artifacts:
  - .engineer/fixes/2026-08-11-expired-session-reports-a-saved-movement.md
  - .engineer/fixes/2026-08-11-a-foreign-currency-account-cannot-be-written-to.md
  - .engineer/fixes/2026-08-11-a-recurring-charge-cannot-live-in-a-dollar-account.md
findings_summary: "THREE FIXES SAT AT `hardened` FOR TWO DAYS WITH THEIR CODE ALREADY IN `main`. Closing them was mostly bookkeeping, and one of the three was not: it carried an open followup saying its EIGHT MUTATION SURVIVORS WERE NEVER ADJUDICATED, which the project's own rule forbids leaving. A fresh adjudicator was given it and re-swept the module rather than reading the report — AND THE REPORT WAS STALE ON BOTH COUNTS. Today `services/recurring.py` scores 76 mutants, 75 killed, ONE survivor, 98.7%, not 65/8/87.7%. SEVEN OF THE EIGHT WERE REAL GAPS and were closed on 2026-08-12 by `fab23cb`, out of FEATURE 013's CP8 — a different feature's hardening closed this fix's debt, and neither artifact knew about the other. The adjudicator proved it instead of assuming it: re-sweeping those exact sites with only those five tests deselected brought all seven back alive. Each maps to an explicit clause — AC-18 refuses an end date BEFORE the start, not on it; an amount ZERO OR NEGATIVE, not one centavo; a cadence LESS THAN one period, not one. The last survivor is a proven equivalent mutant, by an 8.800-case differential with a non-vacuity control. IT ALSO OVERTURNED THE OTHER OPEN NOTE: `row.amount = amount` in `retarget` was recorded as dead code, and it is not — it only ever looked dead on the recurring path, and `services/recurring.py` no longer calls `retarget` at all. Deleting it turns 4 backend tests and 12 acceptance scenarios red. THE THIRD FIX'S OPEN FOLLOWUP WAS SETTLED BY READING RATHER THAN WRITING: feature 006 AC-17 already said a payment may not be planned in a currency differing from the account's own, so planning in dollars was always in scope and the fix made the screen obey a criterion that predated it."
human_action_needed: no
recommended_next: "Feature 015 `fund-belongs-to-its-charge` — rebase its branch onto `main` (17 behind), write the ADR superseding 0043, then CP2. The migration rehearsal needs the owner (CHARTER §7)."
tracker_update: "local — three fixes closed; no feature status changes."
exit_criteria:
  - criterion: "the code being closed is actually in `main`"
    verified_by: tool
    met: true
    evidence: "Checked before touching any artifact rather than taken from the notes. `95f10d5` (expired session), `3cf13f4` (foreign-currency account), `0e75c93` (recurring in dollars), all on `main`. Corroborated in the source: `client.ts` carries SESSION_EXPIRED_MESSAGE and the 401 branch, `to-pay/page.tsx` imports `currencyHeldBy`/`currencyOf`, the create dialog derives currency reactively, and the recurring screen has a currency picker. ADR-0053 is `accepted` and supersedes 0052."
  - criterion: "every open followup is resolved or explicitly carried"
    verified_by: judgment
    met: true
    evidence: "Two were open. The foreign-currency one asked whether planning in another currency is in scope — settled by reading feature 006 AC-17, which already governs it, and by confirming the coverage gap it worried about is closed: all three screens now pick a foreign-currency account in their tests, and CHARTER §6 was amended the same day to require it. The recurring one asked for the eight survivors to be adjudicated on a fresh agent, and that is what was done."
  - criterion: "every survivor was read and judged, not counted"
    verified_by: judgment
    met: true
    evidence: "Eight, by a fresh adjudicator (`cp8-adjudicator-recurring`) on a re-run sweep in an isolated worktree, every rung green-gated first. Seven real gaps, each argued against a quoted clause of 007's AC-12/AC-14/AC-18 and each proven still-killable by deselecting the five tests that close them. One equivalent, proven by differential hashing over 8.800 cases with a non-vacuity control. No verdict of `unreachable`: reachability was checked through the API router, not only the service."
  - criterion: "the recorded figures describe the code that ships"
    verified_by: tool
    met: true
    evidence: "They did not, and were corrected rather than left. `mutation_score` moved from 0.877 to 0.987, and the original reading is kept in the notes with a header saying it is the 2026-08-11 sweep — because the gap between the two readings is the finding."
  - criterion: "no source changed"
    verified_by: tool
    met: true
    evidence: "This closure is artifacts only. The adjudicator worked in worktrees, removed them, and left `git diff` empty on the main checkout."
status: complete
---

# fix — close (the three of August 11)

## Lo que parecía papeleo y no lo era

Tres arreglos llevaban dos días en `hardened` con su código ya en `main`. Dos
eran, efectivamente, papeleo. El tercero llevaba escrito, con todas sus letras,
que **sus ocho sobrevivientes de mutación no estaban adjudicados** — que es
justo lo que la regla del proyecto no deja pasar.

## Lo que encontró el adjudicador

Volvió a barrer el módulo en vez de leer el reporte, **y el reporte estaba
viejo por partida doble**:

```
2026-08-11    65 mutantes    57 muertos    8 vivos    87,7 %
hoy           76 mutantes    75 muertos    1 vivo     98,7 %
```

**Siete de los ocho eran huecos reales** — y los cerró la CP8 de **otra
feature**, la 013, el 12 de agosto. Ninguno de los dos artefactos sabía del
otro. El adjudicador no lo dio por bueno: volvió a barrer esos sitios exactos
con solo esas cinco pruebas desactivadas, y los siete revivieron.

Cada uno contra una cláusula citada: el AC-18 rechaza una fecha de fin **antes**
del inicio, no en él; un monto **cero o negativo**, no un centavo; una cadencia
**menor que un período**, no uno.

El octavo sigue vivo y está bien que siga: equivalente probado por un
diferencial de 8.800 casos, con un control de no-vacuidad.

## Lo que además dio vuelta

`row.amount = amount` en `retarget` estaba anotado como código muerto. **No lo
está.** Solo parecía muerto por el camino de recurrentes, y ese camino ya no
existe: `services/recurring.py` no llama a `retarget`. Quedan dos llamadores
vivos y en ambos esa asignación es la única que corre. Borrarla pone en rojo 4
pruebas de backend y 12 escenarios de aceptación.

## La lección

Un artefacto que se cierra tarde no es solo ruido en la lista: **sus cifras
envejecen y siguen leyéndose como verdad.** Este decía 87,7 % con ocho huecos
abiertos cuando hacía un día que eran uno y 98,7 %.

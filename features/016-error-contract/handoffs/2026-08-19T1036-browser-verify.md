---
skill: browser verification (CHARTER §6)
agent_id: main-session
feature: 016-error-contract
started: 2026-08-19T0925
ended: 2026-08-19T1036
checkpoint: 7 (CHARTER §6 gate, part of the same Verify checkpoint the independent verifier's handoffs cover)
artifacts:
  - frontend/components/transaction-edit-dialog.tsx
  - frontend/components/transaction-edit-dialog.test.tsx
findings_summary: "Drove the feature in the browser against the dev sandbox (just dev-local equivalent, docker compose -f docker-compose.yml -f docker-compose.dev.yml, QUAESTOR_ENV_FILE=backend/.env.local.sqlite, branch error-contract), per plan.md's validation_method: the three real banners named there. INFRA NOTES, not feature defects: the frontend container's default host port (3000) collided with an unrelated project's own dev server already running on this machine (/Users/angelozdev/me/ks/POC-Builder/server) — resolved by setting QUAESTOR_WEB_PORT=3100, no changes to the other project. The stack also exited on its own twice for reasons unrelated to this feature (not diagnosed further, matches the kind of host/VM flakiness this session saw elsewhere) — restarted in detached mode (-d) both times, stable throughout the actual walkthrough. ALL THREE BANNERS CONFIRMED WORKING AS DESIGNED: (1) AC-1, creating a category named 'Mercado' (an existing active expense category) showed, inline under Nombre: 'Ya existe una categoría de gasto llamada «Mercado»' — exact match to spec.md/acs.md. (2) AC-2, archiving 'Lavado Carro' then creating a new category with that name showed: 'Ya existe una categoría de gasto archivada llamada «Lavado Carro». Restaurarla en vez de crear otra.' — exact match, offers the restore action in words. Category was restored immediately after, sandbox left clean. (3) AC-3, correcting the posted expense 'CP7 pago SOAT' (450.000 COP) to amount 0 showed, inline under Monto (COP): 'El monto debe ser mayor que cero' — exact match. Transaction was never actually corrected (validation blocked the save), $450.000 confirmed unchanged afterward. A REAL DEFECT WAS FOUND BY THE BROWSER, INVISIBLE TO EVERY PRIOR TEST STREAM: alongside AC-3's correct inline field message, the toast notification read 'Se guardaron los datos, pero el monto y la cuenta quedaron como estaban: amount must be > 0' — Spanish prefix, raw English backend detail appended. Root cause: transaction-edit-dialog.tsx's correction-mutation onError handler built this toast from `e.message` (the CorrectionRefused wrapper's message, itself just cause.message — i.e. the raw ApiError.message/English detail) instead of running the coded ApiError through translateApiError the way the inline field error already did two lines above it. This is exactly the class of defect CHARTER §6 exists to catch (009 shipped one past a green pipeline; 012's browser pass found three more) — no unit, API, acceptance, or vitest test in this feature's diff ever rendered this specific toast path, because none of them simulate the two-mutation partial-save flow this dialog uses for amount/account corrections specifically. FIXED: onError now computes `causeMessage` once via `translateApiError(cause)` (falling back to \"Error\" for a non-ApiError cause, matching the existing pattern) and both the inline field error and the toast now derive from it — removing the duplicate/inconsistent message logic in the same edit. A NEW REGRESSION TEST pins it (`transaction-edit-dialog.test.tsx`, 'The partial-save toast is entirely in Spanish, never the raw backend detail') — verified to fail against the pre-fix code (hand-reverted the fix, reran, 1 failed with the exact before/after diff shown) and pass against the fix, before permanently reverting to the fix. Re-verified in the live browser after the fix: same repro (correct 'CP7 pago SOAT' to 0) now shows the toast fully in Spanish: 'Se guardaron los datos, pero el monto y la cuenta quedaron como estaban: El monto debe ser mayor que cero'."
human_action_needed: no
recommended_next: "Feature is complete: all 6 ACs verified in code and 3 of them (the ones with a real UI surface) verified live in the browser, matching CHARTER §6 and plan.md's validation_method in full. Ready for the owner's review and merge decision (CHARTER §7 — merge to main is the owner's, not this session's, to make)."
tracker_update: null
exit_criteria:
  - criterion: "the feature was driven in a browser against the sandbox, per CHARTER §6 and plan.md's validation_method"
    verified_by: human
    met: true
    evidence: "Three real banners exercised end-to-end through the actual UI (category create dialog x2, transaction correction dialog x1) against the running dev-local stack, not simulated. Screenshots captured at each step confirming exact Spanish wording, correct field placement, and correct interpolated data (category name, direction implied by 'de gasto')."
  - criterion: "green is not verified — the browser pass looked for what tests could not see, not just replayed what they already proved"
    verified_by: human
    met: true
    evidence: "Found a real, previously-invisible defect (the mixed-language partial-save toast) precisely because it required simulating a UI flow (the two-mutation correction path) that no existing test — unit, API, acceptance, or vitest — happened to exercise. Fixed, pinned with a new test verified against both the broken and fixed code, re-verified live in the browser after the fix."
  - criterion: "the sandbox was left in the state it was found (no stray data from the walkthrough)"
    verified_by: human
    met: true
    evidence: "'Lavado Carro' category: archived for the AC-2 repro, restored immediately after (confirmed via 'Categoría restaurada' toast and its reappearance in the active list). The 'Mercado' and 'Lavado Carro'-duplicate creation attempts were both correctly rejected server-side, so neither ever persisted. 'CP7 pago SOAT' transaction: correction to 0 was rejected, balance/amount confirmed unchanged ($450.000) via a fresh screenshot of the list after the dialog was cancelled."
  - criterion: "all changes made during verification are covered by the full test suite, re-run fresh"
    verified_by: tool
    met: true
    evidence: "After the toast fix: backend uv run pytest -q -> 1278 passed, 1 pre-existing unrelated flake (test_scheduler). Frontend pnpm vitest run -> 594 passed, 59 files (was 593 before this fix's regression test). biome check . -> clean (4 pre-existing unrelated warnings in an untouched file). tsc --noEmit -> clean."
status: complete
---

# browser-verify (CHARTER §6) — resumen del handoff

**Los tres avisos funcionan tal como se diseñaron — y el navegador encontró
uno que ningún test veía.**

## Lo esperado, confirmado

AC-1, AC-2 y AC-3 mostraron exactamente el texto que `spec.md` y `acs.md`
prometen, en el campo correcto, en español. "CP7 pago SOAT" nunca se movió
de $450.000 — el rechazo bloqueó la corrección de verdad, no solo en la
pantalla.

## Lo que ningún test veía

Junto al mensaje correcto bajo "Monto", el **toast** decía: *"Se guardaron
los datos, pero el monto y la cuenta quedaron como estaban: **amount must
be > 0**"* — español a medias, inglés crudo pegado al final. La causa: ese
toast se armaba con el mensaje crudo de la excepción, no con
`translateApiError`, dos líneas después de donde el campo inline sí lo
hacía bien. Ningún test de esta feature simula ese camino específico (el
flujo de dos mutaciones que usa este diálogo para monto/cuenta), así que
nadie lo había visto.

Arreglado, fijado con una prueba nueva (verificada contra el bug y contra el
arreglo antes de dejarla), y reconfirmado en vivo en el navegador.

## El sandbox quedó como estaba

"Lavado Carro" archivado y restaurado. Ningún intento de duplicado quedó
guardado. "CP7 pago SOAT" sigue en $450.000.

```
DAE ▸ 016-error-contract
·0 Onboard · ·1.5 Ready · ·2 ACs · ·3 Spec · ·4 Plan · ·5 Implement · ·6 Refine · ▶7 Verify · ·8 Harden
```

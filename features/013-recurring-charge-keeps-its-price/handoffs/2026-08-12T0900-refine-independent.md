---
skill: refine
agent_id: refiner-independent
feature: 013-recurring-charge-keeps-its-price
started: 2026-08-12T0845
ended: 2026-08-12T0900
checkpoint: 6
artifacts:
  - backend/src/quaestor/services/recurring.py
  - backend/src/quaestor/services/planned.py
  - backend/src/quaestor/api/schemas.py
  - backend/src/quaestor/api/routers/transactions.py
  - backend/src/quaestor/migrations/versions/0017_two_obligations_go_back_to_the_price_the_merchant_charges.py
  - acceptance/handlers/recurring_price.py
  - frontend/app/(app)/recurring/page.tsx
  - frontend/app/(app)/to-pay/page.tsx
  - frontend/components/transaction-edit-dialog.tsx
  - frontend/lib/money.ts
findings_summary: "Independent re-review of the branch, no code changed. THE 0840 PASS IS CONFIRMED, not taken on trust: its three applied cleanups were each re-derived — `currencyForAccount`'s deletion (single call site, and its claimed behaviour table is right: accounts in flight + another account chosen returned pesos), `_require_account` written on `_account_holding` (the split is load-bearing — an obligation pointing at a retired account must still be editable), and `PriceCurrencyField` — and both of its declines stand. TWO FINDINGS IT MISSED. (1) A REAL DEFECT, frontend, new on this branch: `createMoney` (`useAmountBox`) lives in `RecurringPage` and never unmounts, and `create.onSuccess` resets `createForm` but not the box's `stated`. Create 99.900 COP on Nu, save, click Nuevo, pick DolarApp — `offerTheAccountsCurrency` reads the stale stated figure and writes US$31,79 into an amount box the owner left empty. `EditChargeForm` and `ConfirmPaymentForm` are keyed children and immune; the create form is the one that is not. No spec scenario and no vitest reaches it. (2) A CONTRACT CONTRADICTION needing the owner: acs.md AC-17 says the assistant keeps requiring the rule's currency to match its account and that the divergence stays written; the branch removed the guard from `create_recurring`, plan.md records that the assistant 'hereda la capacidad sin una línea', and spec.md AC-17 pins the opposite — parity. The MCP tool now accepts 400000.00 COP on a USD account. One of the two artifacts is wrong; both are contract, so refine cannot pick. THREE REUSE MISSES, all small and all real: `currencyOf` is a verbatim copy of `currencyHeldBy` with a different fallback (`money.ts:111-124`) — the exact class the 0840 pass deleted `currencyForAccount` for, left standing one function over; `revert_stored_prices` in migration 0017 is dead (never called — `downgrade()` re-inlines its loop), and `upgrade()` re-inlines `restate_stored_prices`'s, so one two-line loop exists four times; and the account-select + `offerTheAccountsCurrency` wrapper is duplicated verbatim between the two recurring dialogs (`dae_dup.py` flags 345-353 against 710-718), which is the shell around the `PriceCurrencyField` the 0840 pass extracted. EFFICIENCY IS CLEAN: `prices_by_transaction` really is one query per page — bounded by `wanted`, guarded on empty, and `from_one`/`from_written` route through the same helper, so no N+1 on any read path. Its docstring justifies the `active` filter with a cost that is true of the month-report path (ADR-0028, `active_recurring`) and false here, but the decision itself is the owner's from 2026-08-11 and spec.md pins it, so it is not mine to move. THREE PROPOSALS REJECTED INTERNALLY by the charter filter and never shown. Streams re-run from scratch, all green: 602 acceptance · 1181 backend · 529 vitest · import-linter 2 kept / 0 broken."
human_action_needed: yes
recommended_next: "/engineer.crap-analyzer for CP7 (Light Verify) — needs an agent_id differing from both main-session and refiner-independent."
tracker_update: "none — roadmap item already in-progress."
exit_criteria:
  - criterion: "the three review lenses (reuse, quality, efficiency) were applied to the branch's changed code"
    verified_by: inspection
    met: true
    evidence: "Scope was `git diff e2ba3ee..HEAD` — 41 files, of which the ten substantive source files above were read in full alongside `retarget`, `planned._require_account`, `db.get_session`, `mcp/tools/temporal.py` and `use-stated-amount.ts` to trace each changed call path to its ends. `dae_dup.py` ran over the repo and returned `status: ok` with 27 duplicate blocks; the eleven touching changed files were read individually rather than absorbed, and separated into newly-introduced (the two recurring-dialog pairs) from project-shape (the `field.state.meta.errors[0]` block, the to-pay/transaction-create-dialog pairs). Reuse produced three findings, quality six nits, efficiency one confirmation and one docstring correction."
  - criterion: "every proposal was checked against CHARTER.md before being shown"
    verified_by: inspection
    met: true
    evidence: "Three rejected internally and not presented. (1) Merging the create and edit dialogs into one form — same rejection the 0840 pass reached, nine untouched fields on a screen that writes money with no ADR behind it (CHARTER §6). (2) Dropping the `RecurringItem.active` filter in `prices_by_transaction` so a cancelled subscription keeps its AC-21 label — acs.md is silent on it but plan.md records the owner deciding it on 2026-08-11 and spec.md pins it, so it is a behaviour change and a category error for refine. (3) Adding a currency guard to the MCP surface to satisfy acs.md AC-17 — behaviour change, and it would build on a surface the owner has decided to deprecate. No code was changed at any point, so CLAUDE.md's comment prohibition was not exercised; the branch as it stands adds no `#` comments to any source file."
  - criterion: "the behaviour contract is unchanged — both test streams still green"
    verified_by: tool
    met: true
    evidence: "./run-acceptance-tests.sh → `602 passed, 1 warning in 38.23s`. cd backend && SESSION_SECRET=… uv run pytest -q → `1181 passed, 1 warning in 62.50s (0:01:02)`. cd frontend && pnpm exec vitest run → `Test Files 57 passed (57)` / `Tests 529 passed (529)`. cd backend && uv run lint-imports → `Analyzed 83 files, 251 dependencies.` / `Contracts: 2 kept, 0 broken.` Nothing was edited, so these are the branch as HEAD leaves it."
  - criterion: "breaking changes classified, and a graceful path installed where one is consumer-facing"
    verified_by: inspection
    met: true
    evidence: "No changes were made this pass, so no new breaks were introduced. The 0840 pass's one removal was re-checked: `currencyForAccount` was exported from lib/money.ts, `grep` over the frontend finds no remaining reference, and the repo is the only consumer (CHARTER §4 — local-only, no published surface), so removing it outright rather than shimming was right. The branch's two wire additions, `rule_amount` and `rule_currency` on `TransactionOut`, are additive and nullable, and `tests/api/test_read_path_characterization.py` already pins them."
status: complete
---

# CP6 — Refine, firmado por un agente que no escribió el código

El Principio 7 pide que la revisión la firme alguien distinto del que
implementó. Esta pasada rehízo la revisión desde el diff, sin leer el handoff de
las 0840 hasta el final, y **coincide con él en todo lo que aplicó**. Lo que
sigue es lo que además encontró.

## La pasada de las 0840, verificada una por una

| Cambio | ¿Se sostiene? | Cómo se comprobó |
|---|---|---|
| Borrar `currencyForAccount` | Sí | Un solo call site, hoy `currencyHeldBy(...) ?? tx.currency`; su tabla de comportamiento es correcta caso por caso |
| `_require_account` sobre `_account_holding` | Sí | La división carga peso: una obligación que apunta a una cuenta archivada tiene que poder editarse, y solo `_account_holding` lo permite |
| `PriceCurrencyField` | Sí, pero a medias | El interior quedó compartido; la cáscara que lo envuelve sigue duplicada (ver R3) |

Sus dos descartes también se sostienen: los 13 parámetros de `_apply_edit` son
un paso a través mecánico, y el bloque `field.state.meta.errors[0]` es la forma
de todo el frontend.

Se comprobó además, por si el cambio de `confirm_payment` había abierto algo:
`_tx.retarget(session, tx, account_id or tx.account_id, amount)` ahora corre
siempre, y `retarget` rechaza cuentas archivadas. **No es una regresión**: la
línea 245 de `planned.py` ya rechazaba lo mismo unas líneas después, con el
mismo mensaje. Solo se adelantó.

## Lo que la pasada de las 0840 no vio

### D1 — El monto de un recurrente ya creado se cuela en el siguiente (defecto real)

`createMoney` vive en `RecurringPage` y no se desmonta nunca. `create.onSuccess`
hace `createForm.reset(createDefaults)` pero el `stated` del cajón sigue ahí.

> Crea Hevy Pro por **99.900 COP** sobre Nu y guarda. Vuelve a «Nuevo» y elige
> **DolarApp**. La casilla del monto, que él dejó vacía, se llena sola con
> **US$ 31,79** — el precio del cobro anterior, convertido.

`offerTheAccountsCurrency` lee `stated.cents !== null` y ofrece. `EditChargeForm`
y `ConfirmPaymentForm` son hijos con `key` y se montan limpios; el formulario de
crear es el único que no. Ninguna escena del `spec.md` ni ningún vitest reabre el
diálogo, así que las tres suites verdes no lo ven.

Es de la misma familia que «nada puede mostrar una cifra que no va a usar»
(regla 2 de la 012, y uno de los *decision drivers* de la ADR-0053).

### D2 — La `acs.md` AC-17 dice lo contrario de lo que se construyó

| Artefacto | Qué dice |
|---|---|
| `acs.md` AC-17 | «El asistente **sigue exigiendo** que la moneda de la regla coincida con la de su cuenta… la divergencia queda escrita» |
| `plan.md` | «Al quitar la guarda del servicio **hereda la capacidad** sin una línea» |
| `spec.md` AC-17 | «The assistant is neither given anything nor taken anything away» — paridad |
| El código | `create_recurring` ya no compara; MCP acepta 400000.00 COP sobre una cuenta USD |

Los dos son contrato. Uno de los dos está mal escrito y **refine no puede
elegir cuál** — por eso `human_action_needed: yes`. La salida barata es corregir
la `acs.md`: el resultado que se construyó es el más simple, y la memoria del
dueño sobre no gastar alcance en paridad MCP apunta en esa dirección.

## Reuso — tres, pequeños y ciertos

**R1 — `currencyOf` es copia literal de `currencyHeldBy`** (`frontend/lib/money.ts:111-124`),
solo cambia el `??`. Debería ser `return currencyHeldBy(accounts, id) ?? "COP"`.
Es exactamente por lo que se borró `currencyForAccount`, una función más abajo.

**R2 — `revert_stored_prices` está muerta** (migración 0017, línea 80): nadie la
llama, y `downgrade()` vuelve a escribir su bucle. `upgrade()` hace lo mismo con
`restate_stored_prices`. Un bucle de dos líneas, cuatro veces.

**R3 — La cáscara del selector de cuenta está duplicada** entre los dos diálogos
de recurrentes (`dae_dup.py`: 345-353 contra 710-718, y la reja monto+moneda
382-403 contra 747-768). No es la fusión de diálogos que se rechazó — es el par
de campos del precio, que ya tiene la mitad extraída.

## Nits de calidad (no defectos)

- El docstring de `prices_by_transaction` justifica el filtro `active` con un
  costo que es cierto del informe del mes (ADR-0028, `active_recurring`) y falso
  aquí: la consulta ya está acotada por `wanted`. La decisión es del dueño y el
  `spec.md` la fija; lo que no describe esta función es la razón.
- `_apply_edit` vuelve a pedir la cuenta con `_account_holding` justo después de
  que `_require_account` se la devolviera y la tirara (`recurring.py:359-361`).
  Mismo mapa de identidad, cero consultas extra — solo dos búsquedas donde hay
  un valor.
- `RulePriceNote` compara con `=== null`; `== null` sobreviviría además a un
  payload donde el campo no venga.
- `RulePrice` en la lista usa `currencyOf`, que inventa pesos mientras la lista
  de cuentas viaja: un cobro USD sobre cuenta USD enseña un «≈ $…» espurio por
  un instante. Misma forma que se quitó de `currencyForAccount`.
- `_refusal()` en `acceptance/handlers/recurring_price.py` consume una vez y lee
  dos; la guarda `world.last_error in world.errors` costará de leer la próxima
  vez.
- La migración 0017 usa un docstring de atributo (PEP 257) sobre `_WAITING`.
  Es docstring, no comentario, así que pasa el CLAUDE.md — pero es el único del
  archivo.

## Eficiencia

`prices_by_transaction` **sí es una consulta por página**: un `select` acotado
por `wanted`, con salida temprana cuando ninguna fila viene de una regla, y
`from_one`/`from_written` pasan por el mismo helper. Ningún camino de lectura
hace N+1. Comprobado también que el informe del mes no tiene filas por
movimiento, así que la mitad de la AC-21 que nombra «el informe del mes» no
tiene dónde aterrizar — el `spec.md` la acotó al detalle del movimiento y eso es
coherente con la forma del reporte.

## Las cuatro corridas

```
./run-acceptance-tests.sh          → 602 passed, 1 warning in 38.23s
backend  uv run pytest -q          → 1181 passed, 1 warning in 62.50s
frontend pnpm exec vitest run      → 57 files, 529 tests passed
backend  uv run lint-imports       → Contracts: 2 kept, 0 broken
```

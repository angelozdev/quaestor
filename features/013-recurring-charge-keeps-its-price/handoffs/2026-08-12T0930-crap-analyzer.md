---
skill: crap-analyzer
agent_id: verifier-independent
feature: 013-recurring-charge-keeps-its-price
started: 2026-08-12T0905
ended: 2026-08-12T0930
checkpoint: 7
artifacts:
  - backend/src/quaestor/services/recurring.py
  - backend/src/quaestor/services/planned.py
  - backend/src/quaestor/api/schemas.py
  - backend/src/quaestor/migrations/versions/0017_two_obligations_go_back_to_the_price_the_merchant_charges.py
  - frontend/lib/money.ts
  - frontend/app/(app)/recurring/page.tsx
  - frontend/app/(app)/to-pay/page.tsx
  - frontend/components/transaction-edit-dialog.tsx
findings_summary: "CRAP computed over the branch diff against real coverage, both halves. Backend 94.46% (5505/5828), one function above the threshold of 20: `_apply_edit` at 26.2 (complexity 23, 81.8%). Frontend 90.68% statements / 88.56% branches, three above: `RecurringPage` 40.3 (cx 37, 86.6%), `EditTransactionForm` 32.0, `ToPayPage` 28.9. `lib/money.ts` is 100% lines AND branches, `prices_by_transaction` 100%, `_require_chargeable` 100%. THE MONEY RISK ON THIS BRANCH IS LOW, and that is a measured claim, not a shrug: the invariant is checked at one place that all four write gates reach; an account's currency is immutable (`accounts.update_account` takes name and type only), so an obligation that pays itself cannot be diverged from behind; every aggregate that reads a rule converts by the rule's own currency (`month.py:29,59,235`, `funds.py:97,141`) and every aggregate that reads a movement goes through `agg.to_cop_cents(tx)`; and the two lines that actually move a balance are safe by construction — `occurrences.py:98` runs only when `is_auto`, which the invariant pins to the account's currency, and `confirm_payment` routes through `retarget`, which refuses to cross a currency without a restated figure. ONE RANKED RISK, frontend: `ConfirmPaymentForm` falls back to the CHARGE's currency when the accounts query has not resolved (`to-pay/page.tsx:106`) — a fallback that was harmless until this branch, because until this branch a charge always held its account's currency. Submit in that window on a 99.900 COP charge over DolarApp and the form sends 9_990_000 with the USD account; `retarget` takes the figure at face value and debits US$ 99.900,00 from a US$ 1.000 balance. Narrow window, severe amount, and no test on either screen covers the null-accounts branch. TWO TEST GAPS WORTH CLOSING, both real. (1) `PriceCurrencyField.onPick` — the «Moneda del precio» control, the one control that expresses this feature's headline rule — is executed by NO test: `recurring/page.tsx:398-400` (edit) and `:776-778` (create) are both zero-covered, and the eleven vitest scenarios reach it only through the account picker. (2) `schemas.py:206`, the AC-21 seam service→wire, is executed by no test either: `prices_by_transaction` has five service tests, `RulePriceNote` has a vitest over a fixture that already carries `rule_amount`, and the only characterization assertion pins `(None, None)`. I PROBED THAT SEAM LIVE rather than reporting a hole: it is correct today — a posted US$32,10 charge returns `(9990000, 'COP')`, the waiting charge and the switched-off rule both return `(None, None)`, and the balance moved 100000→96790 cents. So it is an unpinned contract, not a defect. NOTHING WAS CHANGED: no source, no test, no spec, no `.build/`. The one script written lives in the scratchpad. Every CP6 finding was re-verified as fixed at HEAD, not taken on trust: `currencyOf` now delegates to `currencyHeldBy`, `revert_stored_prices` is gone from migration 0017, `startANewCharge` clears the create box and a vitest pins it, and acs.md AC-17 now says what was built."
human_action_needed: no
recommended_next: "/engineer.atdd-mutate for CP8 (Harden) — mutation testing on `backend/src/quaestor/services/recurring.py`, which plan.md §Test strategy 4 opts into for the first time, paying the debt ADR-0052 left. Expect the survivors to land in `_apply_edit`'s field-application branches (lines 314, 319, 329, 333, 364) and in the raises at 322/326/341, which this pass measured as unreached by pytest; a survivor INSIDE `_require_chargeable` would be the silver hole back and is the one that must not stand. CP8 NEEDS AN agent_id DIFFERING FROM main-session (implement), refiner-independent (CP6) AND verifier-independent (CP7) — the gate compares CP6/7/8 against the CP5 implementer, and CHARTER §6 Principle 7 wants the three signatures apart."
tracker_update: "progress.md — CP7 row marked done, breadcrumb advanced to CP8, handoff log extended. Roadmap item already in-progress, untouched."
exit_criteria:
  - criterion: "CRAP was computed over the code this branch changed, against coverage the repo's own tooling produced"
    verified_by: tool
    met: true
    evidence: "Scope `git diff --merge-base main` (merge-base e2ba3ee, 42 files). Frontend coverage from the repo's own `@vitest/coverage-v8`: `pnpm exec vitest run --coverage --coverage.reporter=lcov` → `Statements 90.68% (7774/8573) · Branches 88.56% (1573/1776) · Functions 69.73% (666/955)`. Backend has no coverage dep in pyproject.toml, so coverage.py was run as an ephemeral overlay that writes nothing to the repo — `uv run --with pytest-cov pytest -q --cov=src/quaestor --cov-report=json` → `TOTAL 5828 stmts, 323 missing, 94%` (94.46%), `1181 passed, 1 warning in 101.41s`. `compute_crap.py` then ran once per half against those files. Backend, threshold 20, one finding: `_apply_edit` CRAP 26.2 (cx 23, 81.8%); below it `create_recurring` 11.0 (cx 11, 96.3%), `confirm_payment` 9.0 (cx 9, 96.6%), `prices_by_transaction` 8.0 (cx 8, 100%), `from_tx` 3.0 (cx 3, 85.7%), `_require_chargeable` 3.0 (cx 3, 100%), `update_recurring` 3.0 (100%), `restate_stored_prices` 2.0 (cx 1, 0% — the acceptance suite runs it, not pytest). Frontend, three findings: `RecurringPage` 40.3 (cx 37, 86.6%), `EditTransactionForm` 32.0 (cx 32, 97.9%), `ToPayPage` 28.9 (cx 28, 89.6%); below them `EditChargeForm` 18.1, `ConfirmPaymentForm` 10.0 (100%), `boxesFor`/`offerTheAccountsCurrency`/`RulePrice`/`RulePriceNote` 3.0 each (100%), `PriceCurrencyField`/`currencyHeldBy`/`currencyOf` 2.0 each (100%). Per-file uncovered counts: `lib/money.ts` 0 lines and 0 branches; `recurring/page.tsx` 69 lines / 27 branches; `to-pay/page.tsx` 27 / 19; `transaction-edit-dialog.tsx` 4 / 12; `services/recurring.py` 92.1%; `services/planned.py` 96.1%; `api/schemas.py` 99.8%; `api/routers/transactions.py` 100%; migration 0017 96.2%."
  - criterion: "the findings are ranked by what they cost in money, not by score"
    verified_by: inspection
    met: true
    evidence: "The two highest CRAP scores are both ranked below a function scoring 10.0 with 100% coverage, and the reason is written out. `RecurringPage` at 40.3 is the top score and is not the top risk: its 69 uncovered lines are 23 copies of the three-line `field.state.meta.errors[0]` block, the `onError` handlers, and the delete/skip/restore dialogs — none of which decide a figure. `ConfirmPaymentForm` scores 10.0 at 100% line coverage and IS the top risk, because line 106's `?? charge.currency` fallback is a branch coverage does not distinguish and is the one place a wrong figure reaches `retarget`. The backend was traced rather than scored: `grep` over `balance +=`/`delta_balance` found the only two write sites (`occurrences.py:98`, `planned.py:246`), each was read to its guard, and `accounts.update_account` was read to confirm currency is immutable — which is what makes the one-place invariant sufficient rather than merely tidy."
  - criterion: "each named gap says the scenario, the file and what would go wrong"
    verified_by: inspection
    met: true
    evidence: "Six gaps written up in the body with file:line, ranked, and each labelled real risk or bookkeeping. The two called real were both checked past the metric: `PriceCurrencyField.onPick` was traced through `useAmountBox.write` (`lib/use-stated-amount.ts`) to confirm it relabels rather than converts — correct, and unpinned; the AC-21 seam was executed live against an in-memory SQLite through `create_recurring` → `materialize_due` → `confirm_payment` → `TransactionOut.from_one`/`from_txs`, printing `POSTED -> rule_amount: 9990000 rule_currency: COP`, `WAITING -> None None`, `SWITCHED OFF -> None None`, `balance: 96790`, which downgrades it from suspected defect to unpinned contract. The four called bookkeeping are `planned.py:239` (covered by acceptance, not pytest), `_apply_edit`'s field branches (long-standing, and CP8's target), the to-pay «upcoming» section wrapper (its `ToPayRow` is covered through «overdue»), and `RulePrice`'s peso fallback flicker (cosmetic, already a CP6 nit)."
  - criterion: "nothing was changed — the three suites are the branch as HEAD leaves it"
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh` → `602 passed, 1 warning in 36.98s`. `cd backend && SESSION_SECRET=… uv run pytest -q` → `1181 passed, 1 warning in 54.43s`. `cd frontend && pnpm exec vitest run` → `Test Files 57 passed (57)` / `Tests 530 passed (530)`. `just lint` → `Analyzed 83 files, 251 dependencies.` / `Contracts: 2 kept, 0 broken.` / biome `Found 4 warnings. Found 1 info.` — all four pre-existing (`lib/use-url-filters.ts:64 noExplicitAny` and siblings, none on this branch). No source file, test, spec or `.build/` artifact was written; `git status` is clean but for this handoff and progress.md. The one script written for the AC-21 probe lives in the session scratchpad, outside the repo."
status: complete
---

# CP7 — Verificación ligera: dónde está el riesgo, medido

CRAP mide dos cosas a la vez: qué tan enredada está una función y qué tan poco
la toca una prueba. Sirve para ordenar, no para concluir. Lo que sigue empieza
por los números y termina donde los números no llegan.

## Los números

| Mitad | Cobertura | Comando |
|---|---|---|
| Backend | **94,46%** (5505/5828) | `uv run --with pytest-cov pytest --cov=src/quaestor` |
| Frontend | **90,68%** líneas · **88,56%** ramas · 69,73% funciones | `pnpm exec vitest run --coverage` |

El backend no declara `pytest-cov` en `pyproject.toml`, así que se corrió como
capa efímera de `uv`: no escribe nada en el repo.

### Backend — una sola función sobre el umbral de 20

| Función | cx | cob. | CRAP |
|---|---|---|---|
| `_apply_edit` (`recurring.py:288`) | 23 | 81,8% | **26,2** |
| `create_recurring` | 11 | 96,3% | 11,0 |
| `confirm_payment` (`planned.py:195`) | 9 | 96,6% | 9,0 |
| `prices_by_transaction` | 8 | **100%** | 8,0 |
| `from_tx` (`schemas.py:188`) | 3 | 85,7% | 3,0 |
| `_require_chargeable` | 3 | **100%** | 3,0 |

### Frontend — tres sobre el umbral

| Función | cx | cob. | CRAP |
|---|---|---|---|
| `RecurringPage` (`recurring/page.tsx:470`) | 37 | 86,6% | **40,3** |
| `EditTransactionForm` | 32 | 97,9% | 32,0 |
| `ToPayPage` (`to-pay/page.tsx:180`) | 28 | 89,6% | 28,9 |
| `EditChargeForm` | 18 | 92,3% | 18,1 |
| `ConfirmPaymentForm` | 10 | **100%** | 10,0 |

`lib/money.ts` no tiene **ni una línea ni una rama** sin cubrir. Es el módulo
donde vive toda la aritmética de conversión de la feature, y es el único de los
tocados que está entero.

## El riesgo es bajo, y esto es por qué

No es un encogimiento de hombros. Se comprobó, no se supuso:

1. **El invariante se comprueba en un solo sitio** y los cuatro portones lo
   alcanzan. `_require_chargeable` tiene 100% de cobertura y sus dos únicos
   llamadores —`create_recurring` y `_apply_edit`— también están cubiertos ahí.
2. **La moneda de una cuenta no se puede cambiar.** `accounts.update_account`
   recibe `name` y `type`, nada más. Una regla que se cobra sola no puede
   quedar discrepando *por detrás*, que es la única forma de romper un
   invariante comprobado al escribir.
3. **Todo agregado convierte por la moneda de la fila que lee.**
   `month.py:29,59,235` y `funds.py:97,141` usan `item.currency`; todo lo que
   lee movimientos pasa por `agg.to_cop_cents(tx)`; `month_planned_expense`
   excluye explícitamente `recurring_id != None`. Ninguna suma mete una cifra
   extranjera en un total.
4. **Las dos líneas que mueven un saldo están protegidas por construcción.**
   `occurrences.py:98` solo corre si `is_auto`, y el invariante fija esa moneda
   a la de la cuenta. `planned.py:246` viene detrás de `retarget`, que se niega
   a cruzar de moneda sin una cifra reescrita.

Ese cuarto punto es la razón de ser de la AC-2, y sigue en pie.

## El riesgo que sí queda

### `ConfirmPaymentForm` cae a la moneda del cobro cuando no conoce la cuenta

`frontend/app/(app)/to-pay/page.tsx:106`

```ts
const currency = currencyHeldBy(accounts, accountId) ?? charge.currency
```

Ese `??` era inofensivo hasta esta rama, porque hasta esta rama **un cobro
siempre traía la moneda de su cuenta**. Ahora no.

> Hevy Pro espera 99.900 COP sobre DolarApp, que tiene US$ 1.000. El dueño abre
> «Confirmar» antes de que `listAccounts` responda. La casilla dice
> «Monto real (COP)» y trae 99.900. Si confirma en esa ventana, el formulario
> manda `amount: 9_990_000` con la cuenta en dólares; `retarget` ve que cruza de
> moneda, toma la cifra al pie de la letra y escribe `tx.amount = 9_990_000,
> tx.currency = USD`. **El saldo baja US$ 99.900,00 en vez de US$ 32,10.**

La ventana es angosta —la consulta de cuentas arranca al montar la página y el
diálogo se abre con un clic— y el desenlace es enorme. Ninguna prueba, en
ninguna de las dos pantallas, entra por la rama donde `accounts` todavía no
llegó. `RulePrice` (`recurring/page.tsx:200`) tiene la misma forma con
`currencyOf`, pero ahí solo parpadea un «≈ $…» de más: no escribe nada.

## Los huecos de prueba, ordenados

### 1 — «Moneda del precio» no la usa ninguna prueba · riesgo real

`recurring/page.tsx:398-400` (editar) y `:776-778` (crear), ambos con cero
cobertura. Es el **único control que dice de qué se trata la feature**: el
precio es del comercio y se elige aparte de la cuenta (AC-3). Las once escenas
de vitest llegan a la moneda por el selector de cuenta, nunca por este.

Su cuerpo relabela sin convertir —`money.write(money.stated.cents, currency)`,
comprobado leyendo `useAmountBox` en `lib/use-stated-amount.ts`— y eso es lo
correcto. Si algún día convirtiera, o vaciara los centavos, el dueño escribe
99.900, elige «Dólares» y guarda una regla de **US$ 99.900,00**; si esa regla se
cobra sola, el motor la debita así cada periodo. Nada en verde lo vería.

### 2 — La costura de la AC-21 no la ejecuta nadie · riesgo real, defecto ninguno

`api/schemas.py:206` — `out.rule_amount, out.rule_currency = rule_price` — es la
**única línea del backend sin cubrir en todo `schemas.py`**. Alrededor:
`prices_by_transaction` tiene cinco pruebas de servicio, `RulePriceNote` tiene
un vitest sobre un fixture que ya trae `rule_amount` puesto, y la única
aserción de caracterización fija `(None, None)`. El servicio y la pantalla están
probados; **la costura entre los dos no**.

En vez de reportar el hueco, se ejecutó:

```
born charge: 9990000 COP recurring_id= 1
WAITING       -> rule_amount: None     rule_currency: None
confirmed: 3210 USD balance: 96790
POSTED        -> rule_amount: 9990000  rule_currency: COP
from_txs      -> rule_amount: 9990000  rule_currency: COP
SWITCHED OFF  -> rule_amount: None     rule_currency: None
```

Está bien hoy. Es un contrato sin fijar, no un defecto: se puede borrar la línea
o equivocar la llave y las tres suites siguen verdes.

### 3 — `planned.py:239` no lo alcanza pytest · contabilidad

`amount = None`, la rama que se toma cuando el pago cruza de moneda: la única
línea que esta rama cambió en `planned.py`. La suite de aceptación sí la corre
(AC-7, AC-8, AC-9), así que el comportamiento está fijado — solo no en la capa
que corre en el bucle corto.

### 4 — Las asignaciones de `_apply_edit` · contabilidad hoy, CP8 mañana

Sin alcanzar por pytest: 314 (`name`), 319 (`mode`), 329 (`interval_unit`),
333 (`interval_count`), 364 (`category_id`), y los rechazos de 322, 326 y 341.
El `mode` lo cubre aceptación. El resto es un punto delgado viejo de
`update_recurring`, no algo que trajo esta rama — pero es exactamente donde va a
sobrevivir un mutante cuando CP8 corra.

### 5 — La sección «Esta semana» de «Por pagar» · contabilidad

`to-pay/page.tsx:298-311` no la renderiza ninguna prueba; solo se prueba
«Vencidos». `ToPayRow` sí queda cubierta por ese camino, así que lo que falta es
la envoltura.

### 6 — El parpadeo de `RulePrice` · contabilidad

`currencyOf` cae a pesos mientras viajan las cuentas, así que una regla USD
sobre cuenta USD enseña un «≈ $…» espurio por un instante. Nit de la CP6, sigue
en pie, no toca plata.

## Lo que la CP6 dejó pedido, verificado en HEAD

No se dio por bueno: se leyó.

| Hallazgo CP6 | Estado en HEAD |
|---|---|
| D1 — el monto del cobro anterior se colaba en el siguiente | **Arreglado**: `startANewCharge` (`page.tsx:511-514`) vacía formulario y cajón; lo fija un vitest nuevo, que es el test 530 |
| D2 — `acs.md` AC-17 contradecía lo construido | **Resuelto**: la AC-17 ahora dice que la paridad sale gratis por la capa de servicios |
| R1 — `currencyOf` copiaba a `currencyHeldBy` | **Arreglado**: `money.ts:128` delega |
| R2 — `revert_stored_prices` muerta en la 0017 | **Arreglado**: `grep` no la encuentra |
| R3 — cáscara duplicada entre los dos diálogos | Sigue; es forma, no plata |

## Las corridas

```
./run-acceptance-tests.sh          → 602 passed, 1 warning in 36.98s
backend  uv run pytest -q          → 1181 passed, 1 warning in 54.43s
frontend pnpm exec vitest run      → 57 files, 530 tests passed
just lint                          → Contracts: 2 kept, 0 broken; 4 warnings preexistentes
```

Nada se editó. El script de la sonda vive en el scratchpad de la sesión, fuera
del repo.

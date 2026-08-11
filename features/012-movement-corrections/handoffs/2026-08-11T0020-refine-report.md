# CP6 refine — the independent report, verbatim

Produced by 15 fresh agents: 5 diverse lenses, 9 adversarial skeptics prompted
to refute by default, 1 synthesizer. `main-session` dispatched, consolidated and
put the two decisions to the owner. It wrote none of this, and none of the fixes.

```
raised 44   deduped 43   verified 9   refuted 3   survived 6   unverified 34
```

The owner decided, on reading it: correcting accepts an account and an amount
together in one currency (as confirming already does), and a same-currency
transfer gets a real amount control on screen.

---

## Consolidated review — feature 012, `movement-corrections`

I re-read every line cited below against the branch and re-ran the backend repro myself. Six findings arrived; they collapse to **four distinct defects** (three of the six are the same bug found by three independent lenses) plus one hazard and a short refactor list.

**This is not a clean pass.** The feature's two headline criteria, AC-7 and AC-8, have no working path from the screen. Every same-currency correction returns 422.

---

### Charter filter

I rejected **2** proposals outright and do not list them as work:

- One proposal wanted `move_to_account` to start accepting an amount when the destination holds the *same* currency. That is exactly the rule `retarget`'s docstring states as accepted design (`backend/src/quaestor/services/transactions.py:557-559` — "A destination in the same currency leaves the figure alone… correcting refuses one, confirming takes it as the real amount"). Changing it is an ADR amendment, not a code edit. It reappears below as an owner *decision*, not as a fix.
- One proposal wanted the edit dialog's account select seeded with archived accounts. AC-15/AC-16 were deliberately scoped: AC-16 is `@backend` and its own text says "Korea holds no movements in production, so this decides a rule rather than a case." Widening the offered list contradicts AC-15.

No proposal below adds a comment, a migration, or anything to the MCP assistant, and none rebuilds a balance from movements.

---

## USER-FACING DEFECTS

### D1 — Every same-currency correction is refused with 422. AC-7 and AC-8 do not work on the screen.
**`frontend/components/transaction-edit-dialog.tsx:100-105`** (with `backend/src/quaestor/api/routers/transactions.py:136` and `backend/src/quaestor/services/transactions.py:583-585`)

Three lenses found this independently, and two more in the unverified pool. **Five-way agreement — the strongest signal in the pass.**

`accountId` and `amount` are seeded from the row (lines 77-78), so the `?? undefined` never fires and the dialog always sends *both* keys whenever `restated` is true. The router branches on `account_id` first, so any body carrying it goes to `move_to_account(..., amount=body.amount)`; `_retarget_only` then raises because `retarget` returned False for a same-currency destination. The `correct_amount` branch at router line 138 is unreachable from this dialog.

I reproduced it against the real service on in-memory SQLite (Nu Débito COP → RappiCard COP, expense of $93.558):

```
move same-currency WITH amount   -> ValidationError an amount is only stated when the account holds another currency
amount fix via account branch    -> ValidationError an amount is only stated when the account holds another currency
```

What the owner suffers: he moves a Tigo charge from Nu Débito to RappiCard, or retypes it from $93.558 to $95.200, presses **Guardar**, and gets a red toast reading *"an amount is only stated when the account holds another currency"* — an English sentence about currency, in a Spanish UI, for a correction involving one currency. Because `await correctTransaction(...)` runs **before** `updateTransaction(...)`, the payee, date, category, tags and meta he edited in the same dialog are thrown away too. The only correction the product can complete today is a move to an account in a *different* currency.

Nothing catches it. `grep` over `backend/tests/` finds no test of `/correction` at all. The vitest test at `frontend/components/transaction-edit-dialog.test.tsx:217` asserts *byte-for-byte the rejected body* — `toHaveBeenCalledWith(1, { account_id: 2, amount: 5_000_000 })`, with fixture accounts 1 and 2 both COP — and passes only because `correctTransaction` is mocked at line 15. The acceptance handlers call `move_to_account` with `amount=None`, the one shape the dialog never produces.

**Blast radius.** The fix is to build the body from the diff — `account_id` only when it changed, `amount` only when it changed. That reaches `correct_amount` for the first time from the UI, so the router's third branch goes live. The vitest assertion at line 217 must be corrected, or it will defend the defect. One combination remains unrepresentable and needs the owner's call (see the decision below): **account and amount changed together in the same currency**. Note that `confirm_payment` already supports exactly that combination — `spec.md`'s AC-2 scenario "The account and the real amount are corrected in the same act" moves Nu Débito → RappiCard for $420.000, both COP — so the correction path is today strictly weaker than the confirm path.

**Owner decision required:** should correcting accept an account *and* an amount in one currency, the way confirming already does? Yes means amending the rule stated in `retarget`'s docstring and ADR-0051. No means the dialog issues two saves or refuses the combination visibly.

---

### D2 — A same-currency transfer's amount can no longer be corrected anywhere, and the dialog no longer even shows what the leg is worth.
**`backend/src/quaestor/services/transactions.py:664`** and **`frontend/components/transaction-edit-dialog.tsx:87-88, 140`**

Four lenses agreed. **Strong signal.**

`correct_transfer` and `_transfer_sides` are reachable only through the router branch at `routers/transactions.py:132-135`, which fires on `sent`/`received`. The single frontend caller sends only `account_id`/`amount`; `CorrectionBody.sent`/`received` (`frontend/lib/api/types.ts:328-329`) are never populated by anything. `correct_amount` refuses a transfer outright (`transactions.py:641-642`), so the pair-level verb is the *only* route to a transfer's figure — and it has no caller.

Meanwhile the diff made the screen worse. `git diff` on the dialog shows two lines deleted from the summary block:

```
-  {tx.type} · {formatCents(tx.amount, tx.currency)} · cuenta #{tx.account_id}
-  <p className="mt-1 text-xs">Para cambiar monto/cuenta, elimina y vuelve a crear.</p>
+  <p>{tx.type}</p>
```

For a same-currency transfer leg, `amountRidesWithTheMove` is false, so the replacement `MoneyInput` (line 158) never renders. The leg's own figure is now displayed **nowhere** — `formatCents` survives in the file only inside `TransferPairInfo`, which prints the *counterpart's* amount (line 64).

What the owner suffers: he opens either half of the $500.000 Préstamos a terceros → Nu Débito transfer. He sees an account picker, the counterpart's amount, the word "transfer", no figure of his own, and no instruction. Before this feature he at least had a true sentence telling him to delete and recreate. AC-11's worked example — restating either half to $520.000 — cannot be performed by a human. All 22 same-currency production transfers are in this state.

Note the spec tagged AC-11/AC-12's scenarios `@backend`, so the acceptance suite is green and honest. But `plan.md:185-190` reserved a screen arm for AC-13 explicitly (`AC-13 (backend arm)` in slice 3, screen arm in slice 4) and reserved **nothing** for AC-11/AC-12 — so the gap was not a deliberate deferral.

**Blast radius.** Either give the dialog a transfer branch that sends `{ sent, received }` (must be that shape — `correct_amount` 422s on a transfer), which activates `correct_transfer`, `_transfer_sides` and the `TransferImbalance` equality rule from the UI for the first time; or, if transfer amounts are deliberately out of this release, restore one short line saying a transfer's amount is corrected by deleting the pair. Whichever is chosen, the leg's own amount should be shown again — that regression is independent of the decision.

---

### D3 — Clearing the amount and saving reports success while nothing changed.
**`frontend/components/transaction-edit-dialog.tsx:86, 103`**

Two lenses agreed.

`parseMoneyToCents` returns `null` for empty text (`frontend/components/money-input.tsx:14`), so an emptied field sets `amount = null`. `restated` (line 86) becomes true, but `amount: amount ?? undefined` drops the key from the JSON body. The request becomes `{account_id: <unchanged>}` → `move_to_account(amount=None)` → same currency → no refusal → `_restate` computes a zero delta → commit → **200**. `onSuccess` fires `toast.success("Transacción actualizada")`.

The amount `Input` sits inside the `<form>` element and is not part of the TanStack form (`transaction-edit-dialog.schema.ts` validates only payee/category/date/notes/tags/metaId), so pressing Enter in the emptied field submits immediately with no validation.

What the owner suffers: he clears the Monto field of a $45.000 expense meaning to retype it, saves out of habit, is told the transaction was updated, and the figure is still $45.000.

**Blast radius.** Refuse a null amount client-side while the field is shown. Do **not** push this to the server: AC-21 requires that a correction changing nothing changes nothing, and the sibling call site `frontend/app/(app)/to-pay/page.tsx:115` uses the same `?? undefined` legitimately — there an omitted amount means "confirm at the planned amount". The fix must not be copied to both sites.

---

### D4 — The dialog reads a movement's currency from the account list instead of from the movement.
**`frontend/components/transaction-edit-dialog.tsx:85`**

Three lenses agreed.

`const currency = currencyOf(accountsQuery.data, accountId)` — and `currencyOf` (`frontend/lib/money.ts:72`) returns `"COP"` on a miss, by its own docstring. `tx.currency` sits two lines away, authoritative and unused except as a comparison operand. That `currency` drives the label (line 160), the `MoneyInput` scaling (line 161), `amountRidesWithTheMove` (line 87) and the conversion on account change (lines 150-152).

The transient is deterministic, not hypothetical: the only caller is `frontend/app/(app)/transactions/page.tsx`, which warms `qk.accounts(true)` (lines 125, 280) — a different cache key. Nothing populates `accounts(false)`, so opening the edit dialog always fires a cold fetch. A DolarApp expense of US$87,52 first renders as **"Monto (COP)" showing "88"**, then flips to "US$ 87.52". For a USD transfer leg the amount field appears and then vanishes as `amountRidesWithTheMove` flips.

On its own that is a visible flash — the parent's `amount` stays 8752 and `restated` stays false. The reason it matters is the interaction: if `listAccounts(false)` errors (`retry: 1`), `accountsQuery.data` stays undefined permanently while `EntitySelect` remains interactive, and `parseMoneyToCents` in COP mode strips the decimal point — typing "87.52" yields 875200 cents. Today D1 masks that (the POST is refused). **Once D1 is fixed, the amount-only branch goes live and that same typing posts `{amount: 875200}` to `correct_amount`, restating a US$87,52 charge as US$8.752,00 with no way for the backend to know.**

**Blast radius.** `const currency = accountId === tx.account_id ? tx.currency : currencyOf(accountsQuery.data, accountId)` — one expression, no comment, no ADR touched (ADR-0031 governs the rate, not which currency a record carries). **Apply this in the same change as D1, not after it.** Do not extend it to seeding the select with archived accounts (rejected above).

---

## HAZARD — reported, not proposed as work

**Two commits behind one button.** `transaction-edit-dialog.tsx:99-113` runs `correctTransaction` (which commits inside `_restate`, `transactions.py:543`) and then `updateTransaction` (a separate PATCH that can still be refused by `resolve_for_movement` or `refuse_bad_meta`), under a single `onError` and a single toast. If the second write fails, the balance has already moved between two accounts while the owner reads a red toast and reasonably concludes nothing was saved. ADR-0051 chose a separately named path precisely so the most dangerous write in the app is not hidden inside the most innocent one; on screen they are one click again.

I am reporting this as a hazard rather than a defect because I could not construct a refusal the dialog's own controls produce deterministically — the category select is already filtered by direction, and `update_transaction` no longer clears a category via `None`. The generic case (PATCH fails for any reason after the POST committed) is real. If it is touched at all, order the balance-safe write first so a rejected edit leaves the money alone.

---

## REFACTORS — owner decides, none of these hurt him today

1. **No test exists at the REST boundary.** `POST /transactions/{tx_id}/correction`'s four-branch dispatch is executed by nothing: the 53 `@backend` scenarios bind at the services layer, the one over-the-wire scenario posts `{"amount": 1}` and is refused at auth, and the vitest suite mocks the client. `plan.md:230-232` named this risk verbatim, citing 009's `FNF:12 / FNH:0`. **This is the root cause of D1 and D2, not a separate finding** — it is why they shipped. Recommend a `backend/tests/api/test_corrections.py` covering the four body shapes as part of the D1 fix, not as separate work.
2. **A third `currencyOf`** still lives at `frontend/components/transaction-create-dialog.tsx:66`, semantically identical to the extracted `lib/money.ts:68` and used three times. The extraction the plan justified left two definitions in the tree.
3. **The account-picker conversion handler is copy-pasted** into `transaction-edit-dialog.tsx:147-153` and `to-pay/page.tsx:254-262`, and the two copies already disagree on a cleared amount (edit skips conversion, to-pay falls back to `confirming.amount`). `plan.md:110` promised "one helper; the two screens differ in nothing."
4. **`require_positive` was extracted but not finished.** The byte-identical inline check survives at `transactions.py:92`, `:304`, `planned.py:78` and `:267` — the last three lines from the branch that was converted.
5. **Three docstrings state something the code does not do.** `correct_transfer` (`transactions.py:675`) promises `ValidationError` for unequal halves; line 684 raises `TransferImbalance` — different class, 409 not 422. `move_to_account` (`:591`) opens with "Both balances move by the same figure", which is false for the cross-currency case the same docstring goes on to describe. `_refuse_transfer_collision` (`:619`) reports a same-account collision as a `TransferImbalance`, an arithmetic error class for an identity problem.
6. **`_restate` re-reads accounts it just read** (`:529-535`) and guards against a `None` account that cannot occur — every id comes from a foreign key or from `_require_account`. Measured cost is 7-11 statements per correction at n≤2 rows; no user feels it. Worth knowing it is an unreachable branch inside the one module the plan opted into mutation testing.

---

## Latent, not a defect today

`confirm_payment` (`backend/src/quaestor/services/planned.py:226`) routes transfers to `_materialize_planned_transfer` without passing `account_id`, while `to-pay/page.tsx:117` always sends it and `_obligations` (`planned.py:106`) puts transfers in the queue. Confirming a planned transfer against a different account would report "Pago confirmado" and charge the planned account anyway. I verified no live path creates a planned transfer — `plan_payment` makes expenses only and `recurring.py:99-100` refuses a transfer type — so this bites only legacy rows. A one-line refusal in `confirm_payment` would close it permanently; it is not urgent.

---

**Recommended order:** D1 + D4 + the REST test as one change (D4 becomes money-losing the moment D1 lands). Then D3. Then the D2 decision, which is the owner's: give same-currency transfers a real amount control, or put the honest instruction back.

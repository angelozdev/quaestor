# Acceptance specs — 016 error-contract

Formalizes `acs.md` (6 ACs, approved by the owner 2026-08-18) as standard
Gherkin.

## Two streams, because `feature.md` declares `acceptance_stream: mixed`

`@backend` scenarios pin the wire — the `code` and the data that cross from
the server. Untagged scenarios pin what the owner actually sees on screen —
the field the message lands under, in the exact Spanish words — and bind to
vitest instead of pytest, per `run-acceptance-tests.sh`'s handling of a
mixed stream.

**The Spanish sentence itself is never a `@backend` fact for AC-1/AC-2/AC-3.**
Per ADR-0059, the domain exception keeps the English message it always had —
only `code` and `data` are new — and the Spanish text is built entirely on
the client, from `frontend/lib/api/error-catalog.ts`. So the `@backend`
scenarios for those three ACs assert `code`/`data` only; the Spanish wording
is asserted once, correctly, in each AC's untagged scenario. **AC-4 is the
one exception, on purpose**: Pydantic's own `type`/`ctx` are translated
server-side in `_format_validation` (a separate, cheaper design the plan
chose because Pydantic hands the split apart for free), so AC-4's Spanish
text genuinely is a `@backend`-observable fact.

**Corrected here in CP5** (2026-08-18): the first draft of AC-1/AC-2/AC-3's
`@backend` scenarios asserted "told, in Spanish" at the service layer, which
this project's `@backend` scenarios always read via `str(exc)` on the raised
exception (same as feature 008's `_refusal`). That is incompatible with
ADR-0059 as accepted — it would have forced the domain exception itself to
speak Spanish, which also would have leaked into MCP's `domain_error_text`
(explicitly promised untouched). Found by the implementer, resolved with the
owner: the exception stays English, the `@backend` scenarios below assert
`code`/`data` only, and the already-correct untagged scenarios keep the
Spanish assertion where it belongs.

## AC-6 has no Gherkin scenario, on purpose

Pinning "an error nobody could have predicted still answers in Spanish and is
logged" acceptance-style would mean building a new fault-injection mechanism
this suite has never needed — forcing a real, arbitrary crash mid-request.
Decided with the owner during this checkpoint (2026-08-18): a backend unit
test on the exception handler itself does the job without inventing test
infrastructure for one case. `implement`/`refine` own that test; it is not
generated from this file.

## A note this spec carries but does not act on

`features/008-mandatory-categories/spec.md`'s AC-13 already pins "the user is
told that category already exists" and "the user is offered to restore the
archived category" — both stay true and are **not touched here** (never edit
another feature's `spec.md` without permission). Their **step handlers**
(`acceptance/handlers/mandatory_categories.py`,
`then_told_category_exists` / `then_offered_to_restore`) currently assert on
English substrings (`"exist"`, `"already"`, `"restore"`), which will stop
matching the moment AC-1/AC-2 below ship Spanish text — the same
fix-or-accept fallout every consolidation row has produced. Flagged for
`/engineer.plan`: those two handlers need to check the new `code` instead of
an English substring, which also makes them stop being fragile to wording.

---

Feature: Un error viaja con código y datos, y la pantalla arma la frase en español

## AC-1 — Categoría duplicada activa se rechaza en español, con el nombre real

```gherkin
@backend
Scenario: A duplicate expense-category name is refused with a stable code and its data
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Transporte"
  When the user tries to record an expense of 900000.00 COP from "Bancolombia" paying "Avianca" creating the category "Transporte"
  Then the registration is rejected
  And the refusal carries a stable code identifying it as a duplicate category
  And the refusal carries the category's name and direction as data, not baked into a sentence
```

```gherkin
Scenario: The duplicate-category refusal appears under the Name field, in Spanish
  Given the app is open
  And an expense category "Transporte" exists
  When the owner tries to create another expense category named "Transporte"
  Then the Name field shows "Ya existe una categoría de gasto llamada «Transporte»"
```

## AC-2 — Categoría duplicada archivada sugiere restaurar en vez de crear otra

```gherkin
@backend
Scenario: A name held by an archived category is refused with its own code and its data
  Given an account "Bancolombia" in COP with balance 500000.00 COP
  And an expense category "Transporte"
  And the user archives the category "Transporte"
  When the user tries to record an expense of 900000.00 COP from "Bancolombia" paying "Avianca" creating the category "Transporte"
  Then the registration is rejected
  And the refusal carries a stable code identifying it as an archived-category duplicate, distinct from the code for an active-category duplicate
  And the refusal carries the category's name and direction as data, not baked into a sentence
```

```gherkin
Scenario: The archived-category refusal offers to restore it, in Spanish
  Given the app is open
  And an archived expense category "Transporte" exists
  When the owner tries to create another expense category named "Transporte"
  Then the Name field shows "Ya existe una categoría de gasto archivada llamada «Transporte». Restaurarla en vez de crear otra."
```

## AC-3 — Corregir un movimiento a un monto de cero o menos se rechaza en español

```gherkin
@backend
Scenario: Correcting an expense to zero is refused with a stable code
  Given today is 2026-08-18
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user corrects that expense to 0.00 COP
  Then the correction is rejected
  And the refusal carries a stable code identifying it as an invalid amount
  And "Nu Debito" has balance 900000.00 COP

@backend
Scenario: Correcting an expense to a negative amount is refused the same way
  Given today is 2026-08-18
  And an account "Nu Debito" in COP with balance 1000000.00 COP
  And an expense category "Servicios"
  And the user registers an expense of 100000.00 COP from "Nu Debito" paying "Tigo" in category "Servicios"
  When the user corrects that expense to -50000.00 COP
  Then the correction is rejected
  And the refusal carries a stable code identifying it as an invalid amount
```

```gherkin
Scenario: The correction dialog shows the Spanish refusal under the Amount field
  Given the app is open
  And a posted expense of 100000.00 COP from "Nu Debito" paying "Tigo" exists
  When the owner opens the correction dialog and sets the amount to 0
  Then the Amount field shows "El monto debe ser mayor que cero"
```

## AC-4 — Lo que rechaza Pydantic también llega en español

```gherkin
@backend
Scenario: Declaring a fondo naming no category is refused in Spanish
  When the user submits a fondo with no category, the fixed rule, and an amount of 50000.00 COP
  Then the declaration is rejected
  And the user is told, in Spanish, that the category is required
```

## AC-5 — Un error sin código todavía responde con el detalle real, nunca un genérico

```gherkin
@backend
Scenario: A rejection with no code yet still tells the truth, in whatever language it always has
  Given no TRM has been set
  And a recorded expense of 50000.00 COP
  When the user views the current month's report
  Then the report is not shown
  And the user is told, in English as before, that no TRM was set
```

---

## AC-6 — Un error que nadie previó responde con un código fijo, y queda en logs

No Gherkin scenario — see "AC-6 has no Gherkin scenario, on purpose" above.
Pinned instead by a backend unit test on the exception handler registered in
`api/errors.py`: an arbitrary exception in, `code: internal_error` and the
fixed Spanish message out, the real exception recorded via `logging`, never
forwarded to the response body.

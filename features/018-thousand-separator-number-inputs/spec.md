# Acceptance specs — 018 thousand-separator-number-inputs

Formalizes `acs.md` (8 ACs, approved 2026-08-20) as standard Gherkin.

**Frontend-only, per ADR-0045.** Every AC is about what the field shows and
what it saves — no backend behavior changes, no new endpoint, no schema touch.
All eight scenarios are untagged and bind to vitest, per ADR-0045's decision
that a frontend acceptance criterion binds to a colocated test rather than a
mocked pytest stream. Cursor position (AC-3) is observable in jsdom via the
input element's selection range, so no `@browser` tag is needed here — nothing
in this feature depends on layout, width or wrapping.

**Two test files.** AC-1 through AC-7 are properties of the shared `MoneyInput`
component itself, bound to a new `money-input.test.tsx`. AC-8 is that every
screen gets the formatting for free because they all share that one component
— bound to the existing `transaction-create-dialog.test.tsx`, which already
renders a `MoneyInput` for the amount field, as a proof of wiring rather than a
re-test of AC-1's formatting rule.

---

Feature: Los montos separan los miles al escribir

## AC-1 — El monto en pesos separa los miles mientras se escribe

```gherkin
Scenario: Typing a peso amount shows the thousand separator live
  Given the user is entering an amount in Colombian pesos
  When the user types "1000000"
  Then the amount shown is "1.000.000"
```

## AC-2 — El monto en dólares separa los miles sin tocar el punto decimal

```gherkin
Scenario: Typing a dollar amount shows the thousand separator without touching the decimal point
  Given the user is entering an amount in US dollars
  When the user types "1000.5"
  Then the amount shown is "1,000.5"
```

## AC-3 — Editar en medio del número no salta el cursor al final

```gherkin
Scenario: Editing a digit in the middle of a long amount keeps the cursor next to it
  Given the user is entering an amount in Colombian pesos
  And the amount shown is "1.500.000"
  When the user inserts a digit right after the first "5"
  Then the cursor stays right after the digit just inserted
```

## AC-4 — Un monto chico no muestra separador de más

```gherkin
Scenario: A small amount shows no separator
  Given the user is entering an amount in Colombian pesos
  When the user types "500"
  Then the amount shown is "500"
```

## AC-5 — Pegar un número ya formateado se lee igual que pegar los dígitos solos

```gherkin
Scenario: Pasting an already-formatted amount reads the same as pasting the bare digits
  Given the user is entering an amount in Colombian pesos
  When the user pastes "1.000.000"
  Then the amount shown is "1.000.000"
  And the amount saved is 1000000 pesos
```

## AC-6 — Escribir letras u otros símbolos se ignora igual que hoy

```gherkin
Scenario: Typing letters mixed with digits ignores the letters
  Given the user is entering an amount in Colombian pesos
  When the user types "abc1000abc"
  Then the amount shown is "1.000"
```

## AC-7 — El formato es solo visual — el monto guardado no cambia

```gherkin
Scenario: The saved amount survives a round trip through the formatted display
  Given the user typed "1500000" into an amount field in Colombian pesos
  When the amount is saved and the field is shown again with that saved amount
  Then the amount shown is "1.500.000"
  And the amount saved is 1500000 pesos
```

## AC-8 — Toda pantalla que pide un monto lo separa automáticamente

```gherkin
Scenario: The transaction amount field separates thousands without any screen-specific change
  Given the user opens the dialog to create a transaction in Colombian pesos
  When the user types "1000000" into the amount field
  Then the amount shown is "1.000.000"
```

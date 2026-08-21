---
title: "El saldo inicial de un fondo respeta el mes en que se dijo"
slug: fund-opening-balance
number: 019
status: done
autonomy_level: medium
branch: fund-opening-balance
area: budget
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: fund-opening-balance
acceptance_stream: mixed
relevant_adrs: [0043]
created: 2026-08-20
intake: roadmap
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más una pasada en el navegador (CHARTER §6): crear un fondo en agosto declarando que ya tiene $500.000, confirmar que julio lee $0 y agosto lee $500.000 (no antes); luego, simulando lo que el assistant escribiría con set_fund(balance=...), confirmar que la cifra queda fechada al mes en que se ejecuta el cambio y no se vuelve a leer en meses anteriores."
---

# El saldo inicial de un fondo respeta el mes en que se dijo

## Outcome

El formulario de crear un fondo permite decir cuánto ya tiene ahorrado,
fechado al mes de arranque que el dueño ya eligió en la misma pantalla. Y lo
que el assistant escribe después con `set_fund(balance=...)` queda fechado al
mes en que se dice — nunca a uno pasado. El fondo deja de contestar el mismo
número en todos los meses cuando alguien declaró un saldo.

## Por qué

Decidido por Angelo el 2026-08-05 como ADR-041 (producto), cerrando la
enmienda del anchor de ADR-0043. Con los números de esa decisión: un fondo que
pide $200.000/mes, si en enero se declara que ya tiene $500.000 —

| Mes | Debería leer | Hoy lee |
|---|---|---|
| Diciembre | $0 — nada se había declarado todavía | $500.000 |
| Enero | $500.000 | $500.000 |
| Febrero | $700.000 | $500.000 |
| Marzo | $900.000 | $500.000 |

Solo acierta en el mes en que se escribió, e inventa plata en el pasado.

**Dos hallazgos cerraron la decisión.** La pantalla no tiene ningún campo para
esto — ni al crear, ni para editar — así que decirlo por el assistant es hoy
la ÚNICA vía que existe, no una de dos. Y ni YNAB ni Actual Budget tienen un
saldo sin fecha: el presupuesto ES mes a mes, la plata se asigna a la columna
de un mes y de ahí rueda — no hay nada que fechar porque nada flota.

## Scope

**Dentro:**

- Campo de saldo inicial en el formulario de CREAR fondo, fechado al mes de
  arranque que el dueño ya eligió en esa misma pantalla. `create_fund` ya
  soporta `opening_balance` y ya lo fecha bien — solo falta el campo.
- Fechar al mes actual lo que llega por `set_fund(balance=...)` — hoy no
  fecha nada, y el fold lo lee como válido para cualquier mes que se consulte.
- Escenarios de aceptación para la rama del anchor: mutation dejó 3
  sobrevivientes ahí (`stated_for > year_month` invertido, y sus dos
  returns) porque ningún escenario fecha un anchor hoy.

**Fuera (ya decidido en ADR-041, no se reabre):**

- **No se agrega un diálogo de editar el saldo desde la tabla de fondos.** La
  decisión deja esa vía en el assistant, fechada siempre al mes actual —
  nunca elegible a mano.
- **No se toca `create_fund(opening_balance=...)`** — ya fecha correctamente
  al mes de arranque.
- **El assistant.** Se va a deprecar (misma decisión que en 013/014/015) — no
  se le agrega superficie nueva; se corrige el fechado que ya tiene por
  dentro, sin tocar `mcp/format.py` ni el tool en sí.

## Related code / design pointers

- `backend/src/quaestor/services/funds.py` — la rama del anchor
  (`anchor_month`, `anchor_amount`, `stated_for` vs. `year_month`),
  `create_fund`, `set_fund`.
- `frontend/app/(app)/funds/create-form.tsx` — el formulario de crear fondo,
  sin campo de saldo inicial hoy.
- `docs/decisions/product-decisions.md` — ADR-041 (la decisión completa, con
  la tabla de meses).
- `docs/adr/0043-*` — balance derivado; el anchor es la única excepción.
- `.engineer/consolidation.md` — C23, donde se midió el hallazgo.

## Riesgos

Bajo — sin migración (`anchor_month` ya existe, nullable). El riesgo real es
de comportamiento: la rama del anchor no tiene ningún escenario hoy (por eso
sobrevivió a mutation), así que hay que fijar el "antes/después" con cuidado
para no dejar otra combinación sin probar.

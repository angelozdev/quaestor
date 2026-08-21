---
slug: thousand-separator-number-inputs
number: 018
title: Los montos separan los miles al escribir
status: done
autonomy_level: medium
branch: thousand-separator-number-inputs
roadmap_ref: null
acceptance_stream: frontend
relevant_adrs: [0060]
size: small
owner: angelozdev
tracker_ref: local
---

## Outcome

Al escribir un monto en cualquier formulario de plata (crear/editar transacción,
transferencia recibida, metas, fondos), el campo muestra el número con
separador de miles en vivo — así se ve de un vistazo si es 10.000, 100.000 o
1.000.000, sin cambiar el valor que se guarda.

## Por qué

El dueño no siempre distingue a simple vista cuántos ceros escribió. Un typo de
un cero de más o de menos en un monto es un error caro y silencioso — el campo
actual no da ninguna pista visual de la magnitud mientras se escribe.

## Scope

- **Adentro:** `MoneyInput` (el componente compartido) — usado en crear/editar
  transacción, transferencia recibida, metas, fondos. Formato de miles en vivo
  mientras el usuario escribe, en ambas monedas (COP: `1.000.000`; USD: mismo
  separador de miles en la parte entera, con el punto decimal intacto).
- **Afuera:** campos numéricos que no son plata (p. ej. "Orden" en tags y
  grupos de categoría) — decisión explícita del usuario, esos números son
  chicos y no se prestan a la misma confusión.
- **Afuera:** cambiar el valor guardado, el redondeo, o cualquier regla de
  negocio de `parseMoneyToCents` — es un cambio de presentación, no de dato.

## Charter signals

- Screen que escribe plata (CHARTER §6) → se prueba en un navegador real antes
  de darlo por hecho, con cuenta en moneda extranjera (USD) además de COP.

## Related code / design pointers

- `frontend/components/money-input.tsx` — el componente a modificar
  (`parseMoneyToCents`, `centsToText`, el `useState` de texto local).
- Consumidores: `frontend/components/transaction-create-dialog.tsx`,
  `transaction-edit-dialog.tsx`, `transfer-received-field.tsx`,
  `frontend/app/(app)/metas/*.tsx`, `frontend/app/(app)/funds/create-form.tsx`.

## Riesgos

- Bajo — cambio de presentación en un solo componente compartido. El riesgo
  principal es que el cursor salte de posición al insertar/quitar separadores
  mientras el usuario escribe en medio del texto.

## Validation method

Default (acceptance + unit) + CHARTER §6 manual browser check — probar
escribiendo un monto con muchos dígitos en COP y en USD, incluyendo edición en
medio del texto (no solo al final).

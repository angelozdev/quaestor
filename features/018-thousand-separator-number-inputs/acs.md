---
ac_count: 8
high_priority_count: 4
discovered: 2026-08-20
---

## AC-1: El monto en pesos separa los miles mientras se escribe

**Priority:** High
**Type:** Happy path

Al escribir un monto en un campo de plata en pesos (COP), el campo muestra un
punto cada tres dígitos desde la derecha a medida que se escribe — por
ejemplo, escribir `1000000` se ve como `1.000.000`. El valor que se guarda no
cambia: sigue siendo el mismo número de pesos que sin el separador.

## AC-2: El monto en dólares separa los miles sin tocar el punto decimal

**Priority:** High
**Type:** Happy path

Al escribir un monto en un campo de plata en dólares (USD), el campo muestra
una coma cada tres dígitos en la parte entera, y el punto sigue siendo el
separador decimal tal como se escribe hoy — por ejemplo, escribir `1000.5` se
ve como `1,000.5`. El valor guardado no cambia.

## AC-3: Editar en medio del número no salta el cursor al final

**Priority:** High
**Type:** Edge case

Si el usuario inserta o borra un dígito en medio de un monto largo ya
formateado (por ejemplo, corrige el `5` en `1.500.000`), el cursor queda al
lado del dígito que estaba editando — no salta al final del campo.

## AC-4: Un monto chico no muestra separador de más

**Priority:** Medium
**Type:** Edge case

Un monto de menos de mil (por ejemplo `500`) se ve igual que hoy, sin ningún
punto o coma de más al principio.

## AC-5: Pegar un número ya formateado se lee igual que pegar los dígitos solos

**Priority:** Medium
**Type:** Edge case

Si el usuario pega un monto que ya trae separadores (por ejemplo pega
`1.000.000` copiado de otro lado), el campo lo entiende igual que si hubiera
pegado `1000000` — no duplica ni pierde ceros.

## AC-6: Escribir letras u otros símbolos se ignora igual que hoy

**Priority:** Medium
**Type:** Errors

Escribir una letra u otro símbolo no numérico en el campo se ignora, sin
mostrar un error ni un valor inválido — mismo comportamiento que existe hoy.

## AC-7: El formato es solo visual — el monto guardado no cambia

**Priority:** High
**Type:** Cross-cutting

El separador de miles es puramente una forma de mostrar el número mientras se
escribe. El monto que efectivamente se guarda y se manda al servidor es
exactamente el mismo que se guardaría hoy, sin el separador — un ida y vuelta
(escribir → guardar → volver a mostrar) siempre reproduce el mismo monto.

## AC-8: Toda pantalla que pide un monto lo separa automáticamente

**Priority:** Medium
**Type:** Cross-cutting

Como todas las pantallas que piden un monto de plata (crear/editar
transacción, transferencia recibida, metas, fondos) usan el mismo campo
compartido, el separador de miles aparece en todas ellas sin que cada pantalla
tenga que cambiar nada por su cuenta.

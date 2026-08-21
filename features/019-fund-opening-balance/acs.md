---
ac_count: 6
high_priority_count: 4
discovered: 2026-08-20
---

## AC-1: Declarar el saldo al crear el fondo, desde la pantalla

**Priority:** High
**Type:** Happy path

Al crear un fondo, el formulario permite decir cuánto ya tiene ahorrado. Esa
cifra queda fechada al mes de arranque que el dueño eligió en la misma
pantalla.

## AC-2: Lo declarado al crear rige hacia adelante, mes a mes

**Priority:** High
**Type:** Happy path

Un fondo que pide $200.000/mes, creado en enero declarando que ya tiene
$500.000: en enero muestra $500.000, en febrero $700.000, en marzo $900.000 —
la cifra declarada se suma a lo que el fondo va pidiendo cada mes.

## AC-3: Declarar un saldo nuevo después de creado el fondo lo fecha al momento en que se dice

**Priority:** High
**Type:** Happy path

Cuando el dueño le dice al assistant que un fondo ya existente ahora tiene
cierta plata, esa cifra queda fechada al mes en que se lo dice — nunca a un
mes que el dueño elija.

## AC-4: Un mes anterior a cuando se declaró un saldo no lo ve

**Priority:** High
**Type:** Edge case

Un fondo al que se le declaró $500.000 en enero muestra $0 en diciembre — el
mes anterior a la declaración no se entera de una plata que todavía no se
había dicho.

## AC-5: Declarar un saldo nuevo reemplaza al anterior por completo

**Priority:** Medium
**Type:** Edge case

Si el dueño declara un saldo y después declara otro, el segundo reemplaza al
primero entero — mes y monto — sin sumar ni conservar rastro del primero.

## AC-6: Crear un fondo sin declarar saldo se comporta igual que hoy

**Priority:** Medium
**Type:** Edge case

Dejar el campo de saldo inicial en blanco al crear un fondo no cambia nada —
el fondo arranca en $0, exactamente como sucede hoy sin este feature.

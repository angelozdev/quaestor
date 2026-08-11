---
title: "Un cobro recurrente guarda el precio del comercio, no la moneda de la cuenta"
slug: recurring-charge-keeps-its-price
number: 013
status: ready
autonomy_level: medium
branch: recurring-charge-keeps-its-price
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: recurring-currency-independent-of-account
acceptance_stream: mixed
relevant_adrs: [0031, 0035, 0036, 0038, 0045, 0051, 0052]
created: 2026-08-11
intake: discuss
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más una pasada en el navegador contra el entorno de prueba con una cuenta en dólares — y la migración corrida sobre una copia restaurada antes de tocar producción (CHARTER §7)"
---

# Un cobro recurrente guarda el precio del comercio, no la moneda de la cuenta

## Outcome

Una regla recurrente guarda **el precio que cobra el comercio**, aunque la cuenta
que la paga tenga otra moneda. Hevy Pro cuesta 99.900 COP al año y se debita de
DolarApp: la regla dice 99.900 COP. Cuando llega la fecha el cobro no se registra
solo — aparece en «por pagar» con la conversión ya propuesta, el dueño escribe lo
que el banco de verdad debitó, y el movimiento guarda esa cifra y solo esa.

El precio deja de desviarse porque nunca fue una conversión: es el número que el
comercio anuncia, y sigue siendo cierto el año que viene.

## Scope

- **La regla puede tener una moneda distinta a la de su cuenta.** La columna ya
  existe en la tabla; hoy las puertas de escritura la mantienen igual a la de la
  cuenta a la fuerza. Se quita esa atadura en crear y en editar reglas
  recurrentes.
- **Un cobro cuya moneda no es la de su cuenta nunca se registra solo.** Cae en
  «por pagar» con la cifra convertida propuesta a la tasa única (ADR-0031), para
  que el dueño la acepte o la reemplace. El motor no convierte y no publica.
- **El movimiento guarda solo lo que salió**, en la moneda de la cuenta. Ninguna
  tasa se congela por movimiento — ADR-0031 queda intacta, y el precio en pesos
  vive en la regla, no en el movimiento.
- **La ADR que reemplaza a la 0052.** Ayer se decidió que la moneda sigue a la
  cuenta y nunca se declara aparte, con el argumento de que un campo aparte
  «solo podría coincidir de más o contradecir de menos». Este feature es el
  contraejemplo: el precio y el débito son dos cosas distintas y las dos son
  ciertas. `retarget` sigue siendo el contrato para corregir un movimiento ya
  registrado, que es donde nació; lo que se cae es su extensión a las reglas.
- **La migración de las dos reglas que hoy están mal.** Hevy Pro pasa a 99.900
  COP al año y Smart Fit a 120.000 COP al mes, las dos siguen cobrándose a
  DolarApp. **Los precios se cargan, no se calculan**: convertir 30,22 USD a la
  tasa de hoy da 94.951 COP y no 99.900, porque la tasa con la que se escribieron
  (≈3.306) ya no existe en ninguna parte.
- **Fuera de alcance:** las otras dos puertas de escritura (movimiento suelto y
  pago planeado). Ahí no hay deriva — cuando escribes la cifra ya sabes cuál es.
  La deriva es estructural solo cuando el número tiene que estar correcto meses
  por adelantado.
- **Fuera de alcance:** que el motor convierta y publique solo. Se consideró y se
  descartó en el discuss: un día sin tasa cargada dejaría de cobrar, y la cifra
  registrada sería la conversión de la app en vez de lo que el banco debitó.

## Lo que ya está resuelto y no hay que construir

- **Elegir la cuenta al confirmar.** La feature 012, mergeada hoy, ya lo permite.
  «Cualquier cuenta» está hecho; falta «cualquier moneda».
- **Corregir un cobro ya registrado.** También 012: `POST /transactions/{id}/correction`
  prueba su propia aritmética. Una ocurrencia ya planeada en la moneda vieja se
  corrige por ahí, una a una, que es lo que ADR-0052 ya prometía.
- **La columna de moneda en la tabla de recurrencias.** Existe. Esto no es un
  cambio de esquema para la regla — la migración solo reescribe dos filas.

## Decidido en el discuss (2026-08-11)

| | |
|---|---|
| Quién convierte el día del cobro | el dueño, sobre la cifra que la app propone |
| Qué recuerda el movimiento | solo los dólares que salieron; ADR-0031 intacta |
| Dónde vive el precio en pesos | en la regla, no en el movimiento |
| Alcance | reglas recurrentes; no las otras tres puertas |
| Las dos reglas mal guardadas | las migra el feature, con los precios cargados |
| ADR-0052 | se reemplaza, no se acota |

## Charter signals

- **Migración sobre datos reales.** CHARTER §7 exige presencia del dueño y
  respaldo fresco; el manifiesto ya topa `backend/src/quaestor/migrations/**` en
  autonomía `low` sin importar el nivel del feature.
- **Una pantalla que escribe plata se prueba contra una cuenta en otra moneda**
  (CHARTER §6, decidido ayer). Este feature *es* ese caso, así que la regla
  aplica de lleno en vez de ser un extra.
- **Verde no es verificado** (CHARTER §6): se maneja en el navegador antes de
  darlo por hecho.
- Las pantallas hablan inglés al rechazar hasta que salga `id:error-contract`.
  Conocido, anotado, no bloquea.

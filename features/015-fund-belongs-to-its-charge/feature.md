---
title: "Un fondo cuelga del cobro que llena, no de la categoría"
slug: fund-belongs-to-its-charge
number: 015
status: ready
autonomy_level: medium
branch: fund-belongs-to-its-charge
area: funds
owner: angelo
assignee: local
tracker_ref: local
acceptance_stream: mixed
relevant_adrs: [0028, 0031, 0043, 0046, 0054]
created: 2026-08-12
intake: discuss
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más un ensayo de la migración contra una copia restaurada de producción con el dueño delante: los cuatro fondos de suscripciones se convierten en uno por cobro, y la suma de lo que piden los nuevos tiene que ser exactamente la que pedían los viejos — 686.063,64 + 17.465,23 + 277.488,57 + 127.572,22. Ninguna otra cifra del mes puede moverse."
---

# Un fondo cuelga del cobro que llena, no de la categoría

## Outcome

En Recurrentes, un cobro se **marca como fondo**. Marcarlo crea el fondo, atado a
ese cobro, y desde entonces ese fondo aparta mes a mes para él y solo para él.

```
🛡️ Seguro del Carro   pide 636.363   = 7.000.000 ÷ 11 meses hasta julio 2027
```

Cuando el cobro se paga, el fondo empieza el ciclo siguiente solo.

## Por qué

**El dueño no encuentra la función donde la busca.** Registra el Seguro del Carro
a 7.000.000 al año en Recurrentes y la pantalla no dice nada. Para apartar mes a
mes hay que ir a Fondos, pulsar «Nuevo fondo», elegir la categoría y elegir la
regla — cuatro pasos y saber de antemano que existe.

Pedido textualmente el 2026-08-12:

> «Me gustaría como usuario tener en la vista de recurrentes como un check, como
> marcarlo como fondo o distribuirlo como fondo cuando coloco algo que sea años»

> «pero yo quiero un fondo por cada item no por cada categoría»

**Y hay una razón técnica que empuja en la misma dirección.** Hoy el fondo cuelga
de la categoría y adivina: cuando salen 447.300 de 🛡️ Auto Insurance,
`_settled_by_spending` asume que pagaron el cobro **más próximo** y mueve el
fondo al ciclo siguiente. Es una heurística por monto y por fecha.

Medido el 2026-08-12: **`Transaction.recurring_id` ya existe y ya se usa**
(`services/month.py:91` cuenta los turnos pagados por él). Todo pago hecho por el
motor dice qué cobro saldó. Un fondo atado al cobro puede leerlo en vez de
adivinar.

**Esta feature no cambia la aritmética del reparto** — la 014 la midió contra
producción y funciona. Cambia de qué cuelga el fondo, y con eso reemplaza una
adivinanza por un dato.

## Lo que tiene que ceder

**«Una categoría lleva un fondo»**, que fijó la ADR-0043 y que la 003 defendió en
su AC-25 (*«dos fondos sobre una categoría serían dos formas de bajar el mismo
titular»*). 🛡️ Auto Insurance pasa a llevar dos, uno por cobro. **La ADR-0043 se
sustituye, no se enmienda.**

El argumento original sigue en pie para las otras dos reglas: dos fondos `fixed`
sobre una categoría sí serían dos formas de bajar el mismo titular. Lo que cambia
es que dos fondos atados a **cobros distintos** no se pisan — cada uno cubre plata
distinta, y ahora el pago dice cuál.

## Scope

**Dentro:**

- Un fondo puede colgar de un cobro recurrente en vez de una categoría.
- Recurrentes gana la marca, y marcar crea el fondo.
- El saldado deja de adivinarse: lo dice `recurring_id` del pago.
- La pantalla de Fondos muestra una fila por cobro, con el desglose que construyó
  la 014.
- La migración de los fondos de suscripciones que ya existen.

**Fuera:**

- **Las reglas `fixed` y `average`.** Siguen colgando de la categoría y siguen
  siendo una por categoría. Esta feature parte el noun; no lo unifica.
- **El gasto tecleado a mano.** Un movimiento escrito por el dueño no trae
  `recurring_id`. Ya está archivado como `link-a-payment-to-the-charge-it-settled`
  y esta feature debe funcionar sin él, no esperarlo.
- **Metas.** Se midió la cercanía en el discuss: una meta es algo con nombre,
  fuera de toda categoría, que termina; un fondo por cobro se renueva y baja el
  titular de su categoría. La 009 separó las dos cosas a propósito (ADR-0046).
- **El asistente.** Se va a deprecar; misma decisión que en la 013 y la 014.

## El cambio de comportamiento que el dueño va a notar

**Hoy un fondo de categoría recoge los cobros nuevos solo.** Si mañana registra un
tercer cobro anual en 🛡️ Auto Insurance, el fondo lo reparte sin que haga nada.

**Después, no.** Cada cobro se marca. Es el mismo reclamo abierto que tiene Actual
Budget con sus `#template schedule {NAME}`: la plantilla nombra un cobro y no
recoge los que llegan después. Se le dijo al dueño el 2026-08-12 antes de que
decidiera, y decidió igual.

De 5 filas en Fondos pasa a ~8.

## Decisiones tomadas en el discuss

| | Decisión | Cuándo |
|---|---|---|
| 1 | El fondo cuelga del **cobro**, no de la categoría | 2026-08-12 |
| 2 | Marcar el cobro **es** lo que crea el fondo — no un aviso con enlace | 2026-08-12 |
| 3 | Se promueve ya, antes de terminar la 014 | 2026-08-12 |

## Related code / design pointers

- `backend/src/quaestor/services/funds.py` — `_obligations`,
  `_settled_by_spending` (la adivinanza que esto reemplaza), `_charge_month_for`,
  `_ask_from_obligations`, `_refuse_a_second_fund` (la AC-25 que cae)
- `backend/src/quaestor/services/month.py:91` — dónde ya se lee `recurring_id`
- `backend/src/quaestor/domain/models.py` — `Fund`, `RecurringItem`, `Transaction`
- `frontend/app/(app)/recurring/page.tsx` — dónde vive la marca
- `frontend/app/(app)/funds/page.tsx` — la tabla y el desglose de la 014
- `docs/adr/0043-*` — el que se sustituye
- `docs/adr/0054-*` — el desglose que cada fila va a mostrar

## Riesgos

**La migración toca datos reales.** Cuatro fondos de suscripciones se parten en
uno por cobro, y hay que repartir lo que cada uno ya tiene guardado
(`anchor_amount`). `claim_holdings` ya reparte lo que un fondo tiene entre sus
obligaciones, cobro más próximo primero — esa misma regla es el candidato, y hay
que proponérsela al dueño antes de escribirla. CHARTER §7 y el tope de autonomía
`low` sobre `migrations/**` aplican, más un backup fresco por la ADR-0030.

**La suma no puede moverse.** Los nuevos fondos tienen que pedir exactamente lo
que pedían los viejos. Si la suma cambia, la migración está mal.

**Un cobro sin categoría, o cuya categoría se archiva.** Hoy el fondo muere con la
categoría. Atado al cobro, hay que decidir qué pasa cuando el cobro se desactiva
o se borra.

**La 014 tiene que estar mergeada primero.** Esta feature muestra el desglose que
la 014 construye, y toca el mismo servicio. La 014 quedó en CP5 con las cuatro
rebanadas verdes y le faltan CP6, CP7 y CP8.

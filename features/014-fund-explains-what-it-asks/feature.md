---
title: "Un fondo dice de dónde sale su cifra, y su aviso deja de mentir"
slug: fund-explains-what-it-asks
number: 014
status: ready
autonomy_level: medium
branch: fund-explains-what-it-asks
area: funds
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: fund-mixed-interval-categories
acceptance_stream: mixed
relevant_adrs: [0028, 0031, 0043, 0044, 0046]
created: 2026-08-12
intake: discuss
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más una lectura de las cuatro categorías reales — Services, Fitness, Software y Auto Insurance — contra una copia restaurada de producción, comparando el desglose que la pantalla muestra contra el que el servicio calcula. La cifra total no puede cambiar en ninguna."
---

# Un fondo dice de dónde sale su cifra, y su aviso deja de mentir

## Outcome

Un fondo de «Pago mis suscripciones mes a mes» **explica su cifra**: qué parte
vence este mes y qué parte se está guardando, y para cuándo. Y el aviso que sale
al crearlo deja de saltar cuando no hay nada de qué avisar.

Ninguna cifra cambia. Es una feature de lectura entera.

## Por qué

El dueño creía que no podía ahorrar mes a mes para el Seguro del Carro —
7.000.000 al año — si su categoría tenía además un cobro mensual. **Medido
contra producción el 2026-08-12: sí puede, y ya lo está haciendo.**

```
🛡️ Auto Insurance   pide 686.063,64/mes   completo para 2027-04
   SOAT               447.300  cobra 2027-05  ÷  9  →   49.700
   Seguro del Carro 7.000.000  cobra 2027-07  ÷ 11  →  636.363

🔥 Services         pide 277.488,57/mes
   EPM                250.000  vence este mes  ÷  1  →  250.000
   DolarApp Premium   219.908  cobra 2027-04   ÷  8  →   27.488

🏋️ Fitness          pide 127.572,22/mes
   Smart Fit          120.000  vence este mes  ÷  1  →  120.000
   Smart Fit anual     83.294  cobra 2027-07   ÷ 11  →    7.572
```

El reparto funciona en las cuatro. Lo que falla es lo que la app **dice** de él.

**El aviso miente.** Al crear un fondo en 🔥 Services la app avisa:

> «2026-08 no deja mes para ahorrar, así que el objetivo entero cae en 2026-08:
> pediría 277.488,57 de una»

Falso tres veces. El objetivo entero son 469.908, no 277.488. No cae todo en
agosto — 27.488 son la octava parte de un cobro de abril de 2027. Y no es «de
una». El aviso mira solo la obligación **más próxima** y luego cita el total del
fondo; como cualquier cobro mensual vence siempre este mes, **salta siempre**.
Se comprobó el mismo día en 🤖 AI Tools y 📞 Phone, que solo tienen cobros
mensuales y no tienen mezcla ninguna: avisan igual.

**Y ese aviso es el que frenó al dueño.** No creó el fondo porque la app le dijo
que le iba a pedir 277.488 de golpe. Una función que ya tenía y que ya
funcionaba quedó sin usar por lo que la pantalla decía de ella.

**La fila tampoco ayuda.** Muestra `PIDE 277.488` y nada más, así que no hay
forma de saber que 250.000 son la factura de EPM de este mes y 27.488 son ahorro
para abril. El dueño preguntó exactamente eso durante el discuss.

## Scope

**Dentro:**

- El aviso al crear un fondo: salta solo cuando de verdad queda una obligación
  sin meses para repartirla, y nombra cuál.
- La fila del fondo dice de dónde sale su cifra: por obligación, cuánto vence
  este mes y cuánto se guarda, y para qué mes.
- El desglose por obligación llega a la lectura del fondo, calculado al leer.

**Fuera:**

- **Cambiar cualquier cifra.** `asks`, `holds` y `carries` salen iguales. Si una
  cambia, es un defecto de esta feature.
- **Sacar del fondo los cobros mensuales.** Se propuso y el dueño lo rechazó el
  2026-08-12 con razón: la fila dejaría de mostrar los 250.000 que sí tiene que
  pagar este mes.
- **Enlazar a mano un pago con el cobro que saldó.** Salió en el discuss y se
  archivó como `link-a-payment-to-the-charge-it-settled`; solo hace falta el día
  que algo decida el saldado por enlace en vez de por gasto.
- **Las otras dos reglas** (`fixed`, `average`). Explicar también su cifra se
  ofreció y el dueño lo dejó fuera: no tienen ningún problema hoy.
- **Metas.** Un fondo cuelga de una categoría y se renueva solo; una meta no
  cuelga de ninguna y termina. La 009 quitó del fondo la regla con fecha
  justamente para no tener dos mecanismos con fecha (ADR-0046, AC-40).

## Decisiones tomadas en el discuss

| | Decisión | Cuándo |
|---|---|---|
| 1 | Los cobros mensuales **siguen contando** en el fondo — sacarlos escondería plata que sí hay que pagar | 2026-08-12 |
| 2 | La regla **no se ofrece** en una categoría donde no hay nada que repartir | 2026-08-12 |
| 3 | El aviso se arregla **y** la fila explica su cifra | 2026-08-12 |

## Related code / design pointers

- `backend/src/quaestor/services/funds.py` — `_obligations`, `_charge_month_for`,
  `_ask_from_obligations`, `_status`, `preview_fund`, y el aviso alrededor de
  la línea 546
- `backend/src/quaestor/services/month_aggregate.py` — de dónde sale lo acotado
- `frontend/app/(app)/funds/page.tsx` — la tabla y sus dos líneas de texto
- `frontend/app/(app)/funds/rules.ts` — `rulesFor`, que decide qué reglas se
  ofrecen
- `docs/adr/0028-*` — el camino de lectura acotado que este desglose engorda
- `docs/adr/0043-*` — el saldo del fondo es derivado, no guardado

## Riesgos

**La trampa a fijar desde el spec:** el desglose se lee, no se guarda. Si se
guardara, envejecería igual que el precio que la 013 acaba de dejar de guardar.

**El camino de lectura.** La ADR-0028 acotó a propósito lo que el mes carga. Un
desglose por obligación es más dato saliendo por el mismo sitio, y va a
necesitar su propia ADR antes de escribirse.

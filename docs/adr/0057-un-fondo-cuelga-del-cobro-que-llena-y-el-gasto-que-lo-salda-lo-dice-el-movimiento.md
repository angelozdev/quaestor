# 0057. Un fondo cuelga del cobro que llena, y el gasto que lo salda lo dice el movimiento

- **Status:** accepted
- **Date:** 2026-08-15
- **Accepted:** 2026-08-17 (feature 015, tras el CP8. La migración corrió contra
  los datos reales con el dueño delante y ninguna cifra del mes se movió)
- **Deciders:** Angelo
- **Supersedes:** 0043 (cláusula «una categoría lleva un fondo», solo para la regla `from-recurring`)
- **Superseded by:** —

## Context and problem statement

Hoy un fondo cuelga de una categoría y `uq_fund_category` garantiza que solo
haya uno. La regla `from-recurring` reparte entre **todos** los cobros de esa
categoría, y cuando sale plata tiene que **adivinar** cuál pagó: el heurístico
`funds._settled_by_spending` ordena los turnos del más próximo al más lejano y
va restando lo gastado.

Eso obliga al dueño a una decisión que no es suya. 🛡️ Auto Insurance lleva dos
cobros anuales — Seguro del Carro 7.000.000 y SOAT carro 447.300. Si quiere
juntar para el Seguro y no para el SOAT, hoy tiene que **partir la categoría en
dos**, y una categoría es una forma de leer sus gastos, no una hucha.

Y hay un dato que ya existe y que la adivinanza ignora. `Transaction.recurring_id`
está en el esquema desde la 013 y `services/month.py:91` ya lo lee para contar
turnos pagados. Todo pago hecho por el motor **dice** qué cobro saldó.

Dos cosas separables se juntaron en el discuss del 2026-08-12, y conviene
nombrarlas aparte:

1. **La corrección** — leer el hecho (`recurring_id`) en vez de adivinar por
   monto y fecha. No exige cambiar de dueño.
2. **La preferencia** — que la caja cuelgue del cobro, para poder juntar para
   uno y no para el otro.

## Decision drivers

- **Nadie en la industria mueve la propiedad al cobro, y aun así el dueño la
  quiere.** Investigado el 2026-08-15: YNAB pone todo objetivo en la categoría y
  advierte contra tener 20 categorías-objetivo; Actual Budget —el más parecido—
  deja el objetivo *en la categoría* y su `#template schedule {NAME}` solo nombra
  qué cobro dicta la cifra, sumando varias líneas por categoría; Firefly III usa
  un sustantivo aparte (*piggy bank*) atado a una cuenta. Se le presentó esa
  evidencia junto con la observación de que la corrección no necesita el cambio
  de dueño. **Reconfirmó el diseño por cobro**: *«me gusta más la opción 2, es
  más escalable a futuro»*.
- **El argumento de la 0043 sigue en pie para las otras dos reglas.** Dos fondos
  `fixed` sobre una categoría sí serían dos formas de bajar el mismo titular.
  Dos cajas atadas a **cobros distintos** no se pisan: cada una cubre plata
  distinta, y ahora el pago dice cuál.
- **La migración es más barata de lo que se creía.** Medido el 2026-08-15 contra
  el Postgres de producción, en solo lectura: existe **un** fondo
  `from_recurring` y **ninguno** de los cinco fondos tiene `anchor_amount`.
  La migración es 1 → 2 y no hay nada guardado que repartir — con lo que muere,
  por falta de casos, la objeción de que repartir el anchor congelaría una
  distribución que `claim_holdings` recalcula en cada lectura.
- **La consulta que hace falta ya está escrita para otro sustantivo.**
  `load_month_aggregate` agrupa el gasto por `(categoría, año, mes, moneda)` y ya
  excluye lo que fue a una meta con `meta_id IS NULL` (ADR-0046). Agregar
  `recurring_id` al `GROUP BY` da las dos mitades del doble conteo en la misma
  consulta, al mismo costo — la ADR-0028 no se toca.
- **Sin la mitad manual la caja miente.** Si el dueño paga el seguro desde el
  banco y lo anota a mano, la caja sigue creyendo que tiene 7.000.000 ya
  gastados, y el año siguiente no pide nada.

## Considered options

1. **La caja sigue en la categoría y gana una lista de qué cobros llena.** La
   forma de Actual Budget.
2. **La caja cuelga del cobro** — `Fund.recurring_id` opcional, `uq_fund_category`
   pasa a ser único solo cuando ese campo es nulo.
3. **La caja cuelga del cobro, en su propia tabla** — `ChargeFund` aparte de
   `Fund`.
4. **No hay fila de caja: el cobro se marca y la caja se deriva** — una columna
   en `RecurringItem`.

## Decision outcome

Chosen option: **2**, porque conserva intacto lo que la 0043 defendía —una
categoría, un fondo, para `fixed` y `average`— y solo abre la puerta donde el
argumento no aplica, sin duplicar el sustantivo que responde *«¿cuánto aparto
este mes?»*.

La frontera, en una línea:

> **La categoría dice cuánto gastás. El cobro dice para qué juntás.**

Y su mitad de datos:

> **Lo que saldó un cobro lo dice el movimiento, no el monto.**

### Pros and cons of the options

**1 — Lista de cobros sobre el fondo de categoría**
- Good, because es lo que hace la app comparable más cercana y no toca el esquema
  más que con una tabla de enlace.
- Good, because `uq_fund_category` y la 0043 quedan intactas.
- Bad, because el dueño la evaluó con la evidencia delante y la rechazó: quiere
  poder juntar para el Seguro y no para el SOAT sin partir la categoría.
- Bad, because el reclamo abierto de Actual Budget es justamente ese: la
  plantilla nombra un cobro y no recoge los que llegan después.

**2 — `Fund.recurring_id` opcional**
- Good, because un solo sustantivo sigue respondiendo la misma pregunta: el fold,
  el estado, la lista y el término del mes no se bifurcan.
- Good, because el único parcial (`WHERE recurring_id IS NULL`) deja escrita la
  frontera en el esquema: la 0043 sigue siendo verdad donde su argumento vale.
- Good, because la caja hereda la moneda del cobro sin convertir nada, que es lo
  que la AC-11 pide y lo que una meta ya hace.
- Bad, because `funded_categories()` deja de ser un interruptor por categoría —
  una categoría puede quedar cubierta a medias, y los 4 sitios de `month.py` que
  lo leen tienen que distinguir «la categoría entera» de «este cobro».
- Bad, because la invariante «ninguna caja huérfana» hay que **hacerla cumplir**
  en cuatro puertas, no sale gratis del esquema.

**3 — Tabla aparte**
- Good, because cada tabla tiene exactamente las columnas que usa.
- Bad, because duplica el fold, el estado, la lista y la API por un sustantivo
  que contesta las mismas preguntas; `MonthAggregate.funds` se parte en dos y
  cada consumidor se ramifica.

**4 — Marcar el cobro y derivar la caja**
- Good, because la invariante de huérfanas sería estructural: no hay fila que
  huerfanar.
- Bad, because el mes en que se marcó y lo que ya guardó tendrían que vivir en
  `RecurringItem` — contabilidad de fondo en la tabla del cobro.
- Bad, because `fund_status(fund_id)`, `set_fund` y `delete_fund` dejan de tener
  un id al que apuntar: toda la superficie de API se bifurca.

## Consequences

- Good: el dueño marca un cobro en Recurrentes y eso **es** lo que crea la caja
  — un paso donde había cuatro y saber de antemano que la función existe.
- Good: `_settled_by_spending` se retira. Un gasto de 7.000.000 en 🛡️ Auto
  Insurance deja de vaciar la caja del Seguro solo por ser del tamaño correcto.
- Good: el doble conteo queda cerrado por construcción en las dos direcciones —
  el promedio de una categoría deja de contar los pagos de sus cobros marcados,
  y un peso que salda un cobro marcado no vacía además la caja de la categoría.
- Bad / cost: un fondo de categoría recogía los cobros nuevos solo. Después, no:
  cada cobro se marca. Es el mismo reclamo abierto de Actual Budget, y se le dijo
  al dueño el 2026-08-12 antes de que decidiera.
- Bad / cost: cuatro puertas hay que cerrar a mano para que ninguna caja quede
  huérfana — destildar, apagar, borrar y editar la cadencia a mensual. La quinta,
  archivar la categoría, se cierra **rechazando el archivado**, que es lo que la
  003 ya hacía por el fondo de categoría (AC-21) y lo que el dueño reconfirmó el
  2026-08-15.
- Bad / cost: una migración sobre datos reales. CHARTER §7, el tope de autonomía
  `low` sobre `migrations/**` y el backup fresco de la ADR-0030 aplican.

## Confirmation

Tres comprobaciones, cada una verificable sin leer código:

**La 0043 sigue viva donde su argumento vale.** El único parcial sobre
`category_id WHERE recurring_id IS NULL` tiene que existir en el esquema. Una
revisión que encuentre dos fondos `fixed` sobre una misma categoría está viendo
esta ADR rota.

**La suma no se mueve.** La migración es 1 → 2 y las dos cajas nuevas tienen que
pedir exactamente lo que pedía la vieja: `636.363,64 + 49.700,00 = 686.063,64`.
Está fijado en la AC-6 del `spec.md`.

**El mes no cuesta una consulta más.** La 014 dejó un escenario que mide los
statements de leer el mes con cinco fondos contra leerlo con uno y exige que sean
iguales. Agregar `recurring_id` al `GROUP BY` no puede cambiarlo (ADR-0028).

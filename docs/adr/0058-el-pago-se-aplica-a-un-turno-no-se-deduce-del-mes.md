# 0058. El pago se aplica a un turno, no se deduce del mes

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

La ADR-0057 hizo que un movimiento diga **qué cobro** saldó, reemplazando la
adivinanza por monto. El CP7 de la feature 015 encontró que eso resolvió la
mitad del problema: se sabe *qué cobro*, pero no *cuál de sus turnos*, y la
consulta se hace **un mes a la vez**.

Reproducido — Club de vinos, 600.000 cada 6 meses, con turno en noviembre 2026,
marcado y pagado entero en agosto 2026 nombrando el cobro:

```
agosto      junta para 2027-05   pide  66.666    correcto
septiembre  junta para 2026-11   pide 300.000    el turno ya pagado
octubre     junta para 2026-11   pide 300.000    otra vez
```

Al leer septiembre, `settled_in(item, "2026-09")` suma solo los pagos fechados
en septiembre. No ve el de agosto, concluye «sin pagar» y vuelve a reclamar
600.000 que ya salieron — plata que además se descuenta del disponible del mes.

El mismo hueco al revés: un seguro con turno en julio 2027 pagado a mano en
agosto 2027 se lee como *«cobra julio 2029»*, un año de más, porque el código no
puede distinguir un pago adelantado de uno atrasado.

La AC-5 nombra los dos casos: *«De paso resuelve el pago adelantado y el
atrasado: si pagás en junio o en agosto y decís cuál cobro era, la caja se
entera igual.»*

## Decision drivers

- **Un peso se pide una vez.** Un turno pagado no puede volver a reclamarse, ni
  el mes siguiente ni nunca (AC-9).
- **La app no adivina.** Es el eje de la ADR-0057: si el dato importa, lo dice
  el dueño; deducirlo del monto y la fecha es la adivinanza que se eliminó.
- **El período del libro es el mes; lo que se repite es agnóstico** (ADR-0056).
  La cadencia de un cobro no tiene por qué caber en un mes, así que la pregunta
  «¿está pagado?» no puede ser una pregunta mensual.
- **El camino de lectura está acotado** (ADR-0028): 13 consultas fijas por mes,
  medido. Nada de esto puede agregar una consulta por cobro.
- **No inventar estructura que ya existe.** El motor de recurrentes (ADR-0036)
  ya lleva una fila por turno.

## Considered options

1. **El movimiento se aplica al turno, usando `recurring_occurrence`.**
2. **Mirar hacia atrás sin nombrar el turno** — al leer un mes, sumar también
   los pagos de meses anteriores que nombran el cobro.
3. **Una columna nueva en `transaction`** con la fecha del vencimiento saldado.
4. **Guardar en el fondo el último ciclo cerrado** — un campo que avanza.

## Decision outcome

Chosen option: **1 — el movimiento se aplica al turno**, porque la estructura ya
existe, la decisión la toma el dueño en vez de deducirse, y resuelve el pago
adelantado y el atrasado con la misma regla.

`RecurringOccurrence` ya es exactamente una fila por `(cobro, vencimiento)`, con
`transaction_id` para el movimiento que lo pagó y `UniqueConstraint(recurring_id,
due_date)` que garantiza un turno una sola vez. Es lo que el motor escribe
cuando un cobro automático se registra solo. Lo único que falta es que un pago
**escrito a mano** también pueda engancharse ahí.

Esto es el patrón estándar de la industria, que tiene nombre propio: un pago no
deduce a qué cuota corresponde, **se le aplica** (*payment application* /
*allocation*) a la fila de la cuota, que existe de antemano. Los sistemas de
facturación recurrente materializan la cuota primero y aplican el cobro después;
ninguno infiere la cuota del monto y la fecha.

La consulta deja de ser «¿hubo un pago este mes?» y pasa a ser «¿cuál es el
primer turno sin pagar?», que no es una pregunta mensual y por eso no puede
olvidarse al mes siguiente.

`occurrences.py` sigue siendo **el único módulo que escribe un
`RecurringOccurrence`** — la frontera que su propio docstring declara. El enlace
desde un gasto a mano entra por una función nueva de ese módulo, no por
`transactions.py`.

### Pros and cons of the options

**1. El movimiento se aplica al turno (`recurring_occurrence`)**
- Good, porque la tabla, su unicidad por turno y su `transaction_id` ya existen
  y ya los llena el motor: un pago a mano y uno automático quedan indistinguibles
  para el que lee.
- Good, porque un turno pagado lo está para siempre, así que el olvido del mes
  siguiente no puede volver.
- Good, porque el atrasado se resuelve sin regla aparte: el dueño nombra el
  turno de julio y la app no tiene que inferir nada de la fecha del pago.
- Good, porque un turno omitido y uno pagado quedan en la misma tabla, que es
  donde el fondo ya pregunta por los omitidos.
- Bad, porque la pantalla gana una pregunta cuando hay más de un turno abierto.
- Bad, porque hay que decidir qué pasa si el dueño borra el movimiento: el turno
  vuelve a estar sin pagar, y eso tiene que estar cubierto.

**2. Mirar hacia atrás sin nombrar el turno**
- Good, porque no toca el esquema, no toca la pantalla y arregla el caso del
  pago adelantado con muy poco código.
- Bad, porque para saber *cuántos* turnos cubrió un pago hay que volver a
  deducirlo del monto — la adivinanza que la ADR-0057 eliminó, reinstalada en
  otro lugar.
- Bad, porque no resuelve el atrasado: dos pagos y tres turnos siguen sin
  emparejarse.
- Bad, porque «hacia atrás» no tiene fondo: o se lee toda la historia del cobro
  en cada mes, o se elige un límite arbitrario.

**3. Columna nueva en `transaction`**
- Good, porque es explícito y directo.
- Bad, porque duplica lo que `recurring_occurrence` ya modela, y deja dos
  fuentes para el mismo hecho: un turno podría estar `posted` por el motor y
  además apuntado por un movimiento distinto.
- Bad, porque cuesta una migración sobre datos reales para una tabla que ya
  existía vacía de este uso.

**4. Guardar en el fondo el último ciclo cerrado**
- Good, porque es una sola columna y la lectura es trivial.
- Bad, porque congela una cifra derivada, que es justo lo que la ADR-0043
  prohíbe: el fondo guarda su regla, nunca un saldo ni un estado.
- Bad, porque un pago borrado o corregido deja el campo mintiendo, sin nada que
  lo recalcule.

## Consequences

- Good: el pago adelantado y el atrasado se resuelven con la misma regla, y la
  AC-5 pasa a ser cierta en los dos casos que ya nombraba.
- Good: `settled_in` deja de ser una pregunta mensual, así que el defecto no
  puede repetirse en otra forma.
- Good: no hay columna nueva ni migración de esquema. El movimiento se engancha
  a una fila que ya existe o que se crea al enlazarlo.
- Bad / cost: el formulario de gasto gana una pregunta —**cuál vencimiento**—
  cuando el cobro tiene más de un turno abierto. Con uno solo se elige solo y no
  se pregunta nada.
- Bad / cost: borrar o re-clasificar el movimiento tiene que soltar el turno, o
  quedaría un turno marcado como pagado por un movimiento que ya no existe.
- Bad / cost: la AC-5 y su spec cambian, con permiso del dueño (2026-08-15).

## Confirmation

- Un escenario que lee el fondo **el mes siguiente** al pago, que es lo que
  ningún escenario de la 015 hacía y por lo que el defecto quedó verde.
- Un escenario de pago atrasado: turno en julio, pagado en agosto, y el fondo
  junta para el turno del año siguiente y no del subsiguiente.
- Un escenario de borrado: se borra el movimiento y el turno vuelve a estar sin
  pagar.
- El contador de consultas de `load_month_aggregate` sigue en 13, medido con
  `tests/support/query_counter.py` a 6, 20 y 40 fondos.
- `occurrences.py` sigue siendo el único módulo que escribe la tabla: lo dice su
  docstring y lo sostiene el contrato de capas de `lint-imports`.

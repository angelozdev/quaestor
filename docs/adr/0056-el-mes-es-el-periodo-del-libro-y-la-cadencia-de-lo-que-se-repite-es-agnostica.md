# 0056. El mes es el período del libro, y la cadencia de lo que se repite es agnóstica

- **Status:** proposed
- **Date:** 2026-08-15
- **Deciders:** Angelo
- **Supersedes:** — (nombra la frontera que 0028, 0043 y 0044 ya asumían sin escribirla)
- **Superseded by:** —

## Context and problem statement

El dueño preguntó, durante el descubrimiento de AC de la feature 015, qué pasaría
si empezara a recibir ingresos cada 15 días, y si las reglas no deberían ser
«agnósticas y generales, no tan arbitrarias como hacerlo por mes».

La pregunta es arquitectónicamente significativa porque **nadie ha escrito nunca
que el mes sea una decisión**. `year_month` aparece 250 veces en 16 archivos de
`backend/src/quaestor`, y las ADR que lo asumen —0028 (camino de lectura
acotado), 0043 (el saldo del fondo es derivado), 0044 (el titular es un fold
sobre el mes)— lo dan por hecho sin justificarlo. Una feature futura puede
cruzar esa línea sin darse cuenta de que existe.

**Lo primero que hubo que medir es que la pregunta mezcla dos cosas, y solo una
de ellas es mensual.**

*La cadencia de lo que se repite ya es agnóstica.* `IntervalUnit` admite
`day | week | month | year` con un `interval_count` libre, así que un ingreso
cada 15 días se anota hoy como «cada 2 semanas» y funciona sin escribir código.
`monthly_rate_calc` convierte cualquier ciclo a su ritmo mensual —
*«a weekly charge is the ~4,33 turns a month really holds rather than the one a
calendar month shows»* — y `funds._can_be_spread` decide leyendo **el ritmo
real**, no la unidad declarada, precisamente para que «cada 45 días» y «cada 6
semanas» se contesten solas.

*Lo que es mensual es el período del libro:* lo que queda libre, el reparto de
los fondos, las metas y el reporte.

La decisión, entonces, no es «mes sí o mes no». Es **dónde va la frontera entre
las dos**, y dejarla escrita.

## Decision drivers

- **Las obligaciones del dueño están denominadas en meses.** EPM, Claro,
  arriendo y las suscripciones cobran por mes; el seguro del carro y el SOAT por
  año. Nada suyo cobra por quincena. El extracto del banco cierra por mes y la
  TRM se fija por mes (ADR-0031).
- **Un ingreso quincenal cabe en un mes sin cambiar nada.** La mayoría de los
  meses trae 2 turnos y dos meses al año traen 3; ese mes tiene más plata y la
  app ya lo diría bien. El error real del pago quincenal es multiplicar por 2
  para sacar «lo mensual», que subestima ~8% — son 26 pagos al año, no 24. Estar
  en el mes evita ese error gratis, porque cuenta turnos y no multiplica.
- **El experimento ya lo corrió otro.** Firefly III es la única app comparable
  que salió del mes: soporta semanas y trimestres. Su propia documentación dice
  que funciona mejor del día 1 al último del mes, que **el quincenal no está
  soportado** (hay que poner un presupuesto semanal dividido en dos), y que si un
  presupuesto anual se solapa con uno mensual **el mismo gasto se descuenta de
  los dos**. YNAB no tiene período configurable en absoluto y responde al pago
  quincenal con «presupuestá la plata que ya tenés». Actual Budget es mensual y
  punto.
- **Un período configurable multiplica dos ADR vigentes.** El camino de lectura
  acotado de la 0028 y el fold de la 0044 están denominados en meses de punta a
  punta. Un eje nuevo no agrega una columna: reescribe los dos.
- **La app es de un solo usuario** (CHARTER §4). Una perilla que este dueño no
  va a mover es coste puro.

## Considered options

1. **Período del libro configurable** — semanal, quincenal, mensual, trimestral.
   La forma de Firefly III.
2. **El mes es el período del libro; la cadencia es agnóstica.** El estado de
   hoy, escrito y defendido.
3. **El período es el ciclo de pago** — el libro cierra cada vez que entra
   plata, no cada mes.

## Decision outcome

Chosen option: **2**, porque es la única que responde la preocupación real del
dueño —que las reglas no sean arbitrarias— sin comprar un eje que ninguna de sus
obligaciones pide y que la app que sí lo compró todavía no logra usar para
quincenas.

La frontera, en una línea:

> **Lo que se repite es agnóstico. Lo que se reporta es mensual.**

### Pros and cons of the options

**1 — Período configurable**
- Good, because serviría a alguien cuya vida entera es quincenal: arriendo,
  servicios y sueldo cada 15 días.
- Bad, because reescribe la 0028 y la 0044, y sus 250 usos de `year_month`.
- Bad, because Firefly la implementó y aun así el quincenal no le sale: la
  respuesta oficial es un presupuesto semanal dividido a mano en dos.
- Bad, because períodos solapados dejan que el mismo gasto se descuente dos
  veces — una forma de contar doble que hoy es imposible por construcción.
- Bad, because es una perilla para un solo usuario que no la necesita.

**2 — Mes como período, cadencia agnóstica**
- Good, because ya funciona: un ingreso cada 2 semanas se anota hoy y la app
  cuenta sus turnos reales.
- Good, because cuenta turnos en vez de multiplicar, así que el mes de tres
  pagos sale bien sin que nadie lo programe.
- Good, because coincide con cómo cobran las obligaciones del dueño, con su
  extracto y con la TRM.
- Bad, because un mes con tres pagos se lee como un mes rico y nada en pantalla
  lo señala como excepcional.
- Bad, because deja mal servido a un usuario íntegramente quincenal, que no es
  este.

**3 — El período es el ciclo de pago**
- Good, because es lo más cercano a «la plata que tengo hoy», que es la respuesta
  de YNAB.
- Bad, because las obligaciones seguirían venciendo por mes, así que habría que
  repartir cada cobro mensual entre ciclos de pago — el problema que se quería
  evitar, movido de lugar.
- Bad, because el reporte dejaría de poder compararse contra el extracto.

## Consequences

- Good: no se agrega ningún eje. Los 250 usos de `year_month` siguen siendo
  correctos por construcción y ninguna ADR vigente se toca.
- Good: un ingreso cada 15 días no cuesta una línea de código.
- Good: la línea queda nombrada, así que una feature futura no puede cruzarla sin
  sustituir esta ADR — que es exactamente lo que hoy no existe.
- Bad / cost: dos meses al año traen tres pagos quincenales y la app los mostrará
  como meses con más plata, sin decir que son la excepción. Si eso llega a
  confundir, el arreglo es una nota en la pantalla, no un período nuevo.
- Bad / cost: si algún día el dueño pasa a tener obligaciones quincenales de
  verdad —no solo ingresos— esta ADR hay que sustituirla, y el coste será el que
  la opción 1 ya nombra.

## Confirmation

La frontera se respeta mientras **ninguna decisión de reparto o de reporte mire
`IntervalUnit` directamente**. El patrón a copiar es `funds._can_be_spread`, que
pregunta por el ritmo a través de `_turn_after` y nunca por la unidad declarada;
su propio docstring dice por qué. Una revisión que vea `if unit == month` en una
regla de negocio está viendo esta ADR rota.

`monthly_rate_calc` es la otra mitad y ya está probada: convierte cualquier ciclo
a su ritmo mensual y redondea hacia arriba para que un ciclo nunca se subestime.

Una feature que quiera un período del libro configurable sustituye esta ADR; no
la enmienda.

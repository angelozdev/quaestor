# 0053. El precio de un cobro recurrente es el del comercio, y su cuenta decide en qué moneda se paga

- **Status:** accepted
- **Date:** 2026-08-11
- **Deciders:** Angelo
- **Supersedes:** 0052
- **Superseded by:** —

## Context and problem statement

ADR-0052, aceptada el día anterior, decidió que **la moneda sigue a la cuenta y
nunca se declara aparte**, con este argumento textual: la cuenta ya la determina,
así que un campo aparte «solo podría coincidir de más o contradecir de menos».

Hevy Pro es el contraejemplo, y es un cobro real del dueño. El comercio cobra
**99.900 COP al año**; DolarApp, la cuenta que lo paga, debita **dólares**. Las
dos monedas son ciertas al mismo tiempo y no coinciden — no por un error, sino
porque son dos cosas distintas: el precio y el débito. La industria de pagos las
separa desde siempre (*presentment currency* contra *settlement currency*), y es
lo que muestra cualquier extracto de tarjeta.

Con la regla de la 0052, ese cobro tuvo que escribirse como **30,22 USD**, la
conversión del día en que se creó. El próximo julio los mismos 99.900 COP serán
otra cifra en dólares y la regla estará mal por lo que se haya movido la tasa.
Smart Fit, con el mismo problema, ya se había desviado a 30 USD contra 37,20
reales y se corrigió a mano el 2026-08-09.

Cuando el comercio cobra en una moneda y el banco debita en otra, **ningún número
fijo es correcto por más de un mes.** La deriva es estructural, no descuido.

## Decision drivers

- **Un precio no es una conversión.** 99.900 COP es lo que el comercio anuncia y
  sigue siendo cierto el año que viene; 30,22 USD era una foto de una tasa.
- **La 0052 resolvió bien la pregunta que tenía delante.** Mover un movimiento
  ya registrado a una cuenta de otra moneda sí exige reescribir la cifra: el
  movimiento *tiene* plata. Una regla no tiene plata, tiene un precio. Aplicar
  el mismo contrato a las dos fue la equivocación.
- **Nada puede mostrar una cifra que no va a usar** (regla 2 de la feature 012).
- **Convertir sin el dueño abre un hueco de plata.** Medido durante CP2: cuando
  nace un cobro copia el monto *y la moneda* de su regla, y si la regla se cobra
  sola le suma esa cifra al saldo. Regla en pesos, cuenta en dólares, cobro
  automático: 99.900 sumados a un saldo en dólares.
- **ADR-038 ya hace de una tasa faltante un frenazo en todo lo que se lee.** Si
  el motor convirtiera, pasaría a ser un frenazo en **cobrar**, que es peor.

## Considered options

1. **Dejar la 0052 como está.** La moneda sigue a la cuenta; Hevy Pro se escribe
   en dólares y se corrige a mano cada año.
2. **El motor convierte al cobrar.** La regla guarda pesos y el motor crea el
   movimiento en dólares a la tasa del día, solo.
3. **La regla guarda el precio; el dueño confirma la cifra.** La regla puede
   estar en otra moneda que su cuenta, el cobro nunca se registra solo, y al
   confirmarlo la app propone la conversión y el dueño la acepta o la reemplaza.

## Decision outcome

Elegida la **opción 3**, decidida por el dueño el 2026-08-11.

**Una regla guarda el precio del comercio, en la moneda en que el comercio lo
anuncia.** Qué cuenta lo paga es una decisión aparte y posterior. La moneda deja
de seguir a la cuenta.

En su lugar queda **un invariante**, que es lo único que la 0052 protegía de
verdad:

> **Una regla que se cobra sola tiene que estar en la moneda de su cuenta.**

Un predicado, comprobado en un solo sitio antes de guardar, por el que pasan las
cuatro puertas que podrían romperlo: crear, cambiar el monto, cambiar el modo y
cambiar la cuenta.

De ese invariante cae solo el resto del comportamiento:

- **Mover una regla a otra moneda propone la conversión y no la exige** — si la
  regla se confirma a mano. Si se cobra sola, no pasa el invariante y se rechaza
  nombrando las dos salidas: aceptar la conversión, o pasarla a confirmarse a
  mano. La app nunca cambia el modo por su cuenta.
- **El motor no cambia una línea.** Ya copia el monto y la moneda de la regla;
  para una regla manual eso produce un cobro esperando en la moneda del precio,
  sin mover saldo, y para una automática el invariante garantiza que las monedas
  coinciden.
- **El movimiento guarda solo lo que salió**, en la moneda de la cuenta. No se
  congela ninguna tasa: ADR-0031 queda intacta y el precio en pesos vive en la
  regla.

`retarget` (ADR-0051) **sobrevive donde nació** — corregir un movimiento ya
registrado — y pierde su extensión a las reglas recurrentes. Al confirmar un
pago se le pasa la cuenta actual del movimiento cuando el dueño no nombra otra,
de modo que un cobro que discrepa de su propia cuenta entre por la rama que ya
existe y ya está probada por mutación.

### Pros and cons of the options

**1 — dejar la 0052**
- Bueno: cero trabajo, cero riesgo.
- Malo: la deriva sigue. Dos cobros reales del dueño están mal hoy y volverán a
  estarlo cada vez que la tasa se mueva.

**2 — el motor convierte**
- Bueno: nada que confirmar; los cobros siguen siendo automáticos.
- Malo: un día sin tasa cargada deja de cobrar. Y la cifra registrada es la
  conversión de la app, no lo que el banco tomó — la app afirmaría un número que
  nunca ocurrió.
- Rechazada por el dueño el 2026-08-11.

**3 — la regla guarda el precio, el dueño confirma**
- Bueno: el precio deja de envejecer, y la cifra registrada es la real.
- Bueno: reusa un contrato ya aceptado y probado por mutación en vez de inventar
  una segunda forma para la misma pregunta.
- Costo: Hevy Pro y Smart Fit dejan de cobrarse solas — un clic al año y uno al
  mes. El dueño lo aceptó a cambio de escribir la cifra verdadera en ese clic.

## Consequences

- Bueno: los cuatro cobros del dueño sobre DolarApp se vuelven expresables sin
  perder la regla que los genera.
- Bueno: un solo invariante reemplaza una guarda que existía únicamente en un
  docstring y un `if`.
- Malo / costo: la app y el informe muestran el cobro en la moneda que salió, y
  releído a otra tasa da otra cifra en pesos. Un cobro de julio por US$32,10 se
  lee como 141.240 COP en diciembre a 4.400, contra un precio real de 99.900. Es
  una propiedad de ADR-0031 que ya afecta a todo lo comprado en dólares, pero
  éste es el primer caso donde la app **conoce** la cifra verdadera. Se compensa
  mostrándola: el cobro enseña el precio de su regla al lado, leído de la regla
  ya enlazada, sin guardar nada. Solo para reglas encendidas — cargar también
  las apagadas haría crecer el camino de lectura acotado de ADR-0028 con cada
  suscripción cancelada.
- Malo / costo: `type` sigue inmutable y ahora convive con una moneda que sí se
  puede cambiar. La asimetría es deliberada y ya estaba anotada en la 0052:
  cambiar el tipo reescribe lo que la regla *significa*; cambiar la moneda
  reescribe lo que *pide*.
- Malo / costo: dos reglas guardadas hoy en dólares se migran a su precio en
  pesos. Los precios se **cargan**, no se calculan: convertir 30,22 USD a la
  tasa de hoy da 94.951 COP y el precio es 99.900, porque la tasa que las
  escribió (≈3.306) no existe en ninguna parte.

## Confirmation

53 escenarios de aceptación en `features/013-recurring-charge-keeps-its-price/spec.md`,
aprobados por el dueño el 2026-08-11, en rojo antes de la implementación: 38 de
los 47 tests de servicio fallan nombrando la guarda que esta ADR retira.

El invariante se comprueba desde las cuatro puertas (AC-2), y el rechazo al
mover una regla automática entre monedas tiene sus propios escenarios (AC-13),
incluido uno que afirma que el modo no cambia solo.

`backend/scripts/mutate.py` sobre `services/recurring.py` es la comprobación de
que el invariante puede fallar de verdad. La deuda que la 0052 dejó anotada —
ese módulo no estaba en la lista de mutación de ninguna feature — la paga esta
feature, que lo incorpora a su estrategia de pruebas.

---
ac_count: 18
high_priority_count: 9
discovered: 2026-08-12
---

# Criterios de aceptación — 014 fund-explains-what-it-asks

Todas las cifras de este documento se midieron contra producción el 2026-08-12
con la TRM en 3.142. **Ninguna cifra cambia con esta feature**: si una cambia,
es un defecto.

---

## AC-1: La cifra del fondo se abre en los cobros que la produjeron

**Priority:** high · **Type:** happy-path

Debajo de cada fondo de suscripciones, siempre visible, van los cobros que
componen su cifra. 🛡️ Auto Insurance pide 686.063 y debajo dice que 49.700 son
del SOAT y 636.363 del Seguro del Carro.

Es el mismo principio que la 003 ya fijó un nivel más arriba (AC-10): el titular
del mes se abre en los términos que lo produjeron y nada queda sin atribuir. Un
fondo no debería ser la única cifra de la app que no explica de dónde sale.

## AC-2: Cada línea dice cuánto cuesta el cobro, cuándo llega y cuánto pide hoy

**Priority:** high · **Type:** happy-path

Del Seguro del Carro se lee que cuesta 7.000.000, que llega en julio de 2027, y
que por eso pide 636.363 este mes. Las tres cosas, porque con dos no se entiende
la tercera: 636.363 al mes solo tiene sentido sabiendo que son 7.000.000
repartidos en once meses.

## AC-3: Un cobro que vence este mes se lee como que vence, no como que se ahorra

**Priority:** high · **Type:** happy-path

En 🔥 Services los 250.000 de EPM vencen este mes; los 27.488 de DolarApp
Premium se están guardando para abril. La pantalla distingue las dos cosas.

Sin esa distinción el dueño lee «pide 277.488» y no sabe si eso es plata que se
va ya o plata que se queda — que es exactamente la pregunta que hizo el
2026-08-12.

## AC-4: El total es la suma de lo que se ve

**Priority:** high · **Type:** happy-path

Las líneas suman la cifra del fondo, exactamente. No hay un resto sin nombre ni
una línea que no cuente.

## AC-5: Ninguna cifra se mueve

**Priority:** high · **Type:** cross-cutting

Lo que un fondo pide, tiene y pasa al mes siguiente sale idéntico a hoy, en las
cinco categorías con fondo y en las cuatro medidas:

| | pide hoy | pide después |
|---|---|---|
| 🛡️ Auto Insurance | 686.063,64 | 686.063,64 |
| 💻 Software | 17.465,23 | 17.465,23 |
| 🔥 Services | 277.488,57 | 277.488,57 |
| 🏋️ Fitness | 127.572,22 | 127.572,22 |

Esta feature es de lectura. Una cifra distinta es un defecto, no una mejora.

## AC-6: Un cobro omitido este mes sale de la lista

**Priority:** medium · **Type:** edge-case

Omitir Plan de datos Mamá deja 🌐 Internet pidiendo menos ese mes (003, AC-17), y
ese cobro **no aparece** en el desglose de ese mes. La lista muestra lo que está
pidiendo algo, no todo lo que existe.

## AC-7: Un cobro ya pagado este mes sale de la lista, y el fondo sigue con el siguiente

**Priority:** medium · **Type:** edge-case

Cuando el cobro que el fondo esperaba se paga, el fondo empieza el ciclo
siguiente (003, AC-11). Desde ese momento el desglose muestra el turno nuevo, con
su mes nuevo — el Seguro del Carro pagado en julio de 2027 reaparece pidiendo
para julio de 2028.

## AC-8: Un fondo al que este mes no le pide nada lo dice, en vez de quedarse en blanco

**Priority:** medium · **Type:** edge-case

Si todos los cobros de la categoría están omitidos o ya pagados, el fondo pide 0
y su desglose queda vacío. En vez de una fila muda, dice que este mes no hay
nada que apartar y por qué.

Sale de AC-6 y AC-7: si las líneas desaparecen, alguien tiene que explicar el
hueco que dejan.

## AC-9: Un fondo cuya categoría se quedó sin cobros lo dice

**Priority:** low · **Type:** edge-case

Apagar la última regla recurrente de una categoría deja su fondo pidiendo 0 para
siempre. La pantalla lo dice, para que el dueño lo borre o registre otra
obligación, en vez de dejarlo ahí en cero sin motivo aparente.

## AC-10: Un cobro en otra moneda se lee en pesos, como el resto

**Priority:** medium · **Type:** edge-case

DolarApp Premium cuesta 69,99 USD y en el desglose se lee como 219.908 COP, que
es lo que la 003 ya fijó para la cifra del fondo (AC-18) y lo que la ADR-0031
manda: se convierte al leer, con la TRM del momento, y no se guarda ninguna
conversión.

## AC-11: El aviso salta solo cuando algo no se puede repartir

**Priority:** high · **Type:** error

Crear en junio el fondo del Seguro del Carro, que cobra en julio, avisa: no queda
mes para repartir, así que los 7.000.000 caen enteros en junio y el fondo pediría
7.049.700 ese mes. El dueño puede seguir adelante.

Es lo que la 003 quiso decir con AC-24 — la sorpresa llega al crear y nunca
después — dicho sobre el caso en que la sorpresa existe de verdad.

## AC-12: El aviso dice cuál es el cobro y cuánto es

**Priority:** high · **Type:** error

Nombra la obligación y su figura. Hoy cita el total del fondo, que mezcla lo que
sí se reparte con lo que no, y por eso asusta con una cifra que nadie va a pagar
de una.

## AC-13: Un cobro mensual nunca dispara el aviso

**Priority:** high · **Type:** error

Que EPM cobre 250.000 este mes es lo normal, no una sorpresa: un cobro que llega
cada mes no tiene meses entre uno y otro para repartirse. Hoy el aviso salta en
🔥 Services, 🏋️ Fitness, 🤖 AI Tools y 📞 Phone — y las dos últimas ni siquiera
tienen mezcla de intervalos.

Ese aviso es el que hizo que el dueño no creara el fondo. Una función que ya
tenía, sin usar, por lo que la pantalla decía de ella.

## AC-14: La regla no se ofrece donde no hay nada que repartir

**Priority:** medium · **Type:** error

En 📞 Phone, con dos planes mensuales, «Pago mis suscripciones mes a mes» no
aparece entre las opciones al crear. Un fondo que solo puede pedir 0 no se ofrece.

## AC-15: Sin tasa, el fondo se niega igual que hoy

**Priority:** medium · **Type:** error

Un fondo con cobros en dólares y sin TRM configurada sigue negándose a
responder, con el mismo mensaje. El desglose no inventa una lectura parcial ni
muestra unos cobros sí y otros no.

## AC-16: El desglose se lee, nunca se guarda

**Priority:** high · **Type:** cross-cutting

Ni el reparto ni la conversión ni el mes de cobro quedan almacenados. Se calculan
cada vez que se mira, igual que el saldo del fondo (ADR-0043) y que la conversión
de moneda (ADR-0031).

Guardarlos los haría envejecer: una cifra guardada en agosto seguiría diciendo lo
mismo en diciembre con otra tasa y otro calendario — que es exactamente el defecto
que la 013 acaba de quitar del precio de una regla.

## AC-17: Mirar el mes no cuesta más consultas que hoy

**Priority:** medium · **Type:** cross-cutting

El desglose sale de lo que el mes ya carga. La ADR-0028 acotó ese camino a
propósito, y esta feature no lo abre: cinco fondos no son cinco consultas más.

## AC-18: El asistente no se toca

**Priority:** low · **Type:** cross-cutting

Ni una línea. Decidido por el dueño el 2026-08-12 — «no hagas nada sobre el
asistente» — igual que en la 013, porque se va a deprecar.

Consecuencia medida, no supuesta: la tarjeta que el asistente arma nombra sus
campos uno por uno, así que **el desglose no le llega** y su respuesta queda
igual que hoy. La 003 fijó en su AC-28 que el asistente alcanza los fondos igual
que el navegador; **esta divergencia queda escrita, no descubierta**.

El aviso es distinto: el asistente lo repite tal cual lo recibe, así que dejará
de mentir en los dos sitios sin tocar nada.

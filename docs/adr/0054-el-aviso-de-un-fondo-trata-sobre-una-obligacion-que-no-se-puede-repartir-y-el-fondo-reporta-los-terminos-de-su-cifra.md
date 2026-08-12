# 0054 — El aviso de un fondo trata sobre una obligación que no se puede repartir, y el fondo reporta los términos de su cifra

- **Status:** accepted
- **Date:** 2026-08-12
- **Feature:** 014-fund-explains-what-it-asks
- **Amends:** ADR-0043 (el saldo de un fondo es derivado) en la lectura, no en la decisión
- **Related:** ADR-0028 (camino de lectura acotado), ADR-0031 (conversión al leer)

## Context

Un fondo con la regla `from-recurring` reporta una sola cifra: lo que pide este
mes. Esa cifra es la suma de sus obligaciones, cada una dividida entre los meses
que quedan antes de que cobre.

Dos cosas salieron mal de ahí, y las dos se midieron contra producción el
2026-08-12 antes de decidir nada.

**El aviso habla de la cosa equivocada.** La AC-24 de la 003 pidió que un
objetivo inalcanzable se anunciara al crear el fondo. Se implementó mirando la
obligación **más próxima** y citando el **total del fondo**:

```
{mes} leaves no month to save in, so the whole target falls on {inicio}:
it would ask {total} at once
```

Como cualquier cobro mensual vence siempre este mes, la condición se cumple
siempre que la categoría tenga uno. Medido: salta en 🔥 Services, 🏋️ Fitness,
🤖 AI Tools y 📞 Phone — y las dos últimas ni siquiera mezclan intervalos, solo
tienen cobros mensuales.

Y lo que cita es falso. En Services el total son 277.488, de los cuales 250.000
son la factura de EPM que vence ahora y 27.488 son la octava parte de un cobro de
abril de 2027. Ni es «el objetivo entero» (son 469.908), ni cae todo en agosto,
ni es «de una».

**Consecuencia real, no hipotética:** el dueño leyó ese aviso y no creó el fondo.
Una función que ya tenía, que ya funcionaba, sin usar por lo que la pantalla
decía de ella.

**La cifra no se explica.** La fila muestra `pide 277.488` y nada más. No hay
forma de saber qué parte se va este mes y qué parte se está guardando. La 003 ya
resolvió ese mismo problema un nivel más arriba —su AC-10: *«el titular muestra
su trabajo; nada en él es inatribuible»*— y dejó al fondo fuera.

## Decision drivers

- Un aviso que miente es peor que no avisar: desvía al dueño de una función
  correcta.
- La cifra ya está compuesta de términos; no exponerlos es esconder trabajo ya
  hecho.
- La ADR-0028 acotó el camino de lectura del mes a propósito. Nada de esto puede
  costar lecturas nuevas.
- La ADR-0043 estableció que el saldo del fondo es derivado, nunca guardado. Un
  desglose guardado envejecería igual.

## Considered options

### A — Cambiar solo el texto del aviso

Reescribir el mensaje para que no exagere, dejando la condición como está.

- **Pro:** cambio mínimo.
- **Contra:** seguiría saltando en Phone y AI Tools, donde no hay absolutamente
  nada que avisar. El texto sería más suave y seguiría siendo ruido.

### B — Sacar del fondo los cobros mensuales

Que la regla solo cuente lo que se puede repartir, y que el aviso desaparezca
solo.

- **Pro:** el aviso deja de disparar sin tocarlo.
- **Contra:** **rechazado por el dueño el 2026-08-12, con razón.** Services
  pasaría a decir 27.488 y los 250.000 que sí debe este mes no aparecerían en
  ninguna parte. Empeora la pantalla para arreglar el aviso.

### C — El aviso trata sobre una obligación, y el fondo reporta sus términos

- **Pro:** el aviso se vuelve imposible de disparar por un cobro mensual, porque
  un cobro mensual no *puede* repartirse. La condición deja de ser una regla que
  alguien debe recordar y pasa a ser una propiedad de la obligación.
- **Pro:** el desglose son los sumandos que la cifra ya calcula y descarta. Cero
  lecturas nuevas y las líneas cuadran por construcción.
- **Contra:** modifica el comportamiento que la AC-24 de la 003 dejó decidido.

## Decision outcome

**Opción C.**

**1 — El aviso trata sobre una obligación que se podría repartir y no tiene
meses para hacerlo.** No sobre el fondo, y no sobre la obligación más próxima.
Nombra el cobro y cita **su** figura, no el total.

Un cobro que llega cada mes no entra nunca en esa definición: entre uno y el
siguiente no hay meses. Eso convierte la AC-13 de la 014 en una consecuencia de
la definición y no en una condición que haya que comprobar aparte.

**2 — Un fondo reporta los términos de su cifra.** Por cada obligación que está
llenando: cómo se llama, cuánto cuesta, en qué mes cobra, cuánto pide este mes y
si se puede repartir.

Son literalmente los sumandos de

```python
sum(fund_ask_calc(o.required - taken, months_to_fund(year_month, o.charge_month))
    for o, taken in zip(obligations, claimed))
```

conservados en vez de descartados. Por eso las líneas suman la cifra **por
construcción**, y por eso no cuesta ninguna lectura nueva.

**3 — Se lee, nunca se guarda.** Ni el reparto, ni la conversión, ni el mes de
cobro. Es la misma regla que la ADR-0043 puso sobre el saldo y la ADR-0031 sobre
la moneda, por la misma razón: una cifra guardada en agosto seguiría diciendo lo
mismo en diciembre con otra tasa y otro calendario.

**4 — La regla no se ofrece donde nada se puede repartir.** Un fondo que solo
puede pedir 0 no se propone.

## Consequences

**Buenas**

- El aviso deja de disparar en las cuatro categorías donde hoy miente, y sigue
  disparando donde debe: un cobro anual que llega el mes que viene.
- La cifra del fondo se vuelve auditable, como ya lo era el titular del mes.
- El asistente deja de mentir **sin tocarlo**, porque repite el aviso tal cual lo
  recibe.

**Costos**

- La AC-24 de la 003 queda enmendada: su intención se conserva, su disparo
  cambia. Queda escrito aquí y en la `acs.md` de la 014.
- El asistente **no** recibe el desglose: su tarjeta nombra los campos uno por
  uno. Eso se aparta de la AC-28 de la 003 (*«el asistente alcanza los fondos
  igual que el navegador»*), y es deliberado — el dueño decidió el 2026-08-12 no
  tocar el asistente porque se va a deprecar. Divergencia escrita, no
  descubierta.

## Confirmation

- Los 32 escenarios de `features/014-fund-explains-what-it-asks/spec.md`,
  25 de ellos contra la capa de servicios.
- El outline de la AC-13 recorre las cuatro categorías reales que hoy avisan y
  exige que dejen de hacerlo.
- El escenario de la AC-17 exige que cinco fondos se lean sin una lectura por
  fondo.
- Ningún escenario permite que `asks`, `holds` o `carries` cambien.

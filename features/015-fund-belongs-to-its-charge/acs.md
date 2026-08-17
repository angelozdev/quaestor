---
ac_count: 11
high_priority_count: 9
discovered: 2026-08-15
---

# Criterios de aceptación — 015 fund-belongs-to-its-charge

Las cifras de producción de este documento se leyeron el 2026-08-15 en solo
lectura. Las historias que plantean cada decisión usan números de juguete a
propósito: sirven para decidir, no para probar.

**Corrección de hecho sobre la `feature.md`.** Dice que la migración parte
«cuatro fondos de suscripciones» y cita `686.063,64 + 17.465,23 + 277.488,57 +
127.572,22`. Medido: existe **un solo** fondo de cobros, sobre 🛡️ Auto
Insurance. Los otros cuatro son por gasto promedio y están fuera de alcance.
Las otras tres cifras salieron de previsualizaciones del 2026-08-09 sobre
categorías donde nunca se creó un fondo. Además **ningún fondo tiene
`anchor_amount`**: los cinco están en nulo. La migración es 1 → 2 y no hay
nada guardado que repartir.

---

## AC-1: Marcar un cobro en Recurrentes crea su caja

**Priority:** high · **Type:** happy-path

En la lista de Recurrentes, un cobro que se puede repartir ofrece marcarse para
juntar. Marcarlo **es** lo que crea la caja — no abre un formulario, no lleva a
otra pantalla, no propone nada que haya que confirmar después.

Desde ese mes la caja aparta para ese cobro y solo para ese cobro. 🛡️ Seguro
del Carro pasa a ser su propia fila en Fondos, con su propio nombre.

Es el pedido textual del dueño el 2026-08-12: *«tener en la vista de
recurrentes como un check, como marcarlo como fondo»*, y *«yo quiero un fondo
por cada item no por cada categoría»*.

## AC-2: Solo se ofrece a lo que deja un mes libre, y donde no, la pantalla dice por qué

**Priority:** high · **Type:** happy-path

La regla no nombra ninguna cadencia. Dice: **se puede juntar para lo que deja al
menos un mes entero entre un cobro y el siguiente.**

Un seguro que vuelve dentro de un año lo deja. Netflix, que vuelve el mes que
viene, no: si le hicieras caja te pediría los $45 este mes, que es lo que ya
pagás igual.

Escrita así, «cada 45 días» y «cada 6 semanas» se contestan solas por lo que de
verdad hacen, sin que nadie las liste. Es la misma frontera que la ADR-0056
fija para todo el sistema: lo que se repite es agnóstico, lo que se reporta es
mensual.

Donde no se ofrece, la fila lo explica en una línea — no deja un cuadrito
apagado sin motivo.

## AC-3: La fila dice cuánto cuesta, cuándo llega y cuánto pide hoy

**Priority:** high · **Type:** happy-path

Los tres términos, porque con dos no se entiende el tercero.

```
🛡️ Seguro del Carro      pide 636.363,64 este mes
     cuesta 7.000.000 · cobra julio 2027 · 636.363,64 de 7.000.000
```

La cifra sale de una sola división: **lo que falta, entre los meses que quedan
hasta el mes anterior al cobro**, con piso de un mes.

Dos precisiones que el dueño pidió explícitamente el 2026-08-15:

- **«Lo que falta», no «lo que cuesta».** Si la caja ya lleva algo, se descuenta
  antes de dividir.
- **«Hasta el mes anterior».** La plata está completa el último día del mes
  previo al cobro; el mes del cobro no aporta.

Marcado en distintos momentos, un seguro de $1.100 que cobra en julio pide:
ago $100 · ene $183,33 · abr $366,67 · jun $1.100.

## AC-4: Destildar borra la caja entera, y ningún movimiento se toca

**Priority:** high · **Type:** happy-path

No hay estado de pausa. Un cobro está marcado o no lo está.

Destildar borra la caja completa: los meses viejos vuelven a contestar sin ella,
como si nunca hubiera existido. **Ningún movimiento se crea, se borra ni se
modifica** — una caja nunca tuvo plata, solo tuvo una cifra que la app sugería.
Por eso borrarla es barato, y por eso no necesita la devolución que sí necesitó
cancelar una meta (ADR-0055).

**Lo que sí se pierde es el avance.** Volver a marcar crea una caja nueva que
arranca en cero. Una caja que nunca se tocó llega a abril con $800 y pide $100
al mes; una que se destildó en enero y se volvió a marcar en abril pide $366,67.
El dueño lo eligió sabiendo esto, el 2026-08-15.

## AC-5: Un pago anotado a mano puede decir qué cobro saldó

**Priority:** high · **Type:** edge-case

Al guardar un gasto en una categoría donde hay cobros con caja, la app ofrece
enlazarlo:

```
Guardando gasto · 🚗 Carro · -$1.100

   ¿Este pago salda alguno de estos?
     ( ) Seguro   $1.100   julio
     ( ) SOAT        $90   mayo
     (•) Ninguno, es un gasto aparte
```

Si nombra un cobro, su caja se vacía y arranca el ciclo siguiente. Si dice
«ninguno», ninguna caja de cobro se toca.

**El pago dice también cuál vencimiento saldó**, y la app solo pregunta cuando
hay más de uno abierto:

```
   ¿Este pago salda un cobro?
     (•) Club de vinos

   ¿Cuál vencimiento?
     (•) 5 de noviembre de 2026
     ( ) 5 de mayo de 2027
```

Con un solo vencimiento abierto —el caso corriente, la cuenta que acaba de
llegar— se elige solo y no se pregunta nada.

**Sin esto la caja se olvida al mes siguiente.** Pagás el Club de vinos en
agosto por el cobro de noviembre; en agosto la caja lo entiende y arranca el
ciclo siguiente, pero en septiembre vuelve a pedirte los $600.000 del cobro que
ya pagaste, y en octubre otra vez — porque para saber si estaba pagado miraba
solo el mes que te estaba mostrando. El vencimiento saldado queda saldado en
todos los meses que lo lean.

Y resuelve el atrasado por el mismo camino: si el seguro vencía en julio y lo
pagás en agosto, nombrás el vencimiento de julio y la caja junta para el del año
siguiente, no para el subsiguiente.

Si borrás el movimiento, el vencimiento vuelve a estar sin pagar y la caja
retoma. Decidido por el dueño el 2026-08-15, tras el CP7 (ADR-0058).

**Y si el pago deja de saldar sin que lo hayas pedido, la app te lo dice
antes.** Un pago solo puede saldar un cobro de su propia categoría, así que
cambiarle la categoría lo desenlaza. Eso no es lo que fuiste a hacer —vas a
reclasificar un gasto— y en silencio el vencimiento vuelve a estar sin pagar y
la caja se mueve sin que nadie avise:

```
   Editar movimiento
   Categoría   [ 🏠 Hogar        ▾ ]

   ⚠ Este pago salda el vencimiento de julio 2027
     del 🛡️ Seguro del Carro, que está en 🚗 Carro.

     Al moverlo a 🏠 Hogar deja de saldarlo, y la
     caja vuelve a pedir $100.000 al mes.

     [ Cancelar ]   [ Guardar y desenlazar ]
```

Las cifras son las medidas: enlazado la caja pide $47.826 y cobra en 2028-07;
desenlazado pide $100.000 y cobra en 2027-07. Es la misma forma que la quinta
puerta del AC-8 —la app guarda el cambio y avisa antes qué va a pasar, en un
solo paso— y por la misma razón: la que falla callada es la que hay que contar.
Decidido por el dueño el 2026-08-17, tras el CP8.

**Sin esto la caja miente.** Pagás el seguro desde el banco, lo anotás a mano, y
la caja sigue creyendo que tiene los $1.100 con la plata ya gastada — el año
siguiente no te pide nada y llegás sin nada. La alternativa —adivinar que
cualquier gasto del monto correcto fue el cobro— reinstala la misma adivinanza
que esta feature existe para eliminar, y vaciaría la caja del seguro cuando
comprás un extintor de $1.100.

**Esto amplía el alcance de la `feature.md`**, que dejaba el gasto tecleado a
mano fuera. Absorbe el item `link-a-payment-to-the-charge-it-settled`, que
estaba `planned` en el roadmap. Decidido por el dueño el 2026-08-15.

De paso resuelve el pago adelantado y el atrasado: si pagás en junio o en
agosto y decís cuál cobro era, la caja se entera igual.

## AC-6: La mudanza marca los dos cobros, y la cifra del mes no se mueve

**Priority:** high · **Type:** cross-cutting

El fondo de 🛡️ Auto Insurance se convierte en dos cajas, una por cobro, las dos
marcadas. Lo que la app pide en agosto es idéntico antes y después:

| | pide antes | pide después |
|---|---|---|
| 🛡️ Auto Insurance | 686.063,64 | — |
| 🛡️ Seguro del Carro | — | 636.363,64 |
| 🛡️ SOAT carro | — | 49.700,00 |
| **total** | **686.063,64** | **686.063,64** |

Si esa suma cambia, la mudanza está mal.

Destildar el SOAT es un acto posterior del dueño, no algo que la mudanza decida
por él — aunque sea exactamente lo que piensa hacer.

De 5 filas en Fondos se pasa a 6, no a 8.

## AC-7: Un cobro apagado no tiene caja

**Priority:** medium · **Type:** edge-case

Apagar un cobro borra su caja, igual que destildarlo. Volver a prenderlo lo trae
sin caja: si querés juntar de nuevo, lo marcás, y arranca en cero.

Se sigue de AC-4: sin estado de pausa, un cobro apagado no puede sostener una
caja.

## AC-8: Ninguna caja queda huérfana

**Priority:** high · **Type:** cross-cutting

**Una caja existe si y solo si su cobro está marcado y activo.** Ninguna caja le
sobrevive a su cobro.

Las cinco puertas por las que podría quedar una colgando, todas cerradas:

| | |
|---|---|
| destildás el cobro | se borra (AC-4) |
| apagás el cobro | se borra (AC-7) |
| borrás el cobro definitivamente | se borra |
| se archiva la categoría del cobro | la app rechaza el archivado |
| el cobro deja de poder repartirse | se borra, avisando |

La tercera fila la decidió el dueño el 2026-08-15, contra lo que este documento
decía antes: archivar **no** borra las cajas de sus cobros, las rechaza. Es lo
que la app ya hace por el fondo de categoría (003, AC-21) y por la misma razón
— archivar saca la categoría de toda pantalla, así que la plata dejaría de
pedirse sin que nadie avise. La puerta no queda cerrada por limpieza: queda
cerrada porque no abre.

La última es la que falla callada, y es la única que necesitaba decisión: si
editás el Seguro de anual a mensual, deja de cumplir AC-2 y su caja se queda sin
razón de ser. **La app guarda el cambio y avisa antes qué va a pasar**, en un
solo paso:

```
   Al pasar a mensual, este cobro ya no deja meses
   para juntar. Su caja se va a borrar.

   [ Cancelar ]   [ Guardar y borrar la caja ]
```

Pedido por el dueño el 2026-08-15: *«lo que quiero evitar es que no hayan cajas
huérfanas»*. Escrito como «si y solo si» a propósito: es verificable, no una
preferencia.

## AC-9: Un peso se pide una vez y se descuenta una vez

**Priority:** high · **Type:** edge-case

Una categoría puede tener a la vez su caja por gasto promedio y cobros marcados.
Para que eso no cuente doble, **el promedio deja de contar los pagos de los
cobros que ya tienen caja propia**.

En 🍽️ Restaurants gastaste $900 en tres meses, de los cuales $600 fueron el club
de vinos. Sin la regla:

```
   caja del promedio    $300     ← incluye $200 del club
   caja del club        $200
                 total  $500     ← el club, dos veces
```

Con la regla, el promedio mira solo los almuerzos:

```
   caja del promedio    $100
   caja del club        $200
                 total  $300     ← cada peso, una vez
```

**Y el espejo, al descontar:** un peso que cubre un cobro marcado no vacía la
caja de su categoría. Si no, el mismo pago descontaría de dos lados. Un gasto
suelto que no salda ningún cobro sí toca la caja de la categoría, como siempre.

Hoy ninguna categoría del dueño tiene las dos formas a la vez, así que esto no
corrige nada existente: impide un defecto que nada más impide.

## AC-10: La app dice que no, y dice por qué

**Priority:** medium · **Type:** error

Cuatro negativas, cada una con su frase:

- **Un cobro que llega este mismo mes.** Ya no hay tiempo para juntar. La app
  rechaza y dice qué hacer: marcalo después de pagarlo y empezás para el
  próximo. Se rechaza únicamente cuando el próximo cobro cae en el mes en curso
  — el mes anterior sí se acepta, y pide el monto entero en ese mes.
- **Un cobro de ingreso.** No se junta para plata que entra.
- **Un cobro ya terminado**, sin turnos por venir. No hay nada para lo que
  juntar.
- **Un cobro ya marcado.** No se marca dos veces.

Las cuatro frases se leen en español, en la pantalla, sin jerga.

## AC-11: La caja habla la moneda de su cobro

**Priority:** high · **Type:** cross-cutting

Un cobro en dólares se lee entero en dólares. Nada de monedas mezcladas en la
fila:

```
💻 Opal          aparta US$50 este mes
                 lleva US$150 de US$600 · cobra en 9 meses
```

Es el mismo trato que la 009 le dio a una meta: reporta todas sus cifras en su
moneda, y solo su costo en pesos se convierte.

**Lo único que convierte es el total del mes**, porque «lo que te queda libre»
está en pesos y ahí se suma todo junto. Esa conversión pasa una vez, en el
total, al dólar único del día (ADR-0031) — nunca en la fila, y nunca congelada.

Pedido textual del dueño el 2026-08-15: *«si yo aparto 600 dólares en un año,
cada mes se aparten 50 dólares. No quiero combinar monedas cuando no tiene
sentido»*.

Esta AC cae de lleno bajo el CHARTER §6 en su enmienda del 2026-08-13: una cifra
que la app convierte necesita al menos un caso sostenido en otra moneda, escriba
el dueño algo o no. Es literalmente el defecto de hace dos días — fijar «COP»
donde iba la moneda de la meta reportó un aporte de 800 dólares como $800 en vez
de $3.200.000, y pasó 1.325 pruebas verdes.

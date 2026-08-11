---
ac_count: 20
high_priority_count: 14
discovered: 2026-08-11
---

# Acceptance criteria — 013 recurring-charge-keeps-its-price

Descubiertos el 2026-08-11 con el dueño, en la misma sesión que el discuss que
promovió la feature. Las cifras que se citan son sus cobros reales: Hevy Pro a
99.900 COP al año y Smart Fit a 120.000 COP al mes, los dos debitados de
DolarApp, que es una cuenta en dólares. La tasa que aparece en los ejemplos es
3.142, la que la app tiene cargada hoy.

## Las dos reglas

Todo lo de abajo sale de estas dos. Donde un criterio parezca agregar algo
nuevo, es una de ellas aplicada a una pantalla.

**1 — El precio es el del comercio, y no cambia porque cambie la cuenta.** Una
regla guarda el número que el comercio anuncia, en la moneda en que lo anuncia.
De qué cuenta sale la plata es una decisión aparte y posterior. Hevy Pro cuesta
99.900 COP se pague desde donde se pague; escribirlo como 30,22 USD fue guardar
una conversión en vez de un precio, y una conversión envejece.

**2 — Ninguna cifra convertida se aplica sola.** Cuando el precio y la cuenta no
comparten moneda, la app propone la conversión a su tasa única (ADR-0031) y el
dueño la acepta o la reemplaza. Nunca se registra plata que él no vio, y la
propuesta jamás es obligatoria.

## Lo que nunca debe construirse

**Que el motor convierta y cobre solo.** Se midió en el discuss: un cobro que se
registra solo copia el monto y la moneda de la regla y se los suma al saldo de
la cuenta. Con la regla en pesos y la cuenta en dólares, eso le sumaría 99.900
al saldo en dólares de DolarApp. Por eso AC-2 es un rechazo y no una
conveniencia — es lo único que separa esta feature de un hueco de plata.

---

## AC-1: Una regla puede guardar un precio en otra moneda que su cuenta

**Priority:** high · **Type:** functional

El dueño crea Hevy Pro con precio **99.900 COP** al año y cuenta **DolarApp**,
que es en dólares. La app lo guarda. Hoy lo rechaza.

## AC-2: Una regla que se cobra sola no puede tener el precio en otra moneda

**Priority:** high · **Type:** error

El dueño crea Hevy Pro con precio en pesos sobre DolarApp y la marca para que se
cobre sola. La app **lo rechaza** y le dice por qué: un cobro que se registra
solo tendría que convertir sin él. Puede resolverlo poniéndola a confirmar a
mano, o cambiándole la cuenta a una en pesos. Lo mismo al editar una regla
existente: no puede volverse automática mientras su precio esté en otra moneda,
ni puede mudarse a otra moneda mientras esté marcada para cobrarse sola.

## AC-3: La lista de recurrentes muestra el precio y lo que costaría hoy

**Priority:** medium · **Type:** functional

En la pantalla de recurrentes, Hevy Pro dice **99.900 COP (≈US$31,79) ·
DolarApp**. La primera cifra es la que el dueño controla; la segunda es
informativa, se mueve sola con la tasa y nunca es la que el banco termina
cobrando.

## AC-4: Sin tasa cargada, la lista muestra el precio y calla la conversión

**Priority:** medium · **Type:** edge

Si la app no tiene tasa cargada, la fila dice **99.900 COP · DolarApp** y nada
más. No hay error, no hay pantalla en blanco, no hay una cifra inventada.

## AC-5: El cobro nace esperando, en la moneda de la regla

**Priority:** high · **Type:** functional

Llega el 15 de julio. El cobro de Hevy Pro aparece en **por pagar** por
**99.900 COP**, sobre DolarApp. Aparece con la moneda de la regla, no con la de
la cuenta, y esperando — nunca registrado.

## AC-6: Un cobro esperando no mueve ningún saldo

**Priority:** high · **Type:** functional

Mientras el cobro de Hevy Pro está en por pagar, el saldo de DolarApp es
exactamente el mismo que antes de que naciera. Ni en pesos ni en dólares.

## AC-7: Confirmar propone la conversión, y se puede cambiar

**Priority:** high · **Type:** functional

El dueño abre el cobro para confirmarlo. La casilla del monto llega con
**US$31,79** ya escrito — 99.900 COP a la tasa de la app — y dice dólares. Él lo
reemplaza por **US$32,10**, que es lo que DolarApp realmente debitó, y confirma.

## AC-8: Lo que queda registrado está en la moneda de la cuenta

**Priority:** high · **Type:** functional

El movimiento que queda dice **US$32,10** sobre DolarApp. No guarda los 99.900
COP, no guarda la tasa que se usó, y no queda ninguna cifra en pesos pegada a
él. El precio en pesos vive en la regla; el movimiento guarda lo que salió.

## AC-9: El saldo se mueve por la cifra en la moneda de la cuenta

**Priority:** high · **Type:** functional

Al confirmar, el saldo de DolarApp baja **US$32,10** — no 99.900, ni 99.900
dólares, ni nada convertido dos veces.

## AC-10: Sin tasa al confirmar, no hay propuesta pero sí confirmación

**Priority:** high · **Type:** edge

El dueño abre el cobro para confirmarlo y la app no tiene tasa cargada. La
casilla llega **vacía**, la app dice que no puede proponerle una cifra, y él
escribe US$32,10 y confirma normalmente. Una tasa faltante nunca le impide
registrar plata que ya salió de su cuenta.

## AC-11: Confirmar desde otra cuenta sigue funcionando

**Priority:** medium · **Type:** functional

El cobro de Hevy Pro está sobre DolarApp pero el dueño lo pagó desde Nu, que es
en pesos. Al confirmar elige Nu y escribe **99.900 COP**. Queda registrado en
pesos sobre Nu, el saldo de Nu baja 99.900 y el de DolarApp no se mueve. La
regla sigue declarando DolarApp: fue una excepción de un mes, no una mudanza.

## AC-12: Una regla donde precio y cuenta coinciden se comporta igual que hoy

**Priority:** high · **Type:** functional

Opal cuesta 9,99 USD y se cobra a DolarApp. Nada de esta feature la toca: se
crea igual, puede cobrarse sola, nace igual y se confirma igual. Ninguna
conversión aparece en ninguna pantalla.

## AC-13: Mover la cuenta propone la conversión, nunca la exige

**Priority:** high · **Type:** functional

El dueño mueve Opal (9,99 USD) de DolarApp a Nu, que es en pesos. La app le
**propone 31.388 COP** en la casilla del monto, editable. Si la acepta, Opal
queda en pesos; si la borra y deja 9,99 USD, Opal queda en dólares sobre una
cuenta en pesos, que es AC-1 en el otro sentido. Igual en la dirección
contraria. La app sugiere porque cambiar de cuenta suele significar algo, pero
el precio es del dueño.

## AC-14: Un cobro que ya espera conserva el precio con el que nació

**Priority:** medium · **Type:** edge

Hay un cobro de Hevy Pro esperando por 99.900 COP. El dueño sube el precio de la
regla a 110.000. El cobro que espera **sigue diciendo 99.900**, y si está mal él
lo corrige al confirmarlo, que es donde escribe la cifra real de todos modos.
Es lo que la app ya hace con la fecha, la categoría y la cuenta. *(Que todos los
campos alcancen al cobro que espera se decidió el 2026-08-11 como feature
aparte; esta se queda con el comportamiento de hoy.)*

## AC-15: Los cobros ya registrados no se tocan

**Priority:** high · **Type:** edge

El dueño cambia el precio o la moneda de Hevy Pro. Los cobros de años
anteriores, ya registrados, conservan su cifra y su moneda exactas. Un cambio
en la regla nunca reescribe lo que ya pasó.

## AC-16: Los rechazos que ya existen siguen rechazando

**Priority:** medium · **Type:** error

Un precio de cero o negativo, una moneda que la app no maneja, una regla de tipo
traslado, un intervalo menor que uno, una fecha de fin anterior a la de inicio y
una cuenta que no existe se siguen rechazando exactamente igual que hoy. Esta
feature quita una atadura, no las demás.

## AC-17: El asistente no cambia

**Priority:** medium · **Type:** cross-cutting

El asistente sigue exigiendo que la moneda de la regla coincida con la de su
cuenta. La app y el asistente quedan diciendo cosas distintas **a propósito**:
el dueño decidió el 2026-08-11 no gastar alcance ahí porque el asistente se va a
deprecar. ADR-0006/0009 piden paridad; esta divergencia queda escrita en vez de
descubierta.

## AC-18: Un cobro esperando en otra moneda cuenta por su propia moneda

**Priority:** high · **Type:** cross-cutting

El informe del mes y los totales de por pagar leen el cobro de Hevy Pro como
**99.900 pesos**, no como 99.900 dólares ni como US$31,79 convertidos dos veces.
Cada cifra se convierte por la moneda que ella misma declara, no por la de su
cuenta. Es la primera vez que existe una fila cuya moneda no es la de su cuenta,
así que esto se comprueba en vez de suponerse.

## AC-19: La migración deja las dos reglas con su precio verdadero

**Priority:** high · **Type:** cross-cutting

Después de migrar, Hevy Pro dice **99.900 COP al año** y Smart Fit **120.000 COP
al mes**. Las dos siguen cobrándose a DolarApp. Las dos quedan marcadas para
confirmarse a mano, porque AC-2 prohíbe lo contrario: de aquí en adelante Smart
Fit espera un clic al mes y Hevy Pro uno al año, y en ese clic el dueño escribe
la cifra real que el banco tomó. Ningún saldo se mueve por la migración y ningún
movimiento ya registrado se toca.

## AC-20: La migración carga los precios, no los calcula

**Priority:** high · **Type:** cross-cutting

Los dos números se escriben tal cual, no se derivan de nada. Convertir los 30,22
USD guardados a la tasa de hoy daría **94.951 COP** y el precio es 99.900;
convertir los 37,20 USD daría **116.882** y el precio es 120.000. La tasa con la
que se escribieron (≈3.306) no existe en ninguna parte, y ADR-0031 quitó a
propósito las tasas congeladas por movimiento. Una migración que convierta
escribiría dos números nuevos, mal — el defecto que esta feature existe para
eliminar.

> ▶ CP6 Refine — 4/4 criteria met | NEXT: /engineer.crap-analyzer para CP7, con agente fresco | BLOCKED: none

# Progress — 013 recurring-charge-keeps-its-price

Una regla recurrente guarda el precio del comercio, no la moneda de la cuenta.
21 criterios, 54 escenarios. **Verde**, y la migración corrida contra los datos
reales el 2026-08-12 con el dueño delante.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done | 2026-08-11T1658-feature-init.md |
| 2 | ACs | done — aprobados por el dueño 2026-08-11, tras la revisión contra otros sistemas | 2026-08-11T1745-discover-acs-review.md |
| 3 | Spec | done — aprobado por el dueño 2026-08-11; **rojo**, 38/47 tests de servicio fallan | 2026-08-11T1815-atdd.md |
| 4 | Plan | done — ADR-0053 aceptada, reemplaza la 0052; runbook para la migración | 2026-08-11T1756-plan.md |
| 5 | Implement | done — las cinco rebanadas, migración incluida | 2026-08-11T2230-implement.md |
| 6 | Refine | done — firmado por un refinador independiente que encontró un defecto que la primera pasada no vio | 2026-08-12T0900-refine-independent.md |
| 7 | Verify | — | — |
| 8 | Harden | — | — |

## Las dos reglas de las que sale todo

1. **El precio es el del comercio, y no cambia porque cambie la cuenta.** Hevy
   Pro cuesta 99.900 COP se pague desde donde se pague. Escribirlo como 30,22
   USD fue guardar una conversión en vez de un precio, y una conversión
   envejece: el próximo julio esos mismos 99.900 COP son otra cifra en dólares.
2. **Ninguna cifra convertida se aplica sola.** Cuando el precio y la cuenta no
   comparten moneda, la app propone y el dueño acepta o reemplaza. Nunca es
   obligatoria — salvo donde aceptar es la única salida de un estado que AC-2
   prohíbe.

## Lo que nunca debe construirse

**Que el motor convierta y cobre solo.** Medido en el discuss: cuando un cobro
nace copia el monto **y la moneda** de su regla, y si la regla se cobra sola le
suma esa cifra al saldo de la cuenta. Regla en pesos, cuenta en dólares, cobro
automático: **99.900 sumados a un saldo en dólares**. AC-2 es un rechazo por
eso, no por comodidad.

## Decidido en el discuss y en CP2

| | |
|---|---|
| Quién convierte el día del cobro | el dueño, sobre la cifra que la app propone |
| Qué recuerda el movimiento | solo lo que salió; ADR-0031 intacta |
| Dónde vive el precio en pesos | en la regla |
| Alcance | reglas recurrentes; no las otras tres puertas de escritura |
| Una regla que se cobra sola | no puede discrepar de su cuenta — se rechaza |
| Mover la cuenta | sugiere la conversión; la exige solo si la regla se cobra sola |
| Las dos reglas mal guardadas | las migra el feature, con los precios cargados |
| El asistente | no se le da ni se le quita nada — se va a deprecar |

## Lo que la revisión contra otros sistemas encontró

Pedida por el dueño el 2026-08-11. **AC-2 y AC-13 se contradecían** en su propio
caso: Opal se cobra sola en 9,99 USD sobre DolarApp, se mueve a una cuenta en
pesos y se borra la conversión sugerida — AC-13 lo permitía, AC-2 lo prohibía.
Resuelto con rechazo, no con cambio silencioso de modo.

**AC-8 deja a Quaestor solo.** GnuCash guarda dos cifras por movimiento, Firefly
III exige un «foreign amount», Lunch Money guarda la tasa histórica de cada
movimiento, IAS 21 registra a la tasa del día. Quaestor guarda una, a propósito
(ADR-0031). En vez de reabrir eso entró **AC-21**: el cobro muestra el precio de
su regla al lado de lo que salió, leído de la regla ya enlazada, sin guardar
nada. Sin eso, un cobro de julio por US$32,10 se lee como 141.240 COP en
diciembre contra un precio real de 99.900 — 41% de más.

El caso tiene nombre en la industria de pagos: *presentment* contra
*settlement*. AC-5 y AC-8 son esa separación aplicada.

## Lo que CP3 encontró de sí mismo

Dos escenarios se escribieron con nombres copiados de la AC-4 de la 012.
`spec-coverage` los cruzó contra los tests de esa feature y los dio por
cubiertos: habrían quedado verdes probando otra cosa. Detectado comparando 9
UNBOUND reportados contra 11 escenarios sin etiqueta escritos. Renombrados.

## Lo que se decidió NO hacer aquí

**Que un cambio de regla alcance al cobro que ya espera.** El dueño eligió la
versión amplia — todos los campos, no solo el precio — así que se archivó como
`id:rule-change-reaches-the-waiting-charge`. La parte difícil es distinguir un
cobro intacto de uno que él ya editó a mano, y esa distinción no existe en los
datos. 013 se queda con el comportamiento de hoy (AC-14).

## Deudas conocidas, anotadas

- La migración toca datos reales: CHARTER §7 exige respaldo fresco y presencia
  del dueño, y el manifiesto topa `migrations/**` en autonomía `low`.
- 11 escenarios de pantalla siguen sin test de vitest — son de CP5.
- La ADR que reemplaza a la 0052 se escribe en CP4.

## Handoff log

| When | Skill | Agent | Result |
|---|---|---|---|
| 2026-08-11T1650 | discuss | main | promovido `id:recurring-currency-independent-of-account`; cuatro decisiones, y la colisión con ADR-0052 identificada como reemplazo |
| 2026-08-11T1658 | feature-init | main | 013 asignada, rama cortada de main en e2ba3ee; autonomía media con la migración topada en low |
| 2026-08-11T1723 | discover-acs | main | 20 criterios; leer el motor convirtió una preferencia en necesidad — AC-2 evita un hueco de plata |
| 2026-08-11T1745 | discover-acs (revisión) | main | medido contra GnuCash, Firefly III, Lunch Money, Stripe e IAS 21; AC-13 partido por modo, AC-21 agregado |
| 2026-08-11T1815 | atdd | main | 53 escenarios, 38/47 rojos en la guarda correcta; dos escenarios vacíos por colisión de nombre, detectados y renombrados |
| 2026-08-11T1756 | plan | main | la arquitectura es un borrado más un invariante; el motor no cambia una línea y confirmar es una; ADR-0053 reemplaza la 0052; runbook de 7 pasos para la migración |
| 2026-08-11T2230 | implement | main | rebanadas 1, 2, 3 y 5; cuatro defectos encontrados y arreglados, uno mío de verdad; el navegador vio el saldo caer por los dólares y nunca por los pesos; la migración sigue sin correr |
| 2026-08-12T0820 | runbook | main | rebanada 4: respaldo, ensayo sobre copia restaurada, producción y verificación del dueño. El ensayo encontró dos defectos que ninguna suite veía — el enum de Postgres y un `downgrade` que habría encendido cobro automático |
| 2026-08-12T0840 | refine (pasada, sin firma) | main | tres limpiezas, las tres elegidas por el dueño; `currencyForAccount` muere y el que queda no puede inventar pesos. Firma inválida: mismo agente que implementó |
| 2026-08-12T0900 | refine | refiner-independent | firma válida de CP6. Coincide con la pasada anterior y **encuentra lo que no vio**: el diálogo de crear dejaba el precio del cobro anterior en la casilla del siguiente |

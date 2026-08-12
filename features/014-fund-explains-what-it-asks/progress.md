> ▶ CP5 Implement — 0/6 criteria met | NEXT: CP6 refine, con agent_id distinto | BLOCKED: none

# Progress — 014 fund-explains-what-it-asks

Un fondo dice de dónde sale su cifra, y su aviso deja de mentir. 18 criterios,
32 escenarios. **Esta feature es de lectura**: nada se guarda, no hay migración,
y ninguna cifra que la app ya reporta puede moverse.

## Checkpoints

| CP | Stage | Status | Handoff |
|---|---|---|---|
| 1.5 | Ready | done — promovida del roadmap `fund-mixed-interval-categories` | 2026-08-12T1130-discuss.md |
| 2 | ACs | done — aprobados por el dueño 2026-08-12 | 2026-08-12T1210-discover-acs.md |
| 3 | Spec | done — aprobado por el dueño 2026-08-12; **rojo**, 26 de 28 fallan | 2026-08-12T1245-atdd.md |
| 4 | Plan | done — ADR-0054 aceptada, cuatro rebanadas, sin runbook | 2026-08-12T1320-plan.md |
| 5 | Implement | done — las cuatro rebanadas; 28/28 de servicio, 1.190 unitarias, 630 de aceptación, 545 de pantalla | — |

## Las dos reglas de las que sale todo

1. **El aviso trata sobre una obligación que se podría repartir y no tiene meses
   para hacerlo** — no sobre el fondo, y no sobre la más próxima. Un cobro
   mensual no entra nunca en esa definición, porque entre uno y el siguiente no
   hay meses. Por eso el AC-13 es una consecuencia, no una condición que haya
   que recordar comprobar.
2. **El fondo reporta los términos de su cifra.** Son los sumandos que la suma
   ya calculaba y descartaba, conservados en vez de tirados. De ahí que las
   líneas cuadren por construcción (AC-4) y que no cueste ninguna lectura nueva
   (AC-17).

## Lo que no se toca

`asks`, `holds`, `carries`, `on_track`, `next_month_has`, el motor de
ocurrencias y las reglas `fixed` y `average`. El asistente tampoco: su tarjeta
nombra los campos uno por uno, así que el desglose no le llega. **Divergencia
decidida por el dueño y escrita** en ADR-0054 → Costos y en el tercer grupo de
`tests/mcp/test_fund_card_parity.py`.

La corrección del aviso sí le llega gratis, porque lo imprime tal cual.

## Verification reports

### CP5 — rebanada 4, el navegador (sandbox)

Conducido contra el sandbox el 2026-08-12. Cada criterio, leído en pantalla:

| | Lo que se leyó |
|---|---|
| AC-1, AC-2, AC-4 | `$ 180.000` y debajo `Internet — vence este mes · $ 80.000` y `Dominio — se guarda para agosto de 2027 · $ 100.000 de $ 1.200.000` |
| AC-3 | «vence este mes» contra «se guarda para agosto de 2027» |
| AC-6 | omitir Internet lo sacó del desglose y bajó el total a `$ 100.000` |
| AC-8 | sin cobros vivos este mes: «Este mes no hay nada que apartar: sus cobros están omitidos o ya pagados.» |
| AC-9 | sin cobros en la categoría: «La categoría ya no tiene cobros recurrentes, así que pedirá $ 0 siempre.» |
| AC-11, AC-12 | el aviso saltó, nombró el Seguro y citó `$ 6.000.000` — no los `$ 6.050.000` del fondo |
| AC-13 | con Internet mensual + Dominio anual el fondo se creó **sin aviso**; hoy habría avisado |
| AC-14 | «Pago mis suscripciones mes a mes» desapareció en una categoría de solo mensuales, y la selección cayó a la primera regla |

**Dos defectos que solo el navegador vio, y los dos en texto que esta feature
escribió:** el aviso salía en inglés en una app en español, y con la plata sin
formatear (`6000000.00` donde toda la pantalla dice `$ 6.000.000`). El servicio
pasó a reportar el cobro y la pantalla a escribir la frase, que es donde vive el
idioma y el formato. El asistente sigue recibiendo su cadena, sin tocarlo.

El aviso **no tenía ni un test de pantalla** — el navegador era lo único que lo
ejercitaba. Tres tests nuevos, y el primero se comprobó matando una mutación
(citar el total en vez del cobro lo pone rojo).

### CP5 — rebanadas 1 y 2

- **Aceptación 014:** 28/28 escenarios `@backend`. Los 7 UNBOUND son los de
  pantalla, y son el trabajo de la rebanada 3.
- **Aceptación del proyecto:** 626 verdes, sin regresión — incluidos los 71
  pasos que la 003 dejó sobre fondos.
- **Unitarias backend:** 1.190 verdes. `import-linter`: 2 contratos intactos.

## Handoff log

- 2026-08-12T1130 — discuss: el aviso miente cuando la categoría mezcla
  intervalos; medido contra producción, el reparto sí funciona.
- 2026-08-12T1210 — discover-acs: 18 criterios, 9 altos.
- 2026-08-12T1245 — atdd: 32 escenarios, 25 `@backend` y 7 de pantalla.
- 2026-08-12T1320 — plan: ADR-0054, cuatro rebanadas, sin runbook.

## Defectos encontrados durante CP5, y no por las suites

**El generador se tragaba el `Background`.** Ningún escenario de la 014 corría
sus dos pasos previos, así que la suite usaba la tasa que la fixture sembraba
(4.200) en vez de la que el spec declara (4.000). El cobro en dólares pedía
10.500 donde el spec pide 10.000 — verde por la razón equivocada en todo lo
demás. Arreglado en `acceptance/generator.py`; la 014 es la única feature con
`Background`, así que ninguna otra suite cambia de comportamiento.

**Cuatro escenarios míos fijaban lo contrario de su propio criterio.** Dos del
AC-5 pedían mover cifras que el AC-5 declara defecto si se mueven (`spreads_over`
12 en vez de 1; `carries` 300.000 en vez de 375.000); uno del AC-6 se olvidaba
de crear el fondo; y uno del AC-18 le preguntaba al asistente por la lista, que
nunca ha mostrado plata, esperando leer una cifra. Corregidos con permiso
explícito del dueño el 2026-08-12.

## Tracker sync

local — el feature folder es el tracker. Roadmap `fund-mixed-interval-categories`
en `in-progress`.

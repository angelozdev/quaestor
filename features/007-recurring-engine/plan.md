---
slug: recurring-engine
checkpoint: 4
plan_status: approved
created: 2026-08-02
---

# Plan — 007 recurring-engine

Arquitectura confirmada por Angelo en sesión 2026-08-02, con el criterio
explícito de **bajo acoplamiento y alta cohesión**. Cierra los 24 escenarios
rojos de aceptación repartidos en diez ACs: AC-6 (1), AC-12 (6), AC-13 (1),
AC-17 (2), AC-20 (2), AC-21 (2), AC-22 (2), AC-24 (2), AC-25 (2), AC-26 (1) y
AC-28 (3). Los otros 53 escenarios ya pasan contra el código actual — son el
candado de regresión de esta feature.

Huella de datos: **2 valores de enum, 0 columnas nuevas, 0 tablas nuevas, 1
migración**. El resto es reorganización de servicios, adaptadores y frontend.

El motor es la única superficie que mueve un saldo sin acción del usuario, así
que toda divergencia no detectada cuesta dinero real. Eso gobierna el orden de
las fases: primero que el run no se caiga, después las reglas de ciclo de vida,
al final las decisiones interactivas.

## Architecture

### Dónde vive el código

El layering del charter (`api/` → `services/` → `domain/` → `db.py`) no cambia.
Lo que cambia es el corte **dentro** de `services/`: hoy `recurring.py` (325
líneas) es catálogo y motor a la vez, y con esta feature llegaría a ~520
mezclando tres responsabilidades. Se parte por razón de cambio.

| Módulo | Responsabilidad única | Cambia cuando |
|---|---|---|
| `domain/recurrence.py` **(nuevo)** | matemática de fechas de vencimiento, pura | cambia la cadencia o el ajuste de fin de mes |
| `services/recurring.py` | el catálogo: declarar, listar, editar, apagar, encender | cambia qué es una obligación |
| `services/occurrences.py` **(nuevo)** | el único módulo que escribe una `RecurringOccurrence`: cobrar, ofrecer, aceptar, rechazar, saltar, cerrar | cambia la política de materialización |

**Grafo de dependencias — un solo sentido, sin ciclos:**

```
jobs/daily.py            ──►  services/occurrences.py  ──►  domain/{recurrence,rules,models,dtos}
services/recurring.py    ──►  services/occurrences.py
services/planned.py      ──►  services/occurrences.py
services/transactions.py ──►  (registro de hooks; no importa recurring ni occurrences)
services/bootstrap.py    ──►  services/{occurrences, transactions, planned}
api/routers/recurring.py ──►  services/{recurring, occurrences}
mcp/tools/temporal.py    ──►  services/{recurring, occurrences}
```

`occurrences.py` recibe la `RecurringItem` como parámetro y **nunca importa el
catálogo**; el catálogo sí importa `occurrences` (reanudar cierra la pausa). Esa
asimetría es lo que evita el ciclo.

**Invariante verificable:** fuera de `services/occurrences.py` ningún módulo
escribe `RecurringOccurrence`. Para que sea cierta y no aspiracional, los dos
helpers de `planned.py` que hoy tocan el estado de la ocurrencia
(`_occurrence_of`, `_sync_occurrence_posted`) se mudan a `occurrences.py` y
`planned.py` los llama. Es el único archivo de la feature 006 que se toca, y el
cambio es un movimiento, no una reescritura — AC-27 (verde hoy) es su candado.

**Extracción de `due_dates`.** Sale de `domain/rules.py` hacia
`domain/recurrence.py` junto a `_add_interval`, `_add_months` y los dos helpers
nuevos (`is_due_on`, `has_ended`). `rules.py` hoy mezcla signos de saldo,
fechas de recurrencia, sobres de presupuesto y progreso de metas — cuatro temas
sin relación. Radio de impacto real: 3 líneas de import (`services/recurring.py`,
`services/budgets.py`, `backend/tests/domain/test_recurrence.py`), y el test ya
lleva el nombre del módulo que se está creando.

**Archivos tocados:**

| Archivo | Cambio |
|---|---|
| `domain/models.py` | `OccurrenceStatus.offered`, valor de motor en `Source` |
| `domain/recurrence.py` | nuevo — matemática de fechas + `is_due_on` + `has_ended` |
| `domain/rules.py` | pierde la sección de recurrencia |
| `domain/dtos.py` | `MaterializationReport`, `RunFailure` |
| `services/recurring.py` | catálogo; pierde materialización y skip |
| `services/occurrences.py` | nuevo — todo lo que escribe una ocurrencia |
| `services/planned.py` | los 2 helpers de ocurrencia se van; llama a `occurrences` |
| `services/transactions.py` | registro `POST_DELETE_HOOKS` |
| `services/bootstrap.py` | engancha el hook de cierre de fecha |
| `jobs/daily.py` | el reporte diario propaga los fallos |
| `api/routers/recurring.py`, `api/schemas.py` | 3 endpoints: ofrecer / aceptar / rechazar |
| `mcp/tools/temporal.py`, `mcp/registry.py`, `mcp/format.py` | paridad MCP (ADR-0006/0009) |
| `migrations/versions/0008_*.py` | los 2 valores de enum |
| `frontend/app/(app)/recurring/` | diálogo de fechas ofrecidas (componente propio) + marca "terminada" |
| `frontend/app/(app)/transactions/page.tsx`, `lib/api/types.ts`, `lib/api/recurring.ts` | insignia de motor + 3 llamadas |

### D1 — Las fechas pasadas se ofrecen (AC-12, AC-26) — ADR-0035

Declaras Netflix semanal el 2 de agosto con inicio el 12 de julio. La app
muestra 4 fechas (12, 19, 26 jul, 2 ago) y no toca los 500.000 hasta que
respondas. Marcas 2 → salen 51.800 y el saldo queda en 448.200. Rechazas las
otras 2 → nunca vuelven a aparecer y ningún run posterior las recrea.

**Forma.** Un cuarto estado de la ocurrencia: `offered`. La ocurrencia ya es
única por `(obligación, fecha)` y el motor ya ignora toda fecha que tenga
ocurrencia, así que:

- ofrecer = escribir la fila en `offered`
- aceptar = materializarla como cualquier otra (`posted` o `planned`)
- rechazar = pasarla a `skipped`, estado que ya existe y ya bloquea la recreación

Cero tablas nuevas, cero columnas.

**Cómo se separa de AC-9.** `create_recurring` recibe `declared_on` (por defecto
hoy, **no se persiste**). Las fechas anteriores a `declared_on` se ofrecen; las
posteriores las cobra el motor desatendido. La obligación que "ya existía" se
declara con `declared_on = start_date` y entonces no hay nada pasado que
ofrecer. Es literalmente la regla escrita en el preámbulo de `spec.md`.

Mover el inicio hacia atrás (`update_recurring`) ofrece las fechas que ese
cambio abre y que ya vencieron — la regla ahí es "anterior a hoy", sin necesidad
de recordar cuándo se declaró.

**Alternativa descartada.** Tabla aparte de decisiones pendientes: duplica la
clave `(obligación, fecha)` y obliga a consultarla en cada run.

### D2 — "Terminada" no es "apagada" (AC-13, cierra W3) — ADR-0037

El Gimnasio con fin el 26 de julio desaparece de la lista viva el 27, pero la
lista de apagadas distingue "yo lo apagué" de "esto se acabó". Extiendes el fin
al 16 de agosto y vuelve, sin tocar ningún interruptor.

**Forma.** Se **deriva al leer**: terminada ⟺ `end_date is not None and
end_date < hoy`. El flag `active` conserva exactamente el significado que le da
ADR-0005 — el usuario lo apagó. Sin migración y **sin superseder ADR-0005**.

**Consecuencia.** El motor deja de reusar `list_recurring(active=True)` para
decidir a quién cobrar: una obligación terminada con una fecha pendiente por
caída del servidor todavía debe cobrarse. `occurrences.run_due` hace su propia
consulta. Lista viva ≠ conjunto a materializar.

**Consecuencia en los handlers de aceptación.** Dos bindings cambian —
`"X" is switched off` y `"X" is live` pasan a leer el estado vivo/terminado tal
como lo calcula la lista, no el flag crudo. Es el binding el que sigue al
diseño, no al revés.

**Alternativa descartada.** Un tercer estado real en la tabla: supersedería el
ciclo de vida uniforme de ADR-0005 por un caso que no necesita persistirse, y
dejaría `restore` reactivando algo que no produce nada.

### D3 — Reanudar ofrece lo que quedó atrás (AC-17, cierra W4) — ADR-0037

Gimnasio de 8.000 semanal pausado 21 días. Al reanudar, las 2 fechas que
quedaron atrás **se te ofrecen** —marcas las que sí debías, descartas las de la
pausa— y solo se cobra la de hoy sin preguntar. Si las descartas todas, el saldo
queda en 484.000; si las reclamas, en 476.000. Nunca en 468.000 de golpe.

**Forma.** `restore_recurring` delega en `occurrences.offer_paused_stretch`, que
escribe `offered` para toda fecha vencida sin materializar, estrictamente
anterior a hoy. **Sin columna de marca de agua.**

**Por qué ofrecer y no cerrar** *(corregido tras revisión independiente)*. La
primera versión escribía `skipped` y esta sección afirmaba que la puesta al día
tras una caída quedaba intacta "porque no pasa por `restore`". Era falso: una
pausa **después** de una caída arrastra las fechas de la caída. Reproducido —
motor caído 3 semanas, apagar y encender el mismo día, 16.000 COP escritos como
saltados sin avisar.

`restore` no puede distinguir las dos causas, y el usuario sí. Así que deja de
decidir y pregunta, reusando el mecanismo de AC-12 completo. Ningún escenario
aprobado cambió: 201/201 siguen verdes, porque ninguno aserta en qué estado
quedan esas fechas, solo que no se cobran.

**Alternativa descartada.** Guardar `paused_on`/`resumed_on`: estado invisible
que hay que mantener sincronizado, y en el escenario 1 de AC-17 (apagar y
reanudar el mismo día) el intervalo saldría vacío y cobraría de más.

### D4 — Un fallo no cuesta el día (AC-24, AC-22) — ADR-0036

Nequi retirada: Netflix y Claro cobran igual y el saldo de Bancolombia queda en
434.100; Spotify no cobra nada y el reporte del día nombra solo a Spotify.
Mañana, con Nequi de vuelta, Spotify entra.

**Forma.** **Un commit por cobro**, no por lote. Cada cobro es todo-o-nada
—movimiento, saldo y ocurrencia juntos, o ninguno— y los fallos se acumulan.
`materialize_due` deja de devolver una lista y devuelve
`MaterializationReport(created, failures)`; `run_daily` lo propaga a su reporte.
Cada `RunFailure` nombra la obligación y la razón.

**Por qué no savepoints.** Es la opción obvia y aquí está rota: la documentación
de SQLAlchemy advierte que con el driver `pysqlite` en su modo por defecto *"un
SAVEPOINT emitido antes de un BEGIN funciona por su cuenta pero no participa en
la transacción que lo contiene"*. La suite de aceptación corre exactamente en
SQLite en memoria con ese driver, así que el aislamiento sería real en Postgres
y falso en los tests — el peor resultado posible. Un commit por cobro se
comporta idéntico en los dos motores. Coste: ~8 commits/día en vez de 1,
irrelevante a esta escala.

Habilitar el workaround documentado (`isolation_level = None` + emitir `BEGIN`
por evento) queda descartado: cambia el comportamiento transaccional de toda la
suite para resolver un problema de un solo módulo.

### D5 — El movimiento dice que lo hizo el motor (AC-25) — ADR-0038

En la lista de movimientos el cargo de Netflix se ve marcado como hecho por el
motor y nombra a Netflix; los 30.000 registrados a mano en la tienda no llevan
esa marca.

**Forma.** Valor nuevo en `Source`. El vínculo `recurring_id` ya se guarda desde
siempre; lo que falta es mostrarlo. Frontend: insignia en la lista de
movimientos.

**Detalle de migración.** Son enums nativos de Postgres
(`sa.Enum(..., name='source')`), y `ALTER TYPE … ADD VALUE` no puede correr
dentro del bloque transaccional de Alembic — va envuelto en
`op.get_context().autocommit_block()`. La misma migración `0008` añade `offered`
(D1) y este valor.

### D6 — Borrar el cargo cierra la fecha (AC-28) — ADR-0038

Borras el cargo de Netflix del 2 de agosto: vuelven los 25.900 y el 2 de agosto
queda saltado para siempre. El 9 de agosto llega normal. Es la salida a la que
AC-20 manda al usuario cuando le niega saltar una fecha ya cobrada.

**Forma.** Un registro `POST_DELETE_HOOKS` en `transactions.py`, con
`occurrences.py` aportando el hook que cierra la fecha y `bootstrap.py`
enganchándolo — el mismo patrón que ya usan `POST_CONFIRM_HOOKS` y
`ROLLOVER_HOOKS`. Así `transactions.py` (feature 002) no adquiere ninguna
dependencia hacia el motor.

**Alternativa descartada.** Sincronizar directo dentro de `_delete_single`: más
corto, pero mete la feature 007 dentro del archivo de la 002.

### D7 — Los ingresos son siempre automáticos (AC-6)

Declarar un sueldo "que espera aprobación" se rechaza. Nadie podría
confirmarlo: la cola de pendientes no muestra ingresos (feature 006), así que
quedaría esperando donde ninguna pantalla lo alcanza.

**Forma.** Validación en crear y en editar, en el catálogo.

**Gate humano (W8).** Antes de que esto entre hay que contar los ingresos
recurrentes manuales que ya existan en la base de producción. Producción es el
Postgres local (ADR-0030) y el manifest fuerza autonomía `low` en esas rutas —
ese paso lo corre el humano. Ver `runbook.md`.

### Reglas de rechazo del salto (AC-20, AC-21)

Ambas viven en `occurrences.skip`, que es donde ya está el conocimiento de la
fecha:

- **AC-20** — si la ocurrencia está `posted`, se rechaza con un mensaje que dice
  que esa fecha ya se cobró. El saldo queda en 474.100 y la fecha sigue cobrada.
- **AC-21** — si la fecha no está en las fechas de vencimiento de la obligación,
  se rechaza. Usa `recurrence.is_due_on`, pura y testeable sin base de datos.

Saltar una fecha futura y real sigue funcionando como hoy (AC-15, verde).

### ADRs que salen de este plan

| ADR | Qué fija | Deuda que cierra |
|---|---|---|
| **0035** | Materialización interactiva: las fechas pasadas se ofrecen; estado `offered` | W2, W5 · supersede la cláusula de backfill silencioso de ADR-020 (producto) |
| **0036** | Commit por cobro + reporte de fallos por ítem | W2 · supersede el rollback de lote de ADR-020 (producto) |
| **0037** | Ciclo de vida: "terminada" derivada al leer, la pausa se cierra al reanudar | W3, W4 · ADR-0005 queda intacto; matiza la consecuencia de auto-sanado de ADR-0013 |
| **0038** | Procedencia del motor en el movimiento + el borrado cierra la fecha | seam con las features 002 y 006 |

Las cuatro quedan escritas en este checkpoint, en estado `proposed`, y pasan a
`accepted` en F4. La entrada de producto correspondiente
(`product-decisions.md` § ADR-026) ya está escrita y marca ADR-020 como
parcialmente superseded.

## Charter Check

| Regla del charter | Estado | Nota |
|---|---|---|
| §1 DAE + ATDD: la feature avanza por el pipeline de aceptación | ✅ | spec de 70 escenarios / 77 ejecuciones aprobado 2026-08-02; baseline 53 verde / 24 rojo deliberado |
| §1 Decisiones arquitectónicas como ADR | ✅ | 4 ADRs (A–D) escritas en este checkpoint; ninguna decisión de D1–D7 queda sin registro |
| §1 ADRs respetadas, nunca contradichas en silencio | ✅ | ADR-020 (producto) se supersede explícitamente en A y B; ADR-0005 no se toca porque D2 deriva en vez de escribir el flag; ADR-0013 se matiza en C |
| §1 Decisiones de producto separadas de las ADR técnicas | ⚠️ | Ver Amendments — 0035 y 0036 supersede parcialmente `product-decisions.md` § ADR-020; la enmienda (§ ADR-026) ya está escrita |
| §2 Postura local-only (ADR-0026/0030) | ✅ | Sin infraestructura nueva; la migración corre contra el Postgres local, nunca contra Render |
| §2 Layering api → services → domain → db | ✅ | `domain/recurrence.py` puro y sin sesión; lógica en `services/`; routers y tools delgados |
| §2 Scheduler en la lifespan de FastAPI | ✅ | `run_daily` conserva su firma; solo enriquece el dict de reporte |
| §2 Paridad MCP + tiers (ADR-0020) | ✅ | ofrecer = read; aceptar/rechazar = write-destructive, como `skip_recurring` |
| §3 Código/identificadores en inglés (ADR-0001); UI copy español | ✅ | `occurrences.py`, `offered`; copy "Fechas pendientes", "Terminada" en español |
| §3 Python ≥3.12, uv, pytest host-side con SQLite en memoria | ✅ | D4 elige commit por cobro precisamente para no depender del comportamiento de SAVEPOINT de pysqlite |
| §3 pnpm only / Biome / vitest colocado | ✅ | Sin dependencias nuevas en frontend |
| §3 Soft-delete uniforme (ADR-0005) | ✅ | `active` conserva su significado; "terminada" es derivada |
| §4 Alcance: finanzas personales, un usuario, local | ✅ | Sin superficie nueva fuera de eso; "Por cobrar" sigue parqueada |
| §6 Strict gate: tests backend Y frontend de la superficie tocada | ✅ | Test strategy abajo; la superficie frontend son 2 pantallas |
| §7 Autonomía medium + gates de datos | ✅ | La migración y el conteo en producción bajan a `low` por los overrides del manifest; el merge a `main` sigue siendo humano |
| Auto: stance de autonomía | ✅ | medium por defecto; `migrations/**` fuerza `low` — F0 y F2 tienen gate humano explícito |
| Auto: independencia de verificación (Principio 7) | ✅ | CP7 verify con `agent_id` distinto al de CP5 implement |
| Auto: política de mutación | ✅ | `opt_in` en el manifest; esta feature **opta por sí** sobre `domain/recurrence.py` y `services/occurrences.py` — ver Test strategy |
| Auto: presupuestos de performance | ✅ | Sección abajo (medium: informativos, no gate) |

### Amendments

**A1 — `docs/decisions/product-decisions.md` § ADR-020 se supersede
parcialmente.** Es la única desviación ⚠️, y su enmienda está escrita, no
prometida:

- `docs/adr/0035` y `docs/adr/0036` nombran en su campo `Supersedes` las dos
  cláusulas afectadas — la creación silenciosa de fechas pasadas (0035) y el
  rollback de lote de la materialización diaria (0036).
- `docs/decisions/product-decisions.md` § **ADR-026** es la enmienda del lado de
  producto: registra las dos reglas en lenguaje de comportamiento y marca
  ADR-020 como parcialmente superseded, dejando en pie su núcleo (motor every-N,
  clave `(recurring_id, due_date)`, materialización por vencimiento).

Ese archivo llevaba sin entradas desde 2026-07-03. La deriva no la creó esta
feature; esta feature no la aumenta.

Ninguna otra fila queda en ⚠️.

### Deuda arrastrada, fuera del alcance de este plan

- **W1 / I3 (`consistency-check`):** `feature.md` cita ADR-0013, superseded por
  ADR-0026, y su puntero a `ADR-020` es ambiguo. Corrección de una línea con
  `feature-edit`; no bloquea la implementación.

## Phasing

Cinco fases. El orden lo manda el riesgo: primero que un fallo no cueste el día,
después las reglas de ciclo de vida, al final lo interactivo, que es lo que más
superficie nueva trae.

- **F0 — Cimientos (esquema, procedencia y corte de módulos).** Migración `0008`
  con los 2 valores de enum en `autocommit_block`; extracción de
  `domain/recurrence.py`; creación de `services/occurrences.py` moviendo la
  materialización actual **sin cambiar su comportamiento**, incluidos los 2
  helpers de `planned.py`; valor de motor en el movimiento + insignia en la
  lista de movimientos (ADR-0038). **Cierra AC-25 (2 rojos).**
  Gate humano: la migración toca `migrations/**` → autonomía `low`.

- **F1 — El run no se cae (AC-22, AC-24).** `MaterializationReport` +
  `RunFailure` en `domain/dtos.py`; commit por cobro; detección de cuenta
  archivada; `run_daily` propaga los fallos (ADR-0036).
  **Cierra 4 rojos.** Es la fase que más protege dinero real y no depende de F0
  salvo por vivir ya en `occurrences.py`.

- **F2 — Reglas de ciclo de vida (AC-13, AC-17, AC-6).** "Terminada" derivada +
  ajuste de los 2 bindings de aceptación; `offer_paused_stretch` en el reanudar;
  ingresos forzados a automático (ADR-0037). **Cierra 4 rojos.**
  Gate humano: conteo de ingresos recurrentes manuales en producción antes de
  activar la validación (runbook `count-manual-recurring-incomes`).

- **F3 — Decisiones sobre fechas (AC-12, AC-20, AC-21, AC-28, AC-26).** Estado
  `offered` y el trío ofrecer/aceptar/rechazar; `declared_on` en la declaración;
  rechazo del salto sobre fecha cobrada y sobre fecha inexistente;
  `POST_DELETE_HOOKS` y el cierre de la fecha al borrar; 3 endpoints REST + 3
  herramientas MCP con sus tiers; diálogo de fechas ofrecidas como componente
  propio (no dentro de las 681 líneas de la página) + marca "Terminada"
  (ADR-0035). **Cierra 14 rojos** — la fase más grande, y la última porque
  es la que más superficie nueva trae.

- **F4 — Cierre.** Run de aceptación 77/77 verde en 007 y 201/201 global (002,
  005 y 006 como candado de regresión); `spec-check`; suites backend y frontend
  completas; mutación sobre los dos módulos elegidos; `arch-check` contra la
  invariante de escritura de ocurrencias; las ADRs 0035-0038 pasan de `proposed`
  a `accepted` con sus filas del índice.

Las tareas concretas no se enumeran aquí: salen de las specs, una spec = un
ciclo TDD, dirigidas por `atdd:atdd-team`.

## Performance budgets

Autonomía `medium` → informativos, no son un gate de merge. Escala real: un
usuario, decenas de obligaciones, Postgres local.

| Medida | Presupuesto | Por qué |
|---|---|---|
| Run diario, estado estable (≤ 50 obligaciones, 0–5 vencimientos) | < 500 ms | Corre en la lifespan de FastAPI; no debe notarse en el arranque |
| Run de puesta al día (1 obligación diaria, 365 fechas atrasadas) | < 5 s | Caso extremo de máquina apagada un año; 365 commits |
| Commits por run | 1 por cobro + 1 por cierre de pausa | Consecuencia aceptada de D4; a esta escala son decenas, no miles |
| Consulta de fechas ofrecidas de una obligación | < 50 ms | Va detrás de un diálogo; el usuario la espera |
| Suite de aceptación completa | sin regresión > 20 % sobre la marca actual | El commit por cobro multiplica los commits en los tests |

Si el run de puesta al día se acerca al presupuesto, la salida es agrupar por
obligación (un commit por obligación en vez de por cobro) sin cambiar la
semántica de AC-24, que exige aislamiento por obligación, no por fecha.

## Collaboration schedule

| Momento | Quién | Qué |
|---|---|---|
| Apertura de F0 | humano | Revisa y aplica la migración `0008` (autonomía `low` en `migrations/**`) |
| Apertura de F2 | humano | Corre el conteo de ingresos recurrentes manuales en producción y decide qué hacer con los que existan |
| Cierre de cada fase | agente | Run de aceptación de la feature + reporte de rojos que cierra |
| Cierre de F3 | humano | Revisa el diálogo de fechas ofrecidas en la app (es la única superficie nueva de usuario) |
| CP5 → CP7 | agente distinto | Verificación independiente (Principio 7): quien verifica no es quien implementó |
| Merge a `main` | humano | Gate del charter §7, sin excepción |

Fuera de esos puntos el agente avanza solo: implementa, escribe y corre tests,
refactoriza y actualiza artefactos DAE en la rama `recurring-engine`.

## Execution modes

| Fase | Modo | Autonomía |
|---|---|---|
| F0 — esquema y corte de módulos | agente, con gate humano en la migración | `low` en `migrations/**`, `medium` en el resto |
| F1 — el run no se cae | agente | `medium` |
| F2 — ciclo de vida | agente, con gate humano en el dato de producción | `low` para el conteo, `medium` en el código |
| F3 — decisiones sobre fechas | agente, revisión humana de la UI al cerrar | `medium` |
| F4 — cierre | agente para las corridas; humano para el merge | `medium` |

Umbral de bucle atascado: 3 intentos (`stuck_loop_threshold` del manifest). Al
tercero el agente para y reporta en vez de seguir intentando.

Despacho remoto: no disponible (`remote.ready: false`) — todo corre local.

## Test strategy

`feature.md` no declara `validation_method`, así que aplica el stack DAE
estándar del charter: aceptación + unit + mutación. Se declara explícitamente
porque el charter §7 fija que el techo de validación es la superficie local de
tests — no hay staging, ni monitoreo, ni feature flags.

**1 — Aceptación (el contrato).** `./run-acceptance-tests.sh
features/007-recurring-engine`. Meta por fase: F0 → 55 verde, F1 → 59, F2 → 63,
F3 → 77. En F4 la suite completa: 201/201, con 002, 005 y 006 como candado de
regresión. Los tests generados no se editan nunca; solo se regeneran.

Dos bindings de handler se ajustan en F2 (`"X" is switched off`, `"X" is live`)
y cinco en F3 (los tres de AC-12, el de fallos del run, el de procedencia del
movimiento) — todos ya escritos en `acceptance/handlers/recurring_engine.py`
nombrando la intención; F3 los conecta a las APIs reales. Ningún cambio de
handler puede tocar `spec.md`.

**2 — Unit backend (pytest, host-side, SQLite en memoria).**

- `domain/recurrence.py` — sin base de datos: cadencia, ajuste de fin de mes,
  `is_due_on` sobre fecha que no vence, `has_ended` en los bordes (fin = hoy,
  fin = ayer, sin fin). El archivo `tests/domain/test_recurrence.py` ya existe y
  se amplía.
- `services/occurrences.py` — aislamiento por cobro con una obligación rota
  entre dos sanas; el fallo nombra la obligación; la fecha fallida sigue
  disponible al run siguiente; ofrecer/aceptar/rechazar; rechazo del salto sobre
  fecha cobrada y sobre fecha inexistente; cierre de la pausa; el hook de
  borrado.
- `services/recurring.py` — ingreso manual rechazado al crear y al editar;
  "terminada" fuera de la lista viva y dentro de la de apagadas.
- `services/planned.py` — no cambia de comportamiento; sus tests actuales son el
  candado del movimiento de los 2 helpers.
- `jobs/daily.py` — el reporte incluye los fallos y el conteo de creadas.

**3 — Unit frontend (vitest colocado).** Insignia de motor en la lista de
movimientos; diálogo de fechas ofrecidas (aceptar parcial, rechazar todo, lista
vacía); marca "Terminada" en la lista de obligaciones.

**4 — Mutación (CP8).** El manifest la deja `opt_in` con `cadence: on_demand` y
`scope: changed_files`. **Esta feature opta por sí**, limitada a
`domain/recurrence.py` y `services/occurrences.py`: son el código que mueve
saldos sin que nadie mire, y son puros o casi puros, que es donde la mutación
paga. El resto del diff no entra.

**5 — Fitness arquitectónico (CP8).** `arch-check` verifica la invariante:
ningún módulo fuera de `services/occurrences.py` escribe `RecurringOccurrence`,
y `domain/recurrence.py` no importa nada de `services/` ni de `sqlmodel.Session`.

**Qué NO se testea aquí.** El confirmar/omitir desde la cola de pendientes es de
la feature 006; la conversión a COP en lectura es de la 005; el fetch de FX y el
cierre de mes comparten el job diario pero son sus propias features.

---
slug: sinking-funds
checkpoint: 4
plan_status: approved
created: 2026-08-04
---

# Plan — 003 sinking-funds

Arquitectura confirmada por Angelo el 2026-08-04. Cierra los **92 escenarios
rojos** de aceptación repartidos en 30 ACs. **Ninguno pasa hoy** — a diferencia
de la 008, donde 17 de 46 ya estaban verdes. No hay fondo, el número que se
reemplaza calcula otra fórmula, y las metas siguen siendo su propio concepto.

Huella de datos: **+1 tabla (`fund`), −3 tablas (`goal`, `goal_contribution`,
`budget`), −1 columna (`transaction.goal_id`), 1 migración destructiva sobre
datos reales.**

Es la suite más grande del proyecto (007 tuvo 70, 008 tuvo 46) y `feature.md`
ya avisaba que no cabe en una corrida. La partición está abajo.

Tres decisiones de producto aceptadas cambian de estado y una regla del charter
se enmienda. Todo está escrito, no prometido: ver Charter Check.

## Architecture

Registrada en **ADR-0043** (la forma del dato) y **ADR-0044** (el camino de
lectura). Producto: **ADR-037** en `docs/decisions/product-decisions.md`.

### D1 — Un fondo es una fila; lo que *tiene* no se guarda, se deriva

Tabla `fund`, una por categoría de gasto (única), con: la regla
(`fixed` | `average` | `from-recurring` | `target-by-date`), sus parámetros, el
mes de inicio, si acumula, y un ancla. **Sin saldo y sin cuenta.**

```
tiene(M)      = max( apertura(M) − gastado(M), 0 )
apertura(M+1) = max( apertura(M) + pide(M) − gastado(M), 0 )   # acumula
apertura(M+1) = 0                                               # reinicia
```

Esto sale de los escenarios, no de una preferencia. **AC-11** pone el fondo en
$447.300, registra el gasto de $447.300 y exige que tenga **$0** — no los
$74.550 que pide ese mes. O sea: *lo que pide este mes todavía no está adentro*.
**AC-13** exige que un fondo sobregirado caiga a $0 y nunca a negativo, que es
la ADR-005 de producto sin tocarla.

`gastado(M)` es el gasto posteado de la categoría en el mes, que
`MonthAggregate._spent_by_cat_month` **ya tiene cargado para toda la historia**.

**El ancla** es el único par guardado: *"el 2027-01 este fondo tenía
$149.100"*. Se escribe al crear (AC-19, el saldo de apertura que el dueño
teclea) y cuando el dueño lo corrige. Es una afirmación del dueño, no una foto
calculada — por eso no choca con AC-16. Nada en la app la escribe sola y nada la
lee de una cuenta: AC-19 lo prueba con $9.000.000 en una cuenta de ahorros al
lado que el fondo ignora antes y después.

### D2 — El sobre no sobrevive: muere *dentro* del fondo

Un fondo `fixed` que acumula **es** un sobre. Dejar los dos vivos deja dos
formas de bajar el mismo titular — que es la forma exacta de la **C14**:
`set_budget` acepta un sobre sobre una categoría de ingreso y deprime
safe-to-spend para siempre sin manera de limpiarlo. **AC-22 es ese mismo rechazo
en la superficie que lo reemplaza.**

Se van con `Goal`: `Budget`, `set_budget`, la herramienta MCP `assign_budget` y
la pantalla de presupuestos.

**Producción tiene cero filas de `budget`.** Nunca se creó un sobre en la
historia de la app. Migrar no cuesta nada porque no hay nada que migrar.

### D3 — Una sola fórmula para las cuatro reglas

```
pide(M) = (lo que falta) ÷ (meses desde M hasta el mes anterior al cobro)
```

con piso de un mes.

| regla | qué falta | ¿fecha de cobro? |
|---|---|---|
| `fixed` | el monto tecleado | no → divide por 1 |
| `average` | gasto de la ventana ÷ meses **completos con datos** | no → divide por 1 |
| `from-recurring` | por obligación: su monto menos lo acumulado | sí, su vencimiento |
| `target-by-date` | la meta menos lo que tiene | sí, la fecha |

El SOAT de $447.300 que cobra 2027-05-02, con inicio 2026-11: seis meses
(nov→abr) → **$74.550**. En enero con $297.300 adentro: $150.000 ÷ 4 →
**$37.500**. Vaciado, sube sola (AC-7).

**Dos cosas salen como consecuencia, no como caso aparte:**

- **AC-6 — el mes del cobro no aporta.** Para ese mes el fondo ya está completo,
  entonces *lo que falta* es $0 y pide $0. No hay que programarlo.
- **Una obligación que cobra este mes pide su monto completo.** Cero meses
  restantes → el piso lo hace uno → el fondo necesita la plata ahora. Internet
  con tres obligaciones mensuales pide $161.400 (AC-4); saltar Plan de datos
  Mamá lo baja a $123.900 (AC-17). Misma fórmula.

**El promedio (AC-3)** separa dos razones por las que un mes puede estar vacío:
un mes del que la app **no tiene datos** se excluye de la división; un mes que
existió y no gastó nada es un cero real y cuenta. Con 2 meses de historia y
ventana de 12, Servicios divide $300.000 entre **2** → $150.000, y lo dice
(`averaged_over`). El mes en curso nunca se promedia a sí mismo.

### D4 — El cálculo vive en el agregado que ya existe

`services/funds.py` para escrituras y para la fachada de lectura; el cálculo
entra en `MonthAggregate` (ADR-0028). La aritmética pura —el fold, el promedio,
la normalización de intervalos— baja a `domain/rules.py`, sin sesión y sin
modelo, igual que dejó la 008.

Costo real sobre el camino de lectura:

| | |
|---|---|
| se va | `SELECT * FROM budget` (la tabla se elimina) |
| entra | `SELECT * FROM fund` |
| entra | ocurrencias del mes — AC-17 (cargo saltado) y AC-14c (ingreso ya posteado) |
| entra | `MIN(date)` sobre movimientos posteados — AC-3 |
| **neto** | **+2 sentencias sobre las ~8 de hoy** |

El fold son 7 fondos × 12 meses = 84 pasos en memoria. Ninguna consulta nueva de
historia: el promedio y el fold montan sobre datos que la ADR-0028 ya dejó
disponibles.

### D5 — El ingreso del mes: la categoría deja de adivinar en cuanto entra plata

```
ingreso(M) = Σ por categoría de ingreso:
    lo que entró de verdad este mes, si entró algo
    si no, lo que las obligaciones de esa categoría prometen
```

Salario espera $5.000.000 y llega $4.200.000 → cuenta **$4.200.000**, no
$9.200.000 (AC-14c). El salario que el motor ya posteó cuenta una vez.
Rendimientos sin obligación detrás cuenta desde que se registra. El bono
trimestral aporta **$0** a agosto y **todo** a septiembre (AC-14).

**Esto es la cláusula de reconciliación de la ADR-004 de producto, aceptada hace
siete meses y nunca construida** — la C17. Hoy `_income_forecast` no lee un solo
movimiento posteado: reporta $18.128.501 planos todos los meses mientras el
registro dice $0 en abril y $45.176.653 en julio, describiendo los mismos dos
salarios sin compararse nunca.

**Frontera declarada**, al estilo del D4 de la 008: el corte es **por
categoría**, no por obligación. Dos obligaciones en una misma categoría de
ingreso donde sólo una posteó: la otra deja de contarse. La alternativa pide una
regla de emparejamiento entre ingresos posteados y obligaciones, y producción no
ofrece evidencia para ella — la historia es una importación de Lunch Money y la
app lleva un mes de uso real. Está escrito en la ADR-0044 para que nadie lo
"arregle" sin saber que fue elegido.

### D6 — Los tres términos, y las dos cifras que nunca se mezclan

```
disponible(M) = ingreso(M) − Σ lo que piden los fondos − lo que ningún fondo cubre
```

`lo que ningún fondo cubre` es un solo término a propósito: gasto posteado en
categorías sin fondo, obligaciones en categorías sin fondo, **y el exceso por
encima de lo que el fondo tiene** (AC-13 — sólo el exceso sale del disponible,
nunca el monto entero). Tiene que ser uno solo porque AC-10 exige que el
desglose **cuadre exactamente**: `ingreso − Σ piden − sin cubrir = disponible`.

Aparte, y nunca mezcladas:

```
ganancia(M) = Σ ingresos recurrentes, cada uno ÷ los meses de su ciclo
costo(M)    = Σ lo que piden los fondos + obligaciones sin fondo, normalizadas
margen(M)   = ganancia − costo
```

Un bono trimestral de $3.000.000 aporta $1.000.000 a la ganancia **cada mes** de
su ciclo, y $0 al disponible hasta el mes en que vence. AC-14b afirma las dos en
el mismo escenario y espera que difieran: ganancia $6.000.000 contra disponible
$5.000.000. La brecha lleva información, no ruido.

### D7 — El TRM se pide al entrar, siempre — **revertida por el dueño 2026-08-04**

`available`, `rates`, `fund_status` y `list_funds` llaman `get_trm` al entrar y
fallan fuerte con `MissingRate` si no hay tasa, igual que `safe_to_spend`,
`list_budgets` y `budget_status` antes que ellas. **ADR-0031 queda intacta: una
sola regla, sin excepciones.**

El dueño lo decidió así: *"La tasa se aplica al entrar en la app. Siempre debe
estar (mientras creamos un feature que obtenga la TRM por debajo día a día)."*
La fricción se acepta porque tiene fecha de vencimiento — el job diario de TRM
ya está en el roadmap. Registrada como decisión de producto **ADR-038**.

**Costo aceptado:** un mes registrado enteramente en pesos tampoco se puede leer
hasta que haya tasa.

Los 92 escenarios pasan igual, sin tocar ni un `spec.md`: el `World` de
aceptación **siembra** una tasa como estado de fondo de una app corriendo
(`SEEDED_TRM`, un valor que no aparece en ningún spec), y `Given no TRM has been
set` ahora la borra en vez de suponer su ausencia. Los nueve escenarios de 002,
005 y 006 cuyo sujeto *es* la tasa faltante la declaran explícitamente; ninguno
dependía del silencio.

Eso además disuelve el choque que la regla perezosa había creado: AC-9 de la 005
afirma que un reporte sin tasa se niega, y AC-12 de la 003 lee el reporte de un
mes en puro COP — dos specs, un solo registro global de steps. Con la regla de
entrada y el `World` sembrado, las dos se cumplen.

> **Superseded — razonamiento original (2026-08-04, revertido el mismo día).**
> Los reemplazos pedían la tasa **sólo al toparse con un monto que no es COP**:
> un mes en puro COP no la necesitaba; uno con una obligación de US$30 seguía
> fallando fuerte. La medición que lo motivaba: **85 de los 92 escenarios
> aprobados no fijan TRM** — sólo los tres de AC-18, el AC sobre moneda —, de
> donde se concluyó que bajo la regla de hoy el contrato aprobado no podía
> pasar. El error fue de lectura: la medición describía los specs, no la app.
> Los 85 escenarios callaban sobre la tasa, no dependían de su ausencia. La
> enmienda queda **retirada** en ADR-0044.

### D8 — Las metas mueren en una migración; el fondo se borra duro

Revisión `0012`: `DROP` de `goal`, `goal_contribution`, `budget` y de
`transaction.goal_id`; borrado de las tres transferencias propuestas que nunca
se confirmaron. Se van `services/goals.py`, su router, `goals_reads`, el hook
`propose_goal_contributions` y la pantalla.

**Toca datos reales** → `just backup` fresco y gate humano (charter §7,
ADR-0030). AC-27 exige además que todo lo demás sobreviva intacto: cada gasto e
ingreso conserva su categoría, cada transferencia sigue sin ninguna.

Un fondo se **borra**, no se archiva. La ADR-0005 (soft-delete uniforme) sigue
en pie para los maestros; un fondo es una regla pegada a una categoría, no un
maestro: no tiene historia propia y su saldo es derivado. Frontera declarada en
ADR-0043.

### D9 — El asistente: se ajusta el binding, no la convención

Los handlers de CP3 llaman
`registry.funds.create_fund(session, category="X", rule="fixed", …)` con
kwargs planos. La casa usa `(session, inp: PydanticModel)` y `_as_text` como
envoltorio (`mcp/tools/planning.py`).

**Gana la casa.** El handler se ajusta en la fase que construye las puertas. El
`spec.md` **no se toca**; sólo el binding, que es fuente editable y cuyo propio
docstring dice *"Checkpoint 4 owns its shape"*. Los mensajes de rojo que hacen
legible la salida se conservan.

**Corrección, 2026-08-04 (F3).** Este párrafo decía además que la casa
identifica *"con ids"*, y eso era una generalización mía a partir de
`planning.py` solo. La casa tiene **dos** convenciones: las entidades con
nombre propio se resuelven por nombre —`_resolve_account_by_name` y
`_resolve_category_by_name` en `mcp/tools/core.py:123,133`, y `name: str` en
todo `mcp/tools/masters.py`— y las filas sin nombre propio van por id. Un fondo
no tiene nombre propio pero su categoría sí, y el asistente habla en nombres de
categoría, no en números de fila. Las herramientas de fondos toman el nombre de
la categoría y le pasan el id al servicio, que es exactamente la forma que
tenía `assign_budget`, la herramienta que reemplazan. La convención no cambia:
cambia mi descripción de ella.

Paridad REST↔MCP es regla del charter §2 (ADR-0006/0009) y **AC-28 sale casi
gratis**: las reglas viven en `services/`, así que las herramientas heredan cada
rechazo sin código propio — el mismo argumento que hizo que AC-14 de la 008 no
necesitara nada.

### Radio de impacto, medido

- **`goal` se lee en 24 archivos de `backend/src` y 20 de test.** Los de src son
  mayormente re-exports e imports: el núcleo son `services/goals.py` (351),
  `api/routers/goals.py`, `mcp/tools/goals_reads.py`, `mcp/tools/planning.py`,
  `services/reports.py` (`_goal_lines`), `domain/rules.py` (`goal_progress_calc`),
  `domain/dtos.py` (`GoalProgress`), `domain/report_types.py`,
  `domain/report_markdown.py`, `services/bootstrap.py` (`register_goal_hooks`).
- **`budget` se lee en** `services/budgets.py` (223), `services/reports.py`
  (`_envelope_lines`), `services/month_aggregate.py`, `domain/rules.py`,
  `domain/dtos.py`, `mcp/tools/budgets_reads.py`, `mcp/tools/planning.py`,
  `api/routers/budgets.py`.
- **Frontend:** `budgets/page.tsx` (287) se convierte en la pantalla de fondos;
  `goals/page.tsx` (587) se borra; `lib/api/goals.ts` se borra,
  `lib/api/budgets.ts` se reescribe; la tarjeta del home en `page.tsx` (230)
  pasa a disponible + tasas; `app-shell.tsx` pierde una entrada de nav;
  `reports/page.tsx` y `to-pay-widget.tsx` pierden las líneas de metas.
- **`services/goals.py` crea patas de transferencia sin categoría** (líneas 177,
  189, 280) — se van con el módulo, y el CHECK de la 008 las respaldaba mientras
  existieron.
- **`domain/recurrence.py`** menciona metas sólo en un comentario de contexto:
  sin cambio funcional.

## Charter Check

| Regla del charter | Estado | Nota |
|---|---|---|
| §1 DAE + ATDD: la feature avanza por el pipeline de aceptación | ✅ | spec de 92 escenarios aprobado 2026-08-03; baseline 0 verde / 92 rojo deliberado, con 246 verdes de otras features como candado |
| §1 Decisiones arquitectónicas como ADR | ✅ | ADR-0043 (forma del dato) y ADR-0044 (camino de lectura) escritas en este checkpoint, en `proposed` |
| §1 ADRs respetadas, nunca contradichas en silencio | ⚠️ | Ver Amendments — ADR-0006 queda superseded entera y ADR-0005 en su cláusula de metas. Las dos están escritas. ADR-0028 se **extiende** (+2 sentencias), no se contradice. **ADR-0031 queda intacta** — la enmienda a su cláusula de fallo fuerte fue retirada por el dueño (D7) |
| §1 Decisiones de producto separadas de las ADR técnicas | ⚠️ | Ver Amendments — ADR-003 y ADR-006 superseded, ADR-002 y ADR-016 enmendadas, ADR-004 construida por primera vez. `product-decisions.md` § ADR-037 ya está escrita |
| §2 Postura local-only (ADR-0026/0030) | ✅ | Sin infraestructura nueva; la migración corre contra el Postgres local, nunca contra Render |
| §2 Layering api → services → domain → db | ✅ | `domain/rules.py` puro y sin sesión; `services/funds.py` y `month_aggregate` en servicios; routers y tools delgados |
| §2 Paridad REST ↔ MCP (ADR-0006/0009) + tiers (ADR-0020) | ✅ | Las siete herramientas de metas y `assign_budget` se borran; entran las de fondos en las dos superficies. Tiers: lecturas `read`, `create_fund`/`set_fund` `write-safe`, `delete_fund` `write-destructive` |
| §3 Código/identificadores en inglés (ADR-0001); UI copy español | ✅ | `fund`, `asks`, `holds`, `earning_rate`; copy en español. Los rechazos en español dependen de la C9 — ver Deuda arrastrada |
| §3 Python ≥3.12, uv, pytest host-side con SQLite en memoria | ✅ | La revisión `0012` usa `batch_alter_table` por lo mismo que la `0010`: el `DROP COLUMN` de `transaction.goal_id` reconstruye la tabla en SQLite |
| §3 pnpm only / Biome / vitest colocado | ✅ | Sin dependencias nuevas en frontend |
| §3 Soft-delete uniforme (ADR-0005) | ⚠️ | Ver Amendments — un fondo se borra duro. Frontera declarada en ADR-0043; maestros sin cambio |
| §4 Alcance: finanzas personales, un usuario, local | ⚠️ | Ver Amendments — §4 **nombra** "sobres + safe-to-spend (ADR-002/003)" como el diferenciador, y esta feature lo reemplaza. La enmienda al charter ya está escrita y firmada |
| §6 Strict gate: tests backend Y frontend de la superficie tocada | ✅ | Test strategy abajo; la superficie frontend son 2 pantallas, 1 tarjeta y el nav |
| §7 Autonomía medium + gates de datos | ✅ | La migración baja a `low` por el override del manifest; ADR-0030 exige backup fresco; el merge a `main` sigue siendo humano |
| Auto: stance de autonomía | ✅ | medium por defecto; `migrations/**` fuerza `low` — F2 tiene gate humano explícito con runbook |
| Auto: independencia de verificación (Principio 7) | ✅ | CP7 verify con `agent_id` distinto al de CP5 implement |
| Auto: política de mutación | ✅ | `opt_in` en el manifest; esta feature **opta por sí** sobre `domain/rules.py` y `services/funds.py` — ver Test strategy |
| Auto: presupuestos de performance | ✅ | Sección abajo (medium: informativos, no gate) |

### Amendments

**Cuatro** desviaciones ⚠️, no cinco: A5 fue retirada el 2026-08-04 y ADR-0031
queda sin tocar. El plan es **estrictamente más conforme al charter** que cuando
se firmó — cuatro enmiendas en vez de cinco, y una ADR técnica menos alterada.
Las cuatro que quedan tienen su enmienda **escrita en este checkpoint**, no
prometida.

**A1 — Charter §4: el diferenciador cambia de nombre.** `CHARTER.md` §4 decía
que el diferenciador es *"hybrid budget — per-category envelopes with rollover +
global safe-to-spend (product ADR-002/003)"*. Esta feature elimina las dos
mitades. §4 ahora nombra **el fondo**: un noun que reemplaza sobres y metas,
donde la regla de financiación *es* el número mensual y no existe ritual
mensual. Registrado en la cabecera del charter como enmienda fechada y firmada,
igual que la de §2 del 2026-07-29.

**A2 — `product-decisions.md` § ADR-037** es la enmienda de producto, y cubre
cuatro decisiones aceptadas de una sola vez:

- **ADR-003 (safe-to-spend = plata sin asignar) → superseded.** "Plata sin
  asignar" sólo significa algo si existe el ritual de asignación, y el ritual no
  se ejecutó **ni una vez** en la historia de la app: cero filas de `budget`.
- **ADR-006 (metas flexibles) → superseded.** Las metas desaparecen como
  concepto. Una meta es un fondo con meta y fecha, y no nombra ninguna cuenta.
- **ADR-002 (sobres + rollover) → enmendada.** El sobre se vuelve fondo y el
  rollover pasa a ser por fondo. La postura híbrida sobrevive; los dos
  mecanismos se vuelven uno.
- **ADR-016 (sobres opcionales) → enmendada.** "Sobres opcionales" es "fondos
  opcionales"; `unbudgeted_spending` es *gasto en categorías que ningún fondo
  cubre*. El principio no cambia y es la razón de que el titular no tienda a
  cero.
- **ADR-004 → NO superseded**, y la enmienda lo dice explícitamente: su cláusula
  de pronóstico se parte en dos números y su cláusula de reconciliación se
  construye por primera vez.
- **ADR-005 sobrevive intacta** y AC-13 depende de ella directamente.
- **ADR-015** (cuenta origen global para aportes de metas) queda moot; el ajuste
  se queda porque las transferencias manuales lo siguen usando.

**A3 — ADR-0006 técnica queda superseded entera.** Era la ADR que estableció la
paridad REST↔MCP para la superficie de planeación. **La paridad en sí no se
toca** (charter §2, ADR-0009) y se vuelve a satisfacer con las herramientas de
fondos; lo que se va son las herramientas que ADR-0006 nombraba. Registrado en
`Supersedes:` de ADR-0043.

**A4 — ADR-0005 técnica, cláusula de metas.** Un fondo se borra duro. La ADR-0043
declara la frontera: un fondo es una regla pegada a una categoría, sin historia
propia y con saldo derivado. Cuentas, categorías, tags y recurrentes conservan
soft-delete sin cambio.

**A5 — retirada.** Enmendaba la cláusula de "las lecturas fallan fuerte" de
ADR-0031 para pedir el TRM al toparse con un monto extranjero en vez de al
entrar. El dueño revirtió la decisión el 2026-08-04: la tasa se pide al entrar,
siempre. **ADR-0031 no se toca.** Ver D7 y la sección retirada de ADR-0044.

Ninguna otra fila queda en ⚠️.

### Deuda arrastrada, fuera del alcance de este plan

- **C9 — los rechazos de dominio llegan al toast en inglés**, contra charter §3.
  Toca a esta feature porque agrega ocho rechazos nuevos, pero predata y es
  transversal. El `spec.md` afirma que un rechazo *dice lo correcto* haciendo
  match sobre la palabra que lleva el sentido, en español o en inglés — así que
  la redacción se puede arreglar sin tocar el spec. Tarea de consolidación.
- **C12 — el motor de recurrentes acuña cargos bajo categorías archivadas.**
  Independiente; AC-21 no lo cubre porque AC-21 rechaza *archivar* la categoría,
  no el cargo posterior.
- **C16 — las herramientas MCP de categorías no llevan dirección.** Deuda de la
  008.
- **Las seis fugas de implementación** en las specs de 002, 005, 006 y 007,
  listadas en el handoff de CP3 de la 008. Predatan.

## Phasing

Cinco fases. El orden lo manda una dependencia dura y una elección:

**La dependencia:** el fondo tiene que pedir antes de que el número pueda
restarlo. F0 antes de F1, sin alternativa.

**La elección:** la migración destructiva va **antes** que las pantallas, no
después. Así las dos puertas se construyen **una sola vez** contra la superficie
final, en vez de nacer con presupuestos y metas todavía vivos al lado. El costo
es que entre F2 y F3 la app no tiene ni pantalla de presupuestos ni de fondos.
Es una rama, no `main`; es aceptable y es explícito.

- **F0 — El fondo existe y pide.** Tabla `fund`; `domain/rules.py` gana el fold,
  el promedio y la normalización de intervalos como funciones puras;
  `services/funds.py` gana `create_fund`, `preview_fund`, `list_funds`,
  `set_fund`, `delete_fund` y `fund_status`; `MonthAggregate` carga los fondos,
  las ocurrencias del mes y el primer movimiento de la app;
  `categories.archive_category` consulta fondos (AC-21).
  **Cierra ≈48 rojos → 48/92.**
  Quedan afuera de esta fase los escenarios que además afirman el disponible
  (AC-1 s3, AC-24 s2).

- **F1 — El número.** `funds.available` y `funds.rates` reemplazan
  `safe_to_spend`; el término de ingreso reconcilia por categoría (AC-14c, la
  C17); el desglose cuadra (AC-10); el TRM se pide al entrar (D7).
  `services/reports.py` cambia sus líneas de sobre por líneas de fondo.
  **Cierra ≈32 rojos → 80/92.**

- **F2 — Mueren las metas y los sobres.** Revisión `0012`: `DROP` de `goal`,
  `goal_contribution`, `budget` y de `transaction.goal_id`; borrado de las tres
  propuestas sin confirmar. Se borran `services/goals.py`, su router,
  `goals_reads`, las seis herramientas MCP de metas, `assign_budget`,
  `register_goal_hooks`, `goal_progress_calc`, `GoalProgress` y las líneas de
  meta del reporte.
  **Cierra 6 rojos → 86/92.**
  **Gate humano:** `migrations/**` baja la autonomía a `low` y ADR-0030 exige
  `just backup` fresco antes de tocar datos reales. Pasos en `runbook.md`.

- **F3 — Las dos puertas.** REST: `/funds` CRUD, `/funds/available`,
  `/funds/rates`; mueren `/goals` y `PUT /budgets`. MCP: `tools/funds.py` con la
  convención de la casa (Input model + `_as_text`), tiers según §2 del Charter
  Check, y el ajuste del binding del handler (D9). Frontend: `budgets/page.tsx`
  se convierte en la pantalla de fondos, `goals/page.tsx` se borra, la tarjeta
  del home pasa a disponible + desglose + tasas, y el nav pierde Metas.
  **Cierra 6 rojos → 92/92.**

- **F4 — Cierre.** Run de aceptación 92/92 en 003 y **338/338** global (002,
  005, 006, 007 y 008 como candado de regresión); `spec-check` con el agente
  `spec-guardian`, que en CP3 no corrió; suites backend y frontend completas;
  mutación sobre los dos módulos elegidos; ADR-0043 y ADR-0044 pasan de
  `proposed` a `accepted` con sus filas del índice, y ADR-0005/0006 reciben su
  `Superseded by:`.

Las tareas concretas no se enumeran aquí: salen de las specs, una spec = un
ciclo TDD, dirigidas por `atdd:atdd-team`.

**Sobre los conteos por fase:** son estimaciones derivadas de qué afirma cada
escenario, no una partición medida. La cifra que importa y que sí es exacta es
la de F4: 92/92 y 338/338. Si una fase cierra menos de lo estimado, es
información, no falla — se reporta el número real.

## Performance budgets

Autonomía `medium` → informativos, no son gate de merge. Escala real: un
usuario, 41 categorías, ~640 movimientos, 7 fondos derivables, Postgres local.

| Medida | Presupuesto | Por qué |
|---|---|---|
| Sentencias de `load_month_aggregate` | **+2** sobre las ~8 de hoy | −1 (`budget` se va), +3 (`fund`, ocurrencias del mes, `MIN(date)`). Fijado por `backend/tests/api/test_reports_query_count.py` |
| El fold de fondos | 0 consultas | Monta sobre `_spent_by_cat_month`, que ya carga toda la historia en una sentencia |
| `available()` para un mes | < 50 ms | 7 fondos × 12 meses = 84 pasos en memoria después de la carga |
| `rates()` para un mes | < 10 ms | Una pasada sobre los ~14 recurrentes activos, en memoria |
| Reconstrucción de tabla en SQLite (`batch_alter_table` por el `DROP COLUMN`) | — | Corre una vez por base de test: 92 escenarios de aceptación + ~96 archivos backend. Es el mismo riesgo que midió la 008 |
| Suite de aceptación completa | sin regresión > 20 % sobre la marca actual | Marca de hoy: 338 escenarios (92 rojos + 246 verdes) |

El fold crece con los años: es O(fondos × meses desde el inicio más viejo). A
siete fondos y doce meses no se nota; a cinco años sí. La salida, cuando llegue,
es acotar la ventana del fold con el ancla — que ya existe justamente para poder
empezar el fold en un mes arbitrario. Registrado como costo en ADR-0043, **no**
se implementa ahora.

## Collaboration schedule

| Momento | Quién | Qué |
|---|---|---|
| Cierre de F0 | agente | Reporta el conteo real de rojos que cerró contra los ≈48 estimados |
| Cierre de F1 | **humano** | Revisa el número contra producción: es la cifra que el dueño mira todos los días y la que cambia de fórmula |
| Apertura de F2 | **humano** | `just backup` fresco (ADR-0030) antes de que la revisión toque datos reales |
| Apertura de F2 | **humano** | Confirma a mano el conteo previo: 1 meta, 0 aportes, 3 propuestas sin confirmar, 0 sobres — ver `runbook.md` |
| Cierre de F3 | **humano** | Revisa la pantalla de fondos y la tarjeta del home en la app |
| Cierre de cada fase | agente | Run de aceptación de la feature + reporte de rojos que cierra |
| CP5 → CP7 | agente distinto | Verificación independiente (Principio 7): quien verifica no es quien implementó |
| Merge a `main` | **humano** | Gate del charter §7, sin excepción |

Fuera de esos puntos el agente avanza solo: implementa, escribe y corre tests,
refactoriza y actualiza artefactos DAE en la rama `sinking-funds`.

**Un punto extra respecto a la 008, y a propósito:** el cierre de F1 tiene gate
humano. La 008 sólo lo tenía en la migración. Acá el número que cambia de
fórmula es el que el dueño usa para decidir si puede gastar, y AC-14b es la
parte más nueva y menos interrogada del contrato — se diseñó en una sola pasada,
al final, y así quedó registrado en el handoff de CP2.

## Execution modes

| Fase | Modo | Autonomía |
|---|---|---|
| F0 — el fondo pide | agente | `medium` |
| F1 — el número | agente, revisión humana al cerrar | `medium` |
| F2 — mueren metas y sobres | agente, con gate humano en backup y conteo | `low` en `migrations/**`, `medium` en el resto |
| F3 — las dos puertas | agente, revisión humana de la UI al cerrar | `medium` |
| F4 — cierre | agente para las corridas; humano para el merge | `medium` |

Umbral de bucle atascado: 3 intentos (`stuck_loop_threshold` del manifest). Al
tercero el agente para y reporta en vez de seguir intentando.

Despacho remoto: no disponible (`remote.ready: false`) — todo corre local.

## Test strategy

`feature.md` no declara `validation_method`, así que aplica el stack DAE
estándar del charter: aceptación + unit + mutación. Se declara explícitamente
porque el charter §7 fija que el techo de validación es la superficie local de
tests — no hay staging, ni monitoreo, ni feature flags.

**1 — Aceptación (el contrato).**
`./run-acceptance-tests.sh features/003-sinking-funds`.
Meta por fase: F0 → ≈48/92, F1 → ≈80/92, F2 → 86/92, F3 → 92/92. En F4 la suite
completa: **338/338**, con 002, 005, 006, 007 y 008 como candado de regresión.
Los tests generados no se editan nunca; sólo se regeneran.

`acceptance/handlers/sinking_funds.py` **sí se ajusta**, en F3 y sólo en su
capa de asistente (D9). Sus 92 bindings ya nombran la superficie post-feature y
su docstring **es** el contrato de implementación de F0/F1.

**2 — Unit backend.** Tests propios nuevos: el fold en `domain/rules.py` (puro,
sin sesión) con sus tres casos de borde —acumula, reinicia, sobregira—; la
fórmula de "lo que falta ÷ meses que quedan" en las cuatro reglas; la
normalización de intervalos (mes, año, semana, día); la reconciliación de
ingreso por categoría; y las revisiones `0011` y `0012` en las dos direcciones.

Los ~20 archivos de test backend que hoy tocan metas se borran con el módulo, no
se enhebran. Los de `budgets` se reescriben contra fondos. Ese es el barrido
grande de esta feature, equivalente a los ~139 sitios de la 008.

**3 — Unit frontend (vitest, colocado).** `budgets/page.test.tsx` existe y se
reescribe como la pantalla de fondos: crear con cada regla, la advertencia de
AC-24 antes de crear, y el toggle acumula/reinicia apareciendo sólo en `fixed` y
`average`. Nuevo para la tarjeta del home: el desglose cuadra, y el disponible y
las tasas se muestran como cifras distintas y rotuladas — es la separación que
la feature entera existe para hacer, y en la pantalla es donde se puede
confundir.

**4 — Mutación (opt-in).** El manifest la deja `opt_in` / `changed_files` /
`on_demand`. Esta feature **opta por sí** sobre `domain/rules.py` y
`services/funds.py`, y sólo sobre esos dos: ahí vive toda la aritmética del
número, así que un mutante que sobreviva ahí es un agujero en la feature entera,
no un test flojo. Corre en F4.

**5 — `spec-guardian` en F4.** El chequeo de fuga de implementación de CP3 lo
hice yo, inline, porque la instrucción de esa sesión era no despachar agentes
sin pedido. Una pasada independiente sobre las 92 escenarios vale una corrida y
está agendada en F4.

**6 — Lo que no cubre ningún test.** La revisión `0012` sobre los datos reales
del dueño: 1 meta, 0 aportes, 3 propuestas, 0 sobres. Eso es el `runbook.md`,
con backup previo y conteo confirmado a mano.

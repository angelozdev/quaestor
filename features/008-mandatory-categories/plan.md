---
slug: mandatory-categories
checkpoint: 4
plan_status: approved
created: 2026-08-03
---

# Plan — 008 mandatory-categories

Arquitectura confirmada por Angelo el 2026-08-03. Cierra los **29 escenarios
rojos** de aceptación repartidos en trece ACs: AC-1 (1), AC-2 (1), AC-3 (1),
AC-4 (3), AC-5 (3), AC-6 (1), AC-7 (1), AC-10 (2), AC-11 (1), AC-12 (2),
AC-13 (2), AC-14 (3), AC-15 (3), AC-17 (3) y AC-18 (2). Los otros 17 escenarios
ya pasan contra el código actual — son el candado de regresión de esta feature,
no relleno: AC-6/8/9 pasan porque el motor de la 007 ya copia la categoría al
cargo y un cargo saltado la conserva; AC-16 fija comportamiento existente;
AC-19 pasa porque el backfill de producción ya ocurrió.

Huella de datos: **0 tablas nuevas, 0 columnas nuevas, 1 migración** (un CHECK
sobre `transaction`, un `NOT NULL` sobre `recurring_item.category_id`). Todo lo
demás es una regla que hoy está copiada cinco veces y pasa a estar una.

La regla revierte una decisión de producto aceptada — ADR-024 dejó la categoría
opcional a propósito. La enmienda está escrita, no prometida: ver Charter Check.

## Architecture

### D1 — Una sola función responde "¿qué categoría lleva este movimiento?"

Hoy el mismo bloque de seis líneas —*¿existe la categoría? ¿está archivada?*—
está copiado en **cinco** rutas de escritura: `transactions._record`,
`transactions.update_transaction`, `recurring.create_recurring`,
`recurring.update_recurring`, `planned.plan_payment`. La regla nueva le agrega
tres chequeos a cada una. Copiarla cinco veces es cómo una regla se vuelve
cinco reglas ligeramente distintas.

`services/categories.py` crece una función que las cinco llaman:

```python
def resolve_for_movement(session, tx_type, category_id=None, new_category=None) -> int | None
```

Devuelve el id que se guarda, o levanta el rechazo.

| Entrada | Resultado | AC |
|---|---|---|
| `tx_type` es `transfer` con cualquier categoría | rechazado; devuelve `None` | AC-3 |
| ni `category_id` ni `new_category` | rechazado: falta la categoría | AC-1, AC-2, AC-6, AC-7 |
| ambos | rechazado por ambiguo | — |
| `new_category` | se crea con `is_income = (tx_type == income)`; rechaza si un activo ya tiene ese nombre; si el que lo tiene está **archivado**, rechaza ofreciendo restaurarlo | AC-5, AC-12, AC-13 |
| `category_id` | existe, no archivada, y coincide con la dirección | AC-15, AC-16 |

**AC-11 sale como consecuencia**, no como caso aparte: si
`update_transaction` pasa por la misma función, quitarle la categoría a un
gasto es "ninguno de los dos", que la primera regla ya rechaza. Lo mismo aplica
a `update_recurring` — no está en ningún escenario, y lo trato igual (juicio
declarado, confirmado en CP4).

**AC-14 sale gratis.** App, API REST y asistente ya pasan todos por
`services/`. No hay una cuarta puerta que guardar. Los tres escenarios de
AC-14 llaman al cuerpo de la herramienta MCP por debajo del envoltorio
`_as_text` — el mismo camino, sin la capa de presentación — así que prueban
que el asistente **rechaza**, no que formatea un rechazo.

La dirección en sí es una función pura en `domain/rules.py`: sin sesión, sin
modelo, testeable sola, y es la forma que va a leer la feature 003.

Registrado en **ADR-0042**.

### D2 — La oferta filtrada es un argumento, no una función nueva

`list_categories(session, include_archived=False, is_income: bool | None = None)`
→ `GET /categories?is_income=true`.

El desplegable del formulario se re-consulta según Gasto/Ingreso. 🍽️
Restaurantes no aparece cuando registrás un salario — no es que se rechace
después, es que no está entre las opciones. AC-4, AC-10, AC-12.

### D3 — La barrera en los datos: revisión `0010`

Tres cosas en una sola revisión, en este orden:

**a) Guarda previa.** Antes de tocar el esquema, cuenta los gastos e ingresos
sin categoría y se niega nombrando cantidad y tipo: *"1 expense is still
uncategorised"*. En datos limpios cuenta cero y sigue. **AC-18** — el cambio
aterriza sobre datos limpios o no aterriza.

**b) CHECK sobre `transaction`**, declarado también en
`Transaction.__table_args__`:

```sql
CHECK (
  (type IN ('expense','income') AND category_id IS NOT NULL)
  OR (type = 'transfer' AND category_id IS NULL)
)
```

Discrimina por tipo. Un `NOT NULL` a secas cerraría el hueco y rompería las 39
transferencias en la misma sentencia. **AC-17.**

Declarado dos veces a propósito: Alembic es la fuente de verdad del esquema
(`db.py`), pero un constraint que solo conoce Alembic es invisible para quien
lee el modelo. Que las dos declaraciones digan lo mismo lo verifica
`backend/tests/db/test_model_schema_drift.py`, que refleja el CHECK desde una
base migrada y lo compara contra `Transaction.__table_args__` — la suite de
aceptación **no** lo hace: ejercita el esquema migrado a través de los modelos,
pero nunca compara las dos definiciones.

Se instala con `op.batch_alter_table`: en Postgres emite un `ALTER TABLE …
ADD CONSTRAINT` normal, en SQLite reconstruye la tabla. Sin eso la revisión
revienta en cada escenario de aceptación, que migra SQLite en memoria a head.

**c) `recurring_item.category_id` → `NOT NULL`.** Un recurrente nunca es
transferencia (`create_recurring` ya lo rechaza), así que no necesita
discriminación. Y como `occurrences._create_occurrence_tx` **copia**
`item.category_id` a cada cargo, una fuente NOT NULL no puede parir un cargo
nulo: AC-6/8/9 quedan estructurales en vez de depender de buena conducta.

`downgrade()` tira el constraint. A diferencia de la `0009`, revertir esta no
pierde nada.

Registrado en **ADR-0041**.

### D4 — El límite: presencia, no dirección

El constraint fija **presencia**. No verifica que la categoría de un ingreso
sea de ingreso — eso se queda en servicios (AC-15). Meterlo en la base pediría
un trigger o copiar `category.is_income` en cada fila de `transaction`, y los
escenarios de AC-17 solo piden que los registros rechacen un movimiento sin
categoría y una transferencia con una.

Es una frontera declarada, no un olvido: está escrita en ADR-0041 para que
nadie la "arregle" después.

### D5 — Las tres puertas quedan iguales

| Superficie | Cambio |
|---|---|
| REST | `TransactionCreate` gana `new_category: str \| None`; `GET /categories?is_income=` |
| MCP | `RecordExpenseInput` / `RecordIncomeInput` ganan `new_category` — paridad REST↔MCP es regla del charter §2 (ADR-0006/0009). Sin cambio de tier: sigue siendo `write-safe` (ADR-0020) |
| App | `transaction-create-dialog.tsx:253` pierde `allowNullLabel="Sin categoría"` — **esa línea es el hueco**. El select se re-consulta según el tipo. `EntitySelect` gana crear-en-línea y el formulario manda `new_category`, en un solo viaje, para que no se pierda lo tipeado (AC-5) |
| Recurrentes / Por pagar | El campo categoría pasa a obligatorio en sus formularios |

### Radio de impacto, medido

- **181 llamadas** a `record_expense` / `record_income` / `plan_payment` /
  `create_recurring` en **22 archivos** de test backend. **42 ya pasan
  `category_id`**; hasta 139 hay que enhebrar. Se resuelve con un fixture en
  `backend/tests/conftest.py` (que hoy solo tiene `session`) más barrido
  mecánico. Es el costo honesto de la regla y entra en F0 — F0 no está hecha
  con 139 tests rojos.
- `services/goals.py` crea patas de transferencia sin categoría (líneas 177,
  189, 280) y `planned.py:263` igual: siguen correctos, y ahora el CHECK los
  respalda.
- `planned.confirm_payment` mueve `planned → posted` sin tocar la categoría:
  no requiere cambios.

## Charter Check

| Regla del charter | Estado | Nota |
|---|---|---|
| §1 DAE + ATDD: la feature avanza por el pipeline de aceptación | ✅ | spec de 46 escenarios aprobado 2026-08-03; baseline 17 verde / 29 rojo deliberado |
| §1 Decisiones arquitectónicas como ADR | ✅ | ADR-0041 (constraint discriminado) y ADR-0042 (dirección + resolver) escritas en este checkpoint, en `proposed` |
| §1 ADRs respetadas, nunca contradichas en silencio | ✅ | ADR-0028 (read path) intacta; ADR-0005 (soft-delete) intacta — AC-10 la usa tal cual; ADR-0020 sin cambio de tier; ADR-0030 gobierna el backup previo a la migración |
| §1 Decisiones de producto separadas de las ADR técnicas | ⚠️ | Ver Amendments — ADR-024 dejó la categoría opcional a propósito; la enmienda (`product-decisions.md` § ADR-036) ya está escrita |
| §2 Postura local-only (ADR-0026/0030) | ✅ | Sin infraestructura nueva; la migración corre contra el Postgres local, nunca contra Render |
| §2 Layering api → services → domain → db | ✅ | `domain/rules.py` puro y sin sesión; el resolver en `services/`; routers y tools delgados. Coste declarado en ADR-0042: `transactions.py` y `planned.py` importan un servicio hermano |
| §2 Paridad REST ↔ MCP (ADR-0006/0009) + tiers (ADR-0020) | ✅ | `new_category` aparece en las dos superficies; sin cambio de tier |
| §3 Código/identificadores en inglés (ADR-0001); UI copy español | ✅ | `resolve_for_movement`, `is_income`; copy "Categoría *", "Crear categoría" en español |
| §3 Python ≥3.12, uv, pytest host-side con SQLite en memoria | ✅ | `batch_alter_table` existe precisamente para que la revisión funcione en el SQLite de los tests |
| §3 pnpm only / Biome / vitest colocado | ✅ | Sin dependencias nuevas en frontend |
| §3 Soft-delete uniforme (ADR-0005) | ✅ | AC-10 y AC-13 usan `archived` tal como está; restaurar es `unarchive_category`, que ya existe |
| §4 Alcance: finanzas personales, un usuario, local | ✅ | Sin superficie nueva fuera de eso; categorías de transferencia siguen parqueadas |
| §6 Strict gate: tests backend Y frontend de la superficie tocada | ✅ | Test strategy abajo; la superficie frontend son 3 formularios |
| §7 Autonomía medium + gates de datos | ✅ | La migración baja a `low` por el override del manifest; ADR-0030 exige backup fresco; el merge a `main` sigue siendo humano |
| Auto: stance de autonomía | ✅ | medium por defecto; `migrations/**` fuerza `low` — F2 tiene gate humano explícito con runbook |
| Auto: independencia de verificación (Principio 7) | ✅ | CP7 verify con `agent_id` distinto al de CP5 implement |
| Auto: política de mutación | ✅ | `opt_in` en el manifest; esta feature **opta por sí** sobre `domain/rules.py` y `services/categories.py` — ver Test strategy |
| Auto: presupuestos de performance | ✅ | Sección abajo (medium: informativos, no gate) |

### Amendments

**A1 — `docs/decisions/product-decisions.md` § ADR-024 se supersede
parcialmente.** Es la única desviación ⚠️, y su enmienda está escrita:

- **ADR-024** decía, aceptado: *"Optional category when recording.
  `Transaction.category_id` stays nullable… **Alternatives rejected.** Forcing
  a category always (friction)"*. Esta feature revierte esa cláusula.
- Su línea de `Status` ahora marca la cláusula como superseded por ADR-036 y
  deja en pie las otras dos (settings mínimos, importador sin UI), que esta
  feature no toca.
- **`product-decisions.md` § ADR-036** es la enmienda: registra la regla en
  lenguaje de comportamiento, con la medición que la justifica (131
  movimientos, $2.072.854 COP + US$7.486,68 en gastos y $7.003.101 COP +
  US$10.495,55 en ingresos invisibles; 10 de 14 recurrentes sin categoría), y
  responde la fricción que ADR-024 temía en vez de aceptarla — la categoría que
  falta se crea desde el mismo formulario.
- La distinción que la enmienda hace explícita: **`unbudgeted_spending`
  (ADR-016) no se toca.** Una categoría **sin sobre** sigue siendo unbudgeted;
  lo que desaparece es la plata **sin categoría**. Nunca fueron lo mismo.
- Del lado técnico, ADR-0041 y ADR-0042 nombran esta enmienda.

Ninguna otra fila queda en ⚠️.

### Deuda arrastrada, fuera del alcance de este plan

- **Seis fugas de implementación** en las specs entregadas (002, 005, 006,
  007), listadas en el handoff de CP3. Predatan esta feature y no tienen que
  ver con categorías. Tarea de consolidación, no de aquí.
- **`🔄 Payment / Transfer`**: 24 movimientos tipados como gasto que no son
  gasto. Ya tienen categoría, así que pasan la regla. Se decide cuando se
  desparque el discuss de categorías de transferencia.

## Phasing

Cuatro fases. El orden lo manda una dependencia dura: **la regla en servicios
tiene que aterrizar antes que el constraint.** Si el constraint llega primero,
cualquier ruta que todavía escriba `NULL` revienta con un error de driver en
vez de un mensaje legible.

- **F0 — La regla, en un solo lugar.** `domain/rules.py` gana el predicado de
  dirección; `services/categories.py` gana `resolve_for_movement` y el filtro
  `is_income` en `list_categories`; las cinco rutas de escritura pasan a
  llamarlo y pierden su copia del bloque. Incluye el **barrido de los ~139
  sitios de test backend** — la fase no está hecha con la suite roja.
  **Cierra 24 rojos → 41/46.** AC-14 cierra aquí, sin código propio: el
  asistente ya pasaba por servicios.

- **F1 — Las tres puertas iguales.** `new_category` en REST y MCP (paridad,
  charter §2); `GET /categories?is_income=`; frontend: muere
  `allowNullLabel="Sin categoría"`, el select se filtra por tipo, `EntitySelect`
  gana crear-en-línea, y los formularios de recurrentes y por-pagar exigen
  categoría. **Cierra 0 rojos de aceptación** — las specs no llegan al
  navegador — y se cubre con vitest y tests de router/tool. Va aquí, pegada a
  F0, para que no exista una ventana donde el formulario ofrezca algo que el
  backend rechaza.

- **F2 — La barrera en los datos.** Revisión `0010`: guarda previa, CHECK sobre
  `transaction`, `NOT NULL` sobre `recurring_item.category_id`, y el
  `__table_args__` del modelo. **Cierra 5 rojos → 46/46.**
  **Gate humano:** `migrations/**` baja la autonomía a `low` y ADR-0030 exige
  `just backup` fresco antes de tocar datos reales. Pasos en `runbook.md`.

- **F3 — Cierre.** Run de aceptación 46/46 en 008 y **246/246** global (002,
  005, 006 y 007 como candado de regresión); `spec-check`; suites backend y
  frontend completas; mutación sobre los dos módulos elegidos; ADR-0041 y
  ADR-0042 pasan de `proposed` a `accepted` con sus filas del índice.

Las tareas concretas no se enumeran aquí: salen de las specs, una spec = un
ciclo TDD, dirigidas por `atdd:atdd-team`.

## Performance budgets

Autonomía `medium` → informativos, no son gate de merge. Escala real: un
usuario, 41 categorías, ~640 movimientos, Postgres local.

| Medida | Presupuesto | Por qué |
|---|---|---|
| `resolve_for_movement` en el camino de escritura | +0 consultas sobre hoy | La búsqueda de categoría ya existía en las cinco rutas; se mueve, no se agrega. Crear en línea agrega 1 INSERT, y solo cuando el usuario lo pide |
| `list_categories(is_income=…)` | < 10 ms | Un WHERE sobre un booleano en 41 filas; no justifica índice |
| Guarda previa de la revisión `0010` | < 100 ms | Un agregado sobre ~640 filas, una sola vez |
| Reconstrucción de tabla en SQLite (`batch_alter_table`) | — | Corre una vez por base de datos de test: 46 escenarios de aceptación + 96 archivos de test backend. Es el riesgo real de esta feature sobre el tiempo de suite |
| Suite de aceptación completa | sin regresión > 20 % sobre la marca actual | Marca de hoy: 46 escenarios de 008 en 1,06 s |

Si la reconstrucción de SQLite se come el presupuesto, la salida es declarar el
CHECK en el `CREATE TABLE` de la revisión `0001` para bases nuevas y dejar
`batch_alter_table` solo en el camino de upgrade — pero eso rompe la propiedad
de que los tests recorren exactamente las migraciones que corrió producción, así
que se toma solo con la medición en la mano.

## Collaboration schedule

| Momento | Quién | Qué |
|---|---|---|
| Cierre de F0 | agente | Reporta 41/46 y el conteo real de tests backend tocados |
| Apertura de F2 | **humano** | `just backup` fresco (ADR-0030) antes de que la revisión toque datos reales |
| Apertura de F2 | **humano** | Corre la guarda previa contra producción y confirma que devuelve cero — ver `runbook.md` |
| Cierre de F1 | humano | Revisa los tres formularios en la app: es la superficie que el dueño usa todos los días |
| Cierre de cada fase | agente | Run de aceptación de la feature + reporte de rojos que cierra |
| CP5 → CP7 | agente distinto | Verificación independiente (Principio 7): quien verifica no es quien implementó |
| Merge a `main` | **humano** | Gate del charter §7, sin excepción |

Fuera de esos puntos el agente avanza solo: implementa, escribe y corre tests,
refactoriza y actualiza artefactos DAE en la rama `mandatory-categories`.

## Execution modes

| Fase | Modo | Autonomía |
|---|---|---|
| F0 — la regla en servicios | agente | `medium` |
| F1 — las tres puertas | agente, revisión humana de la UI al cerrar | `medium` |
| F2 — la barrera en los datos | agente, con gate humano en backup y conteo | `low` en `migrations/**`, `medium` en el resto |
| F3 — cierre | agente para las corridas; humano para el merge | `medium` |

Umbral de bucle atascado: 3 intentos (`stuck_loop_threshold` del manifest). Al
tercero el agente para y reporta en vez de seguir intentando.

Despacho remoto: no disponible (`remote.ready: false`) — todo corre local.

## Test strategy

`feature.md` no declara `validation_method`, así que aplica el stack DAE
estándar del charter: aceptación + unit + mutación. Se declara explícitamente
porque el charter §7 fija que el techo de validación es la superficie local de
tests — no hay staging, ni monitoreo, ni feature flags.

**1 — Aceptación (el contrato).**
`./run-acceptance-tests.sh features/008-mandatory-categories`.
Meta por fase: F0 → 41/46, F1 → 41/46 (sin movimiento, es superficie),
F2 → 46/46. En F3 la suite completa: **246/246**, con 002, 005, 006 y 007 como
candado de regresión — esas cuatro ya sobrevivieron la enmienda de CP3 sin una
sola regresión y tienen que seguir así. Los tests generados no se editan nunca;
solo se regeneran.

Ningún binding de handler necesita ajuste: los 46 patrones de
`acceptance/handlers/mandatory_categories.py` ya nombran la superficie
post-feature, y su docstring **es** el contrato de implementación de F0/F2.

**2 — Unit backend.** Los ~139 sitios que hoy registran plata sin categoría se
enhebran en F0 con un fixture nuevo en `conftest.py`. Tests propios nuevos:
el predicado de dirección de `domain/rules.py` (puro, sin sesión), cada rama de
`resolve_for_movement`, y la revisión `0010` en las dos direcciones —
`upgrade` sobre datos sucios se niega con el conteo, `downgrade` tira el
constraint y deja la tabla usable.

**3 — Unit frontend (vitest, colocado).** `transaction-create-dialog.test.tsx`
y `transaction-edit-dialog.test.tsx` ya existen. Casos nuevos: el select no
ofrece "Sin categoría"; cambiar Gasto↔Ingreso re-consulta y cambia las
opciones; crear en línea manda `new_category` y conserva payee, monto, fecha y
notas.

**4 — Mutación (opt-in).** El manifest la deja `opt_in` / `changed_files` /
`on_demand`. Esta feature **opta por sí** sobre `domain/rules.py` y
`services/categories.py`, y solo sobre esos dos: el resolver es el único punto
de aplicación de toda la regla, así que un mutante que sobreviva ahí es un
agujero en la feature entera, no un test flojo. Corre en F3.

**5 — Lo que no cubre ningún test.** La revisión `0010` sobre los datos reales
del dueño. Eso es el `runbook.md`, con backup previo y conteo confirmado a
mano.

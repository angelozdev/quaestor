---
slug: fund-belongs-to-its-charge
checkpoint: 4
plan_status: proposed
created: 2026-08-15
---

# Plan — 015 fund-belongs-to-its-charge

## Architecture

### La decisión de fondo

**Un `recurring_id` opcional sobre `Fund`.** No una tabla nueva, no una columna
sobre el cobro. Registrada como **ADR-0057**, que sustituye la cláusula «una
categoría lleva un fondo» de la ADR-0043 **solo para la regla `from-recurring`**.

```
Fund
  category_id   NOT NULL   ← se conserva; la copia el cobro
  recurring_id  NULL       ← nuevo: de qué cobro cuelga, si cuelga de uno

  uq_fund_category   →  único parcial  WHERE recurring_id IS NULL
  uq_fund_recurring  →  único          sobre recurring_id
```

El parcial es la frontera escrita en el esquema: `fixed` y `average` siguen
siendo una por categoría —que es lo único que el argumento de la 0043 defendía—
y la puerta se abre solo donde ese argumento no aplica.

`category_id` se conserva **no nulo** a propósito. Todo lo que hoy agrupa fondos
por categoría —el nombre en la fila, el término del mes, la lista— sigue
funcionando sin ramificarse, y el cobro ya trae su categoría obligatoria
(ADR-0041), así que no hay ningún estado nuevo que validar.

### La pieza que abarata la feature

`load_month_aggregate` ya agrupa el gasto en **una sola consulta** por
`(categoría, año, mes, moneda)`, y ya excluye lo que fue a una meta con
`meta_id IS NULL` (ADR-0046). Agregar `recurring_id` al `GROUP BY` da las dos
mitades del doble conteo **en la misma consulta y al mismo costo**:

| lectura | de dónde sale | qué AC cierra |
|---|---|---|
| lo que gastó la categoría **sin** lo que saldó un cobro marcado | filas cuyo `recurring_id` no tiene caja | AC-9, mitad de arriba |
| lo que se gastó saldando **ese** cobro | la fila de ese `recurring_id` | AC-9, el espejo |

Sin consulta nueva, sin tocar la ADR-0028. El precedente exacto —excluir del
promedio lo que otro sustantivo ya contó— lo escribió la 009 hace una semana
para las metas.

### Flujo de datos

```
api/routers/recurring.py   marcar / destildar
        ↓
services/funds.py          mark_charge() · unmark_charge()
        ↓                  crean y borran el Fund con recurring_id
domain/models.py           Fund.recurring_id
        ↑
services/month_aggregate.py   spent_in(cat, mes)      ← ya sin lo saldado
                              settled_in(cobro, mes)  ← nuevo, misma consulta
        ↑
services/funds.py          _walk / _ask / _obligations
        ↓
services/month.py          funded_categories() se parte en dos
```

### Lo que se retira

`funds._settled_by_spending` — el heurístico que ordena los turnos del más
próximo al más lejano y va restando lo gastado. Un gasto de 7.000.000 en
🛡️ Auto Insurance deja de vaciar la caja del Seguro por ser del tamaño correcto.
Lo reemplaza el `recurring_id` del movimiento, que ya existe desde la 013.

### Acoplamiento y radio de impacto

Medido, no estimado:

| símbolo | sitios | qué pasa |
|---|---|---|
| `funded_categories()` | 3 en `month.py` + 1 definición | se parte en dos preguntas: la categoría entera vs. este cobro |
| `fund_on_category()` | 2 (`mcp/tools/funds.py`, `_refuse_a_second_fund`) | pasa a preguntar solo por el fondo de categoría |
| `uq_fund_category` | 1 modelo + 1 migración | pasa a único parcial |
| `_settled_by_spending` | 1 llamador (`_obligations`) | se borra |
| `record_expense()` | firma | gana `recurring_id`, espejo de `meta_id` |

**Una categoría puede quedar cubierta a medias**, y ese es el único punto donde
el cambio no es local. Hoy `funded_categories()` es un interruptor: si la
categoría tiene fondo, nada de lo suyo entra en «lo que nada cubre». Con cajas
por cobro, 🍽️ Restaurantes puede tener su promedio **y** un cobro marcado, o
ningún fondo de categoría y un solo cobro marcado. El término de obligaciones de
`_uncovered` deja de contar los cobros que ya tienen caja propia, y sigue
contando los demás de esa categoría.

### La quinta puerta se cierra rechazando

`archive_category` ya **rechaza** archivar una categoría con fondo (003, AC-21).
El dueño reconfirmó el 2026-08-15 que siga así para las cajas por cobro, contra
lo que la AC-8 decía. Es la única de las cinco puertas que no borra nada: no
puede quedar una caja huérfana por ahí porque la puerta no abre. `acs.md` y
`spec.md` quedaron corregidos el mismo día.

### Alternativas descartadas

Las cuatro opciones y su balance están en la **ADR-0057**. En una línea cada una:
la lista sobre el fondo de categoría (Actual Budget) el dueño ya la evaluó con la
evidencia delante y la rechazó; la tabla aparte duplica el fold, el estado y la
API por un sustantivo que contesta lo mismo; y derivar la caja desde una columna
en el cobro deja el mes en que se marcó y lo que ya guardó en la tabla
equivocada, y bifurca toda la API que hoy toma un `fund_id`.

## Charter Check

| # | Regla del charter | Estado | Evidencia |
|---|---|---|---|
| §1 | DAE con ATDD completo; ADRs para lo arquitectónico | ✅ | `feature.md`, `acs.md`, `spec.md` + IR ya existen. **ADR-0057** escrita (`proposed`), sustituye la cláusula de la 0043. **ADR-0056** sigue `proposed` — la AC-2 la vuelve prueba. |
| §2 | Posture local-only; capas `api/ → services/ → domain/ → db`; migraciones en `migrations/` | ✅ | Nada remoto. El cambio entra por `api/routers/recurring.py` → `services/funds.py` → `domain/models.py`. Una migración Alembic nueva. |
| §3 | Inglés en el código; Python ≥3.12 + uv + pytest; pnpm; Biome; Conventional Commits; soft-delete para masters | ✅ | Un fondo se **borra**, no se archiva — frontera ya declarada por la ADR-0043 («es una regla atada a una categoría, no un master»). Nada más cambia de convención. |
| §4 | Un solo usuario, local; el **fondo** como sustantivo único | ✅ | Sigue siendo un sustantivo: un `Fund`, un fold, un estado. La opción de la tabla aparte se descartó justo por esto. |
| §5 | Roles architect / implementer / acceptance-tester / reviewer | ✅ | CP4 architect, CP5 implementer, el spec ya está escrito, CP6–CP8 reviewer. |
| §6 | Nada mergea sin backend **y** frontend verdes en la superficie tocada | ✅ | Stream `mixed`: 38 escenarios `@backend` (pytest generado) + 11 de pantalla (vitest). |
| §6 | **Una pantalla que escribe plata se prueba contra una cuenta en otra moneda** | ⚠️ | El formulario de gasto gana el enlace «¿qué cobro salda esto?» (AC-5) y **ningún escenario de la AC-5 usa otra moneda**. Remedio abajo. |
| §6 | **Una cifra que la app convierte se prueba en otra moneda también** | ✅ | AC-11, tres escenarios `@backend` en USD más uno de pantalla; uno cambia la TRM de 4000 a 5000 y exige que la cifra propia del fondo no se mueva. |
| §6 | **Verde no es verificado: se maneja en navegador antes de darla por hecha** | ✅ | Programado como puerta del CP7, no del CP5. El contenedor del frontend **sí** recarga en caliente (montajes en `docker-compose.yml`), así que no hay excusa para saltarlo. |
| §7 | Autonomía media con puertas de datos | ✅ | El agente implementa y prueba solo en la rama. |
| §7 | **Humano obligatorio para migraciones que tocan datos reales** | ✅ | La rebanada 4 **para** y espera al dueño. Backup fresco por la ADR-0030 antes de correrla. |
| §7 | Humano obligatorio para merges a `main` | ✅ | El merge es suyo. |
| — | Postura de autonomía declarada | ✅ | `medium`, con `migrations/**` capado a `low` — respetado por el corte de la rebanada 4. |
| — | Independencia de la verificación | ✅ | Los 49 escenarios se escribieron y quedaron rojos **antes** del plan (CP3, 47 casos fallando). Ninguno se puede ajustar para que pase sin que se note. |
| — | Política de mutación | ✅ | Sweep de mutación en el CP8, como la 014. La suite de backend **no es hermética** (`test_scheduler` toca `backend/quaestor.db` en disco): migrar un worktree limpio antes del sweep. |
| — | Presupuestos de rendimiento | ✅ | Declarados abajo; la 014 ya dejó el escenario que los mide. |

### Amendments

**Ninguna enmienda al charter.** La única ⚠️ es un hueco del `spec.md`, no una
desviación de la regla — la regla es correcta y el remedio es una prueba, no una
excepción.

**Remedio de la ⚠️ (§6, moneda extranjera en el formulario de gasto).** Un
escenario a agregar a la AC-5, que necesita el permiso explícito del dueño porque
toca `spec.md`:

```gherkin
@backend
Scenario: A dollar payment settles its dollar charge without passing through pesos
  Given a recurring charge "Opal" on "Tecnología" of 600.00 USD every year, next due 2027-08
  And "Opal" is marked to be saved for
  When the user records an expense of 600.00 USD in category "Tecnología" settling "Opal"
  Then the fund for "Opal" says the charge lands in 2028-08
  And the fund for "Opal" asks 50.00 USD this month
```

Sin él, el descuento de la caja pasa por centavos COP —que es como
`spent_by_cat_month` guarda todo— mientras la caja reporta en dólares, y
convertir de vuelta a la TRM del día es exactamente el defecto del 2026-08-13:
fijar `"COP"` donde iba la moneda de la meta reportó un aporte de 800 dólares
como $800 en vez de $3.200.000, y pasó 1.325 pruebas verdes.

**Hasta que el dueño lo autorice, la rebanada 3 no se da por cerrada.**

## Phasing

Cuatro rebanadas verticales — cada una atraviesa esquema, servicio y pantalla, y
cada una termina con sus escenarios en verde.

### Rebanada 1 — Marcar un cobro crea su caja, y la caja se explica

*AC-1, AC-2, AC-3, AC-10, AC-11 · 18 escenarios*

`Fund.recurring_id` + el único parcial + la migración de esquema. `mark_charge`
y sus cinco negativas. `_obligations` lee un cobro cuando el fondo cuelga de uno.
`FundStatus` gana la moneda del cobro. En pantalla: la marca en Recurrentes y la
fila propia en Fondos.

Termina cuando una caja existe, pide la cifra correcta, la explica en tres
términos y habla la moneda de su cobro.

### Rebanada 2 — Ninguna caja sobrevive a su cobro

*AC-4, AC-7, AC-8 · 13 escenarios*

`unmark_charge`. Las tres puertas que borran (apagar, borrar, editar a mensual),
la que rechaza (archivar la categoría) y el aviso previo de la edición de
cadencia. Ningún movimiento se toca en ninguna.

Termina cuando la invariante «existe si y solo si su cobro está marcado y vivo»
se cumple después de operaciones mezcladas.

### Rebanada 3 — Un peso se pide una vez y se descuenta una vez

*AC-5, AC-9 · 11 escenarios + el de moneda pendiente de permiso*

`recurring_id` al `GROUP BY`. `record_expense(recurring_id=…)`. El enlace en el
formulario de gasto. `funded_categories()` se parte en dos y el término de
obligaciones de `_uncovered` deja de contar los cobros con caja propia.
`_settled_by_spending` se borra.

Termina cuando los mismos tres meses de gasto promedian 300.000 con el cobro sin
marcar y 100.000 con el cobro marcado, mientras su caja pide 200.000 — 300.000 de
las dos formas.

### Rebanada 4 — La migración · **PARA Y ESPERA AL DUEÑO**

*AC-6 · 3 escenarios*

Un fondo se convierte en dos, los dos marcados. Cero anchors que repartir.

**Puerta dura del CHARTER §7:** `migrations/**` está capado a autonomía `low`.
El agente escribe la migración y la prueba contra una copia restaurada; **no la
corre contra los datos reales sin el dueño delante**, y con un `just backup`
fresco antes (ADR-0030).

Termina cuando `636.363,64 + 49.700,00 = 686.063,64` — exactamente lo que pide
hoy el único fondo que existe — y Fondos pasa de 5 filas a 6.

## Performance budgets

La ADR-0028 acota el camino de lectura y la 014 ya dejó la prueba que lo mide.

| presupuesto | hoy | techo | cómo se mide |
|---|---|---|---|
| statements para leer un mes | *n* | *n*, sin cambio | escenario de la 014 *«the month was read once, not once for each fund»*: lee el mes con 5 fondos y con 1 y exige que cuesten lo mismo |
| consultas nuevas | — | **cero** | `recurring_id` entra como columna del `GROUP BY` que ya existe |
| filas del agregado de gasto | (cat, mes, moneda) | × cobros distintos por celda | cota real ≤ 3 hoy; el dueño tiene 2 cobros en su categoría más poblada |
| fold de fondos | 1 walk por fondo | 1 walk por fondo | 5 fondos pasan a 6; el walk no cambia de forma |

Si la cuenta de statements se mueve, la rebanada 3 está mal hecha.

## Collaboration schedule

| momento | quién | qué |
|---|---|---|
| antes de la rebanada 1 | dueño | aprueba este plan y el escenario de moneda de la AC-5 |
| fin de cada rebanada | agente | reporta escenarios verdes y qué queda rojo |
| antes de la rebanada 4 | **dueño, obligatorio** | `just backup`, y está delante cuando la migración toca datos reales |
| CP7 | dueño + agente | paso por navegador contra el sandbox, saldos en centavos |
| merge a `main` | **dueño** | CHARTER §7 |

## Execution modes

- **Rebanadas 1–3:** autonomía `medium`. El agente implementa, prueba y refactoriza
  en la rama `fund-belongs-to-its-charge` sin parar.
- **Rebanada 4:** autonomía `low`. Escribe y prueba sola; para antes de correr.
- **Sin dispatch remoto:** `remote.ready: false`.
- **Una rebanada, un commit** con Conventional Commits, y las pruebas de esa
  rebanada verdes antes del siguiente.

## Test strategy

`feature.md` declara un `validation_method` propio, así que manda sobre el
estándar:

> «Los tres flujos (pytest, aceptación generada, vitest), más un ensayo de la
> migración contra una copia restaurada de producción con el dueño delante […]
> Ninguna otra cifra del mes puede moverse. Más el paso por navegador que exige
> el CHARTER §6.»

Eso da cinco capas:

1. **Aceptación generada** — 49 escenarios, 38 `@backend` → 47 casos pytest.
   Hoy 47/47 en rojo, todos por `unsupported step`. Es la línea base: cualquier
   verde antes de escribir código es un binding mal hecho, no una feature.
2. **Vitest** — los 11 escenarios de pantalla, bound por nombre. `spec_coverage.py`
   falla mientras alguno quede sin prueba, así que no se pueden olvidar.
3. **Unitarias** — la segunda corriente de la ATDD. Donde más hacen falta: el
   único parcial (dos fondos `fixed` sobre una categoría siguen rechazándose), el
   nuevo `settled_in`, y `funded_categories()` partida en dos.
4. **Ensayo de migración contra producción restaurada, con el dueño delante** —
   la rebanada 4. Se comprueba `686.063,64` antes y después, y que ninguna otra
   cifra del mes se mueva.
5. **Paso por navegador antes de darla por hecha** (CHARTER §6) — saldos leídos en
   centavos, no de la pantalla, que redondea. La 009 pasó con la tubería entera
   verde y el navegador de la 012 encontró tres defectos más.

**Mutación en el CP8**, como la 014. Con la advertencia medida: la suite de
backend no es hermética —`test_scheduler` toca `backend/quaestor.db` en disco—
así que el sweep se corre sobre un worktree limpio y migrado.

**Durante el rojo de la ATDD no se tocan los handlers para que pase nada.** Los
47 rojos de hoy son el estado esperado hasta que exista la conducta.

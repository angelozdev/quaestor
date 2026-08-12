---
slug: fund-explains-what-it-asks
checkpoint: 4
plan_status: approved
created: 2026-08-12
---

# Plan — 014 fund-explains-what-it-asks

## Architecture

### La forma: el desglose ya se calcula, y se tira

Así se arma hoy la cifra de un fondo de suscripciones
(`services/funds.py`, `_ask_from_obligations`):

```python
amount = sum(
    fund_ask_calc(o.required - taken, months_to_fund(year_month, o.charge_month))
    for o, taken in zip(obligations, claimed, strict=True)
)
```

**Cada sumando de esa suma es una línea del desglose.** Se calcula, se suma y se
descarta. El nombre del cobro se pierde un paso antes: `_obligations` construye
`_Obligation(required, charge_month)` a partir de `item`, que lo tiene y no lo
pasa.

De ahí salen dos propiedades que no hay que programar:

| | |
|---|---|
| **AC-17** — mirar el mes no cuesta más | Cero lecturas nuevas: los números ya están calculados |
| **AC-4** — las líneas suman la cifra | Las líneas **son** los sumandos; no pueden no cuadrar sin romper la suma |

El cambio es **conservar** en vez de descartar:

- `_Obligation` gana `name` y `can_be_spread` — los dos salen de `item`, ya en
  mano, sin leer nada.
- `_Ask` gana las líneas, que son los términos que ya suma.
- `FundStatus` las lleva hasta la pantalla.

### El aviso: cambia de qué habla, no cómo lo dice

Hoy `_warning` recibe `walked.ask.charge_month`, que `_ask_from_obligations`
fija en `obligations[0].charge_month` — **la más próxima** — y cita `would_ask`,
**el total**. Con cualquier cobro mensual en la categoría lo más próximo vence
siempre este mes, así que salta siempre.

Arreglar el texto no arregla nada. Lo que cambia es el sujeto:

> El aviso deja de ser sobre el fondo y pasa a ser sobre **una obligación**: la
> primera que *se podría* repartir y no tiene meses para hacerlo.

Un cobro mensual no entra en esa definición nunca, porque entre un mes y el
siguiente no hay meses que repartir. **La AC-13 deja de ser una condición que
alguien debe recordar comprobar y pasa a ser una consecuencia de la definición.**

`can_be_spread` vive en la línea, no en el aviso, para que el aviso no tenga que
saber de recurrencias. ADR-0054.

### Lo único con un dato nuevo: no ofrecer la regla

La AC-14 es lo único que la pantalla no puede responder hoy: si esa categoría
tiene algo repartible. **Reusa la vista previa que ya existe** —
`POST /funds/preview`, que nunca escribe — con un campo más, en vez de abrir un
camino nuevo. Un endpoint menos que mantener y una consulta menos que acotar.

### Lo que no se toca

`asks`, `holds`, `carries`, `on_track`, `next_month_has`, el motor de
ocurrencias, y las reglas `fixed` y `average`. **Ni una línea.**

El asistente tampoco: `mcp/format.py:354` arma su tarjeta nombrando los campos
uno por uno, así que el desglose no le llega solo. Pero `fund_preview_card`
imprime `preview.warning` tal cual, así que **la corrección del aviso le llega
sin tocarlo**.

## Charter Check

| Regla del charter | | Nota |
|---|---|---|
| §1 Decisiones significativas van a ADR | ✅ | ADR-0054, aceptada, citada por el plan |
| §2 Capas backend `api/ → services/ → domain/` | ✅ | El desglose nace en `services/funds.py` y viaja en un DTO de dominio |
| §2 Paridad MCP con REST | ⚠️ | Ver enmienda |
| §3 Inglés en código, español en la UI | ✅ | |
| §3 pnpm, Biome, Conventional Commits | ✅ | |
| §6 Nada se mergea sin las dos suites verdes | ✅ | |
| §6 Una pantalla que escribe plata se prueba contra otra moneda | ✅ | AC-10 cubre el cobro en dólares; **esta pantalla no escribe** |
| §6 Verde no es verificado: se conduce en navegador | ✅ | Rebanada 4 |
| §7 Humano requerido para migraciones sobre datos reales | ✅ | **No hay migración.** Nada se guarda |
| §7 Autonomía media | ✅ | Sin topes de ruta: no toca `migrations/**` ni `.dev-data/**` |
| Postura de autonomía: mutación | ✅ | `services/funds.py` ya está en la lista de la 003 |
| Independencia de verificación | ✅ | CP6, CP7 y CP8 con `agent_id` distintos, como en la 013 |

### Amendments

**§2 — paridad MCP.** El asistente no recibirá el desglose. Es una desviación
consciente de la AC-28 de la 003, decidida por el dueño el 2026-08-12 («no hagas
nada sobre el asistente») porque la superficie se va a deprecar, y **registrada
en ADR-0054 → Consequences → Costos**. No hace falta enmienda al charter: §2 pide
paridad de la superficie MCP, y la decisión de producto de deprecarla es anterior
a este plan y ya está escrita en el roadmap.

**Ninguna otra desviación.** La fila ⚠️ es la única, y tiene su ADR.

## Phasing

Cuatro rebanadas. Cada una deja las dos suites verdes.

**1 — Los términos (backend).** `_Obligation` gana nombre y si se puede
repartir; `_Ask` conserva las líneas; `FundStatus` las expone. Cierra AC-1, AC-2,
AC-3, AC-4, AC-5, AC-6, AC-7, AC-10, AC-16, AC-17. Es la rebanada grande y no
cambia ninguna cifra.

**2 — El aviso (backend).** `_warning` pasa a recibir las líneas en vez del mes
más próximo y el total. Cierra AC-11, AC-12, AC-13, AC-18. Es la más pequeña y la
que más comportamiento cambia.

**3 — Las pantallas (frontend).** La fila con sus líneas, el formulario que no
ofrece la regla donde no aplica, y el campo nuevo en la vista previa. Cierra
AC-8, AC-9, AC-14, AC-15. Aquí se escriben los 7 escenarios de vitest que hoy
están sin ligar.

**4 — El navegador.** Contra el sandbox, comparando el desglose que la pantalla
muestra contra el que el servicio calcula. No cierra criterios: comprueba que los
cerrados son alcanzables.

## Performance budgets

**El presupuesto es cero.** La ADR-0028 acotó lo que un mes carga, y esta feature
no lo abre: los números del desglose ya se calculan dentro de ese límite.

Medida a mantener: leer cinco fondos no debe costar más lecturas que leer uno.
El escenario de la AC-17 lo exige y CP7 lo mide.

## Collaboration schedule

| Momento | Quién | Qué |
|---|---|---|
| CP5, tras la rebanada 2 | dueño | Que el aviso deje de saltar donde miente, leído en la app |
| CP5, rebanada 4 | dueño | La pasada en navegador |
| CP6 / CP7 / CP8 | agentes frescos | Independencia (§6), `agent_id` distintos entre sí y del implementador |

Sin puertas de datos: no hay migración ni escritura.

## Execution modes

Autonomía **media** sin topes de ruta. El agente implementa, prueba y refactoriza
solo. Se detiene en las dos filas de arriba.

## Test strategy

El `validation_method` de `feature.md` pide más que las suites: **una lectura de
las cuatro categorías reales contra una copia restaurada de producción**,
comparando el desglose de la pantalla contra el del servicio, y exigiendo que la
cifra total no cambie en ninguna. Eso es CP7, y es lo que de verdad prueba la
AC-5 — las suites usan números limpios (80.000, 100.000) justamente porque no
pueden ver los sucios.

Además del estándar:

1. **Aceptación** — los 32 escenarios; 25 generados contra la capa de servicios,
   7 en vitest.
2. **Unitarias** — backend y frontend, ambas suites verdes en cada rebanada.
3. **`spec-coverage`** — hoy en rojo a propósito; verde cuando los 7 escenarios
   de pantalla tengan su test. Es el detector que en la 013 cazó dos escenarios
   ligados sin querer a otra feature.
4. **Mutación (opt-in)** — `backend/src/quaestor/services/funds.py`, ya en la
   lista desde la 003. Comando:

   ```
   cd backend && SESSION_SECRET=$(python3 -c "print('x'*64)") uv run pytest -q
   ```

   Un superviviente dentro de la condición del aviso sería el defecto de vuelta.

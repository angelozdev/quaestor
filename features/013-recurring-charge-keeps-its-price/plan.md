---
slug: recurring-charge-keeps-its-price
checkpoint: 4
plan_status: approved
created: 2026-08-11
---

# Plan — 013 recurring-charge-keeps-its-price

## Architecture

### La forma: esto es un borrado con un invariante encima

Hoy `services/recurring.py:112` exige que la moneda declarada sea la de la
cuenta, y `:267` enruta la misma pregunta por `_tx.retarget`, que reescribe en
vez de dejar que las dos difieran. Las dos se van.

En su lugar queda **un predicado**, en `services/recurring.py`:

> una regla que se cobra sola tiene que estar en la moneda de su cuenta.

Comprobado en **un solo sitio**, justo antes del commit, por el que pasan las
cuatro puertas que podrían romperlo: crear, cambiar el monto, cambiar el modo y
cambiar la cuenta. Cuatro guardas dispersas serían cuatro sitios donde olvidarse
de una — y la 0052 existió precisamente porque una de ellas vivía solo en un
docstring.

**El «exige» de AC-13 cae solo del invariante.** Mover una regla manual sin
reescribir el monto lo pasa; mover una automática no. No hay que programar dos
veces la diferencia entre sugerir y exigir.

### El motor no cambia una línea

`occurrences._create_occurrence_tx` ya copia `item.amount` **y**
`item.currency` al cobro que nace. De ahí:

| | |
|---|---|
| Regla manual, monedas distintas | nace un cobro esperando en la moneda del precio, sin mover saldo — **AC-5, AC-6** |
| Regla automática | el invariante garantiza que coinciden, así que `acc.balance += delta_balance(...)` sigue siendo correcto — **AC-12** |

Verificado leyendo el módulo, no supuesto. Es el mejor argumento a favor del
invariante: protege exactamente la línea que podría abrir un hueco de plata.

### Confirmar: una línea, reusando `retarget`

`services/planned.py:232` solo reescribe la moneda cuando el dueño nombra otra
cuenta. Con 013 un cobro puede discrepar de su **propia** cuenta.

```
antes:   if account_id is not None and _tx.retarget(session, tx, account_id, amount):
después: if _tx.retarget(session, tx, account_id or tx.account_id, amount):
```

Un cobro en la misma moneda entra, `crosses` sale falso y **nada cambia**. El de
Hevy Pro entra por la rama que ya existe y exige la cifra reescrita. **AC-7,
AC-8, AC-9 y el rechazo de AC-8 salen de ahí.** `retarget` no se modifica: sigue
siendo la función que 012 dejó probada por mutación.

### AC-21: lo único de verdad nuevo

Un movimiento **no expone hoy de qué regla salió** — `recurring_id` está en el
modelo y no en `TransactionOut`. Hace falta:

- `TransactionOut` gana `rule_amount` y `rule_currency`, nulos cuando no hay
  regla o cuando la regla coincide con la cuenta.
- `from_tx` los recibe como parámetro, igual que ya recibe `tag_names` — no
  abre sesión.
- El camino de listado resuelve las reglas referenciadas **en bloque**, una
  consulta por página, nunca una por fila.
- El informe del mes las resuelve **en memoria**: `load_month_aggregate` ya trae
  `active_recurring`.

**Solo reglas encendidas**, decidido por el dueño el 2026-08-11: traer también
las apagadas haría crecer el camino de lectura acotado de ADR-0028 con cada
suscripción cancelada de por vida, a cambio de una etiqueta en un cobro viejo.

### La migración se protege sola

Una revisión de Alembic que empareja por **nombre + monto actual + moneda
actual**. Si no cuadra exactamente con `Hevy Pro / 30,22 USD` o
`Smart Fit / 37,20 USD`, no hace nada.

Eso importa porque las migraciones corren en **todas** las bases — la de prueba,
el sandbox, cualquiera nueva. Ahí no encuentra nada y sigue. En la del dueño
escribe los dos precios y pasa las dos reglas a manual, porque el invariante
prohíbe lo contrario.

Los precios se **cargan**: `99900_00` y `120000_00` en el cuerpo de la
migración. Convertir daría 94.951 y 116.882 (AC-20).

### Frontend

| Superficie | Qué cambia |
|---|---|
| `app/(app)/recurring/page.tsx` | la moneda se elige aparte de la cuenta; la fila muestra precio y conversión (AC-3, AC-4); mover cuenta propone (AC-13); el modo automático se rechaza con las dos salidas (AC-2) |
| `app/(app)/to-pay/page.tsx` | el diálogo propone la conversión para un cobro que discrepa de su cuenta (AC-7), y llega vacío sin tasa (AC-10) |
| detalle del movimiento | la línea del precio de la regla (AC-21) |
| `lib/money.ts` | **nada nuevo** — `amountForAccount` de 012 hace exactamente esto |

### Lo que NO se toca, y por qué

- **`retarget`** — su contrato para movimientos ya registrados es correcto y
  está probado por mutación. Solo pierde su call site en `recurring.py`.
- **El asistente** — ni se le da ni se le quita nada (AC-17). Al quitar la
  guarda del servicio hereda la capacidad sin una línea; la única alternativa
  sería *añadir* una guarda a una superficie que se va a deprecar.
- **`spec.md` de la feature 007** — su fila `USD` sobre cuenta `COP` usa
  `paying itself` y el invariante la mantiene rechazada. Comprobado corriendo la
  suite.
- **ADR-0031** — ninguna tasa se congela por movimiento.

## Charter Check

| Regla de la carta | Cumple | Evidencia |
|---|---|---|
| §1 ADRs para lo arquitectónicamente significativo | ✅ | ADR-0053, acepta y reemplaza la 0052; índice y cabecera de la 0052 actualizados |
| §2 Capas backend `api → services → domain → db` | ✅ | el invariante vive en `services/recurring.py`; el router no gana lógica; `domain/models.py` no cambia |
| §2 Migraciones en `migrations/` (Alembic) | ✅ | una revisión nueva, idempotente y auto-guardada |
| §3 Inglés en el código; copy en español | ✅ | identificadores en inglés; el rechazo de AC-2 es copy y va en español |
| §3 pnpm, Biome, vitest colocado | ✅ | sin dependencias nuevas |
| §3 Conventional Commits | ✅ | en uso en toda la rama |
| §6 Nada se mergea sin las dos suites verdes | ✅ | ver Test strategy |
| §6 Una pantalla que escribe plata se prueba contra una cuenta en otra moneda | ✅ | *toda* la feature es ese caso; DolarApp aparece en 47 de los 53 escenarios |
| §6 Verde no es verificado: se maneja en el navegador | ✅ | fase 5 del Phasing, contra el sandbox, saldos en centavos |
| §7 Autonomía media | ✅ | manifiesto: `allowed_levels [low, medium]` |
| §7 Override de ruta `migrations/**` → `low` | ✅ | la fase 4 va a nivel bajo, con el dueño delante |
| §7 Humano requerido: migración sobre datos reales | ⚠️ | ver Amendments |
| Independencia de verificación (Principio 7) | ✅ | CP6, CP7 y CP8 en agentes frescos; `main-session` no escribe código de implementación |
| Política de mutación | ✅ | `services/recurring.py` entra a la lista de opt-in — ver Test strategy §4 |

### Amendments

**Ninguna enmienda a la carta.** La fila ⚠️ no es una desviación: CHARTER §7 dice
que la migración sobre datos reales **requiere al humano**, y el plan lo acata en
vez de esquivarlo. `runbook.md` lo convierte en pasos con dueño explícito, y la
fase 4 no se marca hecha sin la evidencia que ese runbook pide.

## Phasing

Cinco rebanadas. Cada una deja las dos suites verdes salvo donde se dice.

**1 — El invariante (backend).** Quitar las dos ataduras, añadir el predicado y
llamarlo desde las cuatro puertas. Cierra AC-1, AC-2, AC-5, AC-6, AC-12, AC-13,
AC-14, AC-15, AC-16, AC-17, AC-18. Es la rebanada grande y es casi toda borrado.

**2 — Confirmar (backend).** La línea de `planned.py`. Cierra AC-7 (mitad
servicio), AC-8, AC-9, AC-10 (mitad servicio), AC-11.

**3 — Las pantallas (frontend).** Recurrentes, «por pagar», detalle del
movimiento, y los dos campos nuevos en la lectura del movimiento. Cierra AC-3,
AC-4, AC-7, AC-10, AC-13 (la sugerencia), AC-21. Aquí se escriben los 11
escenarios de vitest que hoy están sin ligar.

**4 — La migración.** Autonomía `low`, dueño delante, respaldo fresco primero.
Cierra AC-19 y AC-20. Ver `runbook.md`.

**5 — El navegador.** Contra el sandbox, con una cuenta en dólares y los saldos
leídos en centavos, no en pantalla. No cierra criterios: comprueba que los
cerrados son alcanzables.

## Performance budgets

| Camino | Presupuesto | Cómo se comprueba |
|---|---|---|
| Informe del mes | **sin cambio** respecto a hoy (ADR-0028) | el precio de la regla se resuelve en memoria sobre `active_recurring`, ya cargado |
| Lista de movimientos | **+1 consulta por página**, nunca por fila | una resolución en bloque de las reglas referenciadas |
| Detalle de un movimiento | +1 consulta | una regla, por id |
| Crear / editar una regla | **sin cambio** | el invariante lee la cuenta que la puerta ya carga |
| Materializar cobros | **sin cambio** | el motor no se toca |

Fuera de presupuesto por decisión del dueño: cargar reglas apagadas para el
informe. Crecería con cada suscripción cancelada.

## Collaboration schedule

| Momento | Quién | Qué |
|---|---|---|
| Antes de la fase 4 | dueño | `just backup`, y estar presente (CHARTER §7) |
| Después de la fase 4 | dueño | leer las dos reglas en la app y confirmar precio, cuenta y modo |
| Después de la fase 5 | dueño | ver la grabación de la pasada por el navegador |
| CP6 en adelante | agentes frescos | `main-session` no escribe implementación |

## Execution modes

| Fase | Modo | Por qué |
|---|---|---|
| 1, 2 | subagente local | acotado, con la suite roja como criterio de parada |
| 3 | subagente local | 11 escenarios de vitest esperando, contrato claro |
| 4 | **el dueño y yo, juntos** | datos reales, CHARTER §7, autonomía `low` |
| 5 | yo, con Chrome MCP | la pasada por el navegador es de la sesión principal |

Despacho a la nube: no habilitado (`remote.ready: false`).

## Test strategy

Incorpora el `validation_method` de `feature.md`, que no es el de por defecto.

**1 — Aceptación generada.** 53 escenarios; 47 tests de servicio hoy en rojo (38
fallando, 9 controles verdes). El pipeline completo antes de cualquier push.

**2 — Vitest.** Los 11 escenarios sin etiqueta que `spec-coverage` reporta
UNBOUND. Ninguno puede nombrarse como uno de la 012: dos ya se renombraron por
esa colisión exacta y el conteo UNBOUND es el detector.

**3 — Unitarias.** Del lado del servicio, el invariante desde sus cuatro puertas.

**4 — Mutación (opt-in).** `backend/src/quaestor/services/recurring.py`, que
hasta hoy no estaba en la lista de ninguna feature — deuda que la 0052 dejó
anotada y que ésta paga. Comando:

```
cd backend && SESSION_SECRET=$(python3 -c "print('x'*64)") uv run pytest -q
```

El invariante es una comprobación **que tiene que poder fallar**: un mutante que
sobreviva dentro de él significa que no puede, y sería el hueco de plata de vuelta.

**5 — Navegador (CHARTER §6, y el `validation_method`).** Contra el sandbox, con
una cuenta en dólares, leyendo los saldos en centavos en vez de en pantalla, que
redondea.

**6 — La migración, sobre una copia restaurada** antes de tocar producción. Es
la mitad del `validation_method` que ninguna suite cubre.

## Deuda conocida que este plan deja abierta

- **La AC-21 no tiene escenario para una regla apagada.** La decisión de hoy
  —solo las encendidas muestran el precio— quedó sin pinear. Requiere permiso
  del dueño para tocar `spec.md`; pedido al presentar este plan.
- `id:rule-change-reaches-the-waiting-charge` sigue en el roadmap, sin empezar.

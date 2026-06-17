# Quaestor — P0 Core (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** —
**Parte de:** `2026-06-16-quaestor-general-design.md`

---

## Objetivo

Entregar la **fundación** del backend: el modelo de datos persistido, la aritmética de dinero/FX, las reglas de balance y los **services base** para operar cuentas, categorías, tags, tasas y transacciones (gasto/ingreso/transferencia). Frontera: **sin HTTP, sin MCP, sin UI** y sin lógica temporal (recurrentes, rollover, presupuestos, metas). Todo es invocable y testeable desde código puro.

## Alcance

**En:**
- `domain/models.py`: Account, Category, Transaction, Tag, TransactionTag, FxRate, Settings.
- `domain/money.py`: tipo `Money`, escala por moneda, conversión FX, formateo display.
- `domain/rules.py`: actualización incremental de balance en tx `posted`.
- `db.py`: engine SQLite, sesión, estrategia de migraciones.
- Services: `transactions.py`, `accounts.py`, `categories.py`, `tags.py`, `fx.py` + reads.

**Fuera:**
- RecurringItem, RecurringOccurrence, Budget, Goal, GoalContribution (los crean **P3/P4**).
- Semántica completa de `planned` / "Por pagar" y `cerrar_mes` (**P3**).
- API REST (**P1**), tools MCP (**P2**), reportes/importer (**P5**), frontend (**P6**).

## Aporte al modelo de datos

P0 crea **solo** estas entidades (resto en §5 del general, añadidas por otros sub-proyectos):

| Entidad | Campos clave |
|---|---|
| **Account** | `name`, `type` (debit/credit/cash/savings), `currency`, `balance` (centavos), `archived`. **Tarjeta de crédito** (`type=credit`): cuenta normal con saldo negativo = deuda; el pago del extracto es una `transfer` (débito → tarjeta), no un gasto (ADR-021) |
| **CategoryGroup** | `name`, `sort_order`, `archived` — contenedor de categorías; entidad propia (ADR-023) |
| **Category** | `name`, `group_id?` (FK CategoryGroup), `is_income`, `exclude_from_budget`, `exclude_from_totals`, `archived` |
| **Transaction** | `date`, `payee`, `notes`, `type` (expense/income/transfer), `status` (planned/posted), `amount` (centavos, moneda original), `currency`, `fx_rate`, `to_base` (centavos COP), `account_id`, `category_id?`, `transfer_group_id?`, `source` (manual/agent/import), `created_at` |
| **Tag** + **TransactionTag** | `name`; relación m2m |
| **FxRate** | `date`, `usd_cop` (tasa); único por fecha |
| **Settings** | `base_currency=COP`, `default_source_account_id?` (FK Account, cuenta origen global de aportes de meta — la usa P4, ADR-015), config de la app (fila singleton) |

> P0 incluye los campos `status` y `transfer_group_id` en Transaction, pero solo ejercita `status=posted` y los pares de transferencia. La semántica avanzada de `planned` (vencimiento, confirmación) la aterriza P3 sin redefinir el modelo.

## Componentes

- `src/quaestor/domain/models.py` — tablas SQLModel + enums (`AccountType`, `CategoryKind`, `TxType`, `TxStatus`, `Source`).
- `src/quaestor/domain/money.py` — `Money`, escalas, `to_base`, formateo.
- `src/quaestor/domain/rules.py` — `aplicar_a_balance`, `delta_balance`, signo por tipo.
- `src/quaestor/db.py` — `engine`, `get_session`, `init_db`, transacción atómica.
- `src/quaestor/services/{accounts,categories,tags,fx,transactions}.py` — casos de uso + reads.
- `tests/` — pytest sobre domain + services con SQLite in-memory.

## Interfaz pública (services)

```python
# accounts.py
crear_cuenta(name, type, currency, balance=0) -> Account
listar_cuentas(incluir_archivadas=False) -> list[Account]
consultar_cuenta(account_id) -> Account
archivar_cuenta(account_id) -> Account

# categories.py
crear_grupo(name, sort_order=0) -> CategoryGroup              # entidad de grupo (ADR-023)
listar_grupos(incluir_archivados=False) -> list[CategoryGroup]
crear_categoria(name, group_id=None, is_income=False, **flags) -> Category
listar_categorias(incluir_archivadas=False) -> list[Category]

# tags.py
crear_tag(name) -> Tag
listar_tags() -> list[Tag]
etiquetar(tx_id, tags: list[str]) -> Transaction   # crea tags faltantes (upsert)

# fx.py
fijar_tasa_fx(date, usd_cop) -> FxRate              # upsert por fecha
tasa_vigente(date) -> Decimal                       # última <= date; MissingRate si no hay

# transactions.py
registrar_gasto(account_id, amount, currency, date, payee, category_id=None,
                notes=None, source="manual", fx_rate=None) -> Transaction
registrar_ingreso(account_id, amount, currency, date, payee, category_id=None,
                  notes=None, source="manual", fx_rate=None) -> Transaction
transferir(from_account_id, to_account_id, amount, currency, date,
           notes=None, source="manual", fx_rate=None) -> tuple[Transaction, Transaction]
listar_transacciones(filtros...) -> list[Transaction]   # cuenta/categoría/tag/tipo/status/rango
consultar_transaccion(tx_id) -> Transaction
```

Toda escritura es **atómica** (commit/rollback). Los services nunca exponen la sesión; reciben/abren su propia unidad de trabajo.

## Lógica y reglas clave

- **Dinero = entero en centavos**, nunca float. `Money` envuelve `(centavos: int, currency)` y conoce la escala por moneda (COP y USD usan 2 decimales → escala 100).
- **Signo por `type`, no en el monto.** `amount` se almacena **siempre positivo**; el service aplica el signo: `expense` resta, `income` suma. `delta_balance` en `rules.py` centraliza esto.
- **FX congelado.** Si `currency != base (COP)`: `fx_rate` = el pasado o `tasa_vigente(date)`; `to_base = amount × fx_rate` se calcula y **se guarda fijo** al registrar. Tx en COP → `fx_rate=1`, `to_base=amount`. Cambiar la tasa después no altera tx ya guardadas. La tabla `FxRate` la **puebla un job diario** (P7, ADR-011) llamando a `fijar_tasa_fx`; este service queda además como **override manual**. `tasa_vigente` no cambia: lee la última ≤ fecha.
- **Balance incremental solo en `posted`.** Al registrar una tx `posted`, el service ajusta `Account.balance` con `delta_balance` (en moneda de la cuenta). Las tx `planned` **no tocan balance**. El balance no se recalcula desde cero.
- **Transferencia = par atómico.** `transferir` genera dos transactions con el mismo `transfer_group_id` y `type=transfer`: una resta en `from_account`, otra suma en `to_account`. Las dos se persisten o ninguna. Quedan **excluidas de ingreso/gasto** (marca consumible por reportes en P5).
- **Settings singleton.** Una sola fila; `base_currency=COP` fija la moneda de todos los `to_base`.

## Errores

`domain` lanza errores tipados (mapeables luego a 4xx en P1 / texto en P2):

- `ValidationError` — monto ≤ 0, moneda no soportada, cuenta/categoría inexistente o archivada, `type` inválido.
- `MissingRate` — tx no-COP sin `fx_rate` explícito y sin tasa vigente para la fecha. Mensaje accionable: "fija la tasa usd_cop para {date}".
- `TransferImbalance` — origen == destino, o el par no cuadra (no debe ocurrir; guarda de invariante).
- `NotFound` — id inexistente en reads/escrituras.

Transferencias y cualquier escritura multi-fila: **commit/rollback atómico**; un fallo deja la DB intacta.

## Testing y criterio de "listo"

`pytest` sobre `domain` + `services` con **SQLite in-memory** (fixture de sesión por test):

- Money/FX: escalas COP/USD, redondeo a centavos, `to_base` congelado tras cambiar la tasa.
- Balance: gasto resta, ingreso suma, monto siempre positivo; `posted` mueve balance.
- Transferencia: par con mismo `transfer_group_id`, origen−/destino+, **atómica** (fallo → ninguna fila).
- FX: `tasa_vigente` toma la última ≤ fecha; `MissingRate` cuando falta.
- Reads: filtros por cuenta/categoría/tag/tipo/status/rango.
- Validación: montos inválidos, moneda no soportada, ids inexistentes → error tipado.

**Listo cuando:** en código/tests se puede registrar gasto, ingreso y transferencia; los balances quedan correctos; el `to_base` USD está congelado; las transferencias son atómicas; y `init_db` levanta el esquema en in-memory.

## Integración con otros sub-proyectos

- **P1 (API)** y **P2 (MCP)** son adaptadores delgados sobre estos services; no tocan la DB directo ni añaden lógica.
- **P3 (Motor temporal)** añade RecurringItem/RecurringOccurrence y la semántica plena de `planned` (vencimiento, `confirmar_pago`, `cerrar_mes`) **reutilizando** `registrar_*`/`transferir` y el campo `status` ya definido aquí.
- **P4 (Presupuestos/Metas)** añade Budget (con rollover)/Goal/GoalContribution y la columna `goal_id?` en Transaction (migración propia), apoyándose en `to_base`, el flag de exclusión de categorías y `transferir` (aportes a meta, materializados al confirmar en "Por pagar").
- **P5 (Reportes/Importer)** lee transacciones, consume la marca de transferencia para excluirlas de ingreso/gasto y usa `to_base` para agregados; el importer llama a `registrar_*`.

**Convenciones transversales respetadas:** centavos `int`, agregados en `to_base` COP, signo por `type`, **solo `posted` cuenta**, transferencias atómicas. P0 no re-litiga estas reglas; las implementa.

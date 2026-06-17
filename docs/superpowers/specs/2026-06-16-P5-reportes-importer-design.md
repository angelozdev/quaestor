# Quaestor — P5 Reportes + Importer (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** P0 (core), P3 (motor temporal), P4 (presupuestos + metas).
**Se expone vía:** P1 (endpoints `/reports`, `/import`), P2 (tools MCP `reporte_mensual`, `importar_csv`), P6 (pantallas `/reports`, `/import`).
**Parte de:** `2026-06-16-quaestor-general-design.md` (reportes §9, importer §10, convenciones §5/§12).

---

## Objetivo

Dar dos capacidades de cierre del ciclo: **leer** el mes con un reporte mensual (markdown para el chat + datos estructurados para el frontend) y **cargar** historia/lotes con un importer CSV bulk atómico de formato propio. P5 es **agregación + formateo + ingesta**; no recalcula reglas ajenas: reutiliza los services de P0/P3/P4 para los números.

## Alcance

**Incluye**
- Service `reporte_mensual(mes) -> (datos, markdown)` con todas las secciones de §9.
- Service `importar_csv(contenido, dry_run=False) -> ResultadoImport` con validación fila por fila, atomicidad y reporte de errores con número de línea.
- Helpers de agregación reutilizables (gasto por categoría, neto, USD share, drift MoM).
- Contrato de datos (`ReporteMensual`, `ResultadoImport`) para wire en P1/P2 y pantallas P6.

**No incluye**
- Recalcular reglas de presupuesto/meta/rollover (vienen de P4/P3 ya calculadas).
- Gráficos HTML/PDF (v2; v1 es markdown + tablas).
- Migrador específico de Lunch Money (solo el CSV propio genérico).
- Wire físico de tools/endpoints/UI (lo hacen P1/P2/P6; P5 entrega el contrato).

## Aporte al modelo de datos

**Ninguna entidad nueva.** P5 sólo **lee** (Transaction, Account, Category, Budget, Goal, GoalContribution, RecurringOccurrence, FxRate) y **escribe Transaction/Tag/TransactionTag** vía los services de creación de P0 al importar. Las filas importadas se insertan con `source=import` y, si aplica, `status` por defecto `posted`. No define migraciones propias.

## Componentes

- `services/reports.py` — `reporte_mensual`, helpers de agregación.
- `services/importer.py` — `importar_csv`, parser y validación de filas.
- `domain/report_types.py` — dataclasses del contrato (`ReporteMensual`, `SeccionCategoria`, `LineaPresupuesto`, `LineaMeta`, `BalanceCuenta`, `DriftMoM`, `ResultadoImport`, `ErrorFila`).
- `domain/report_markdown.py` — renderer puro `datos -> str markdown` (sin I/O, testeable solo).
- Reúsa de P0: `transactions` (reads, `registrar_*`), `money`/`fx` (`to_base`, `tasa_vigente`), maestros (resolver cuenta/categoría por nombre). De P3: `por_pagar`, occurrences. De P4: `estado_presupuesto`, `progreso_metas`.

## Interfaz pública

```python
def reporte_mensual(mes: str) -> ReporteMensual            # mes = "YYYY-MM"; .markdown es atributo del resultado
def importar_csv(contenido: str, *, dry_run: bool = False) -> ResultadoImport
```

```python
@dataclass
class ReporteMensual:
    mes: str
    ingreso: int; gasto: int; neto: int                    # centavos COP, solo posted
    por_categoria: list[SeccionCategoria]                  # (categoria, group_name, total, pct)
    presupuestos: list[LineaPresupuesto]                   # (categoria, presupuesto, real, pct, estado)
    metas: list[LineaMeta]                                 # (nombre, acumulado, target?, eta?, on_track?)
    balances: list[BalanceCuenta]                          # (cuenta, currency, balance)
    drift_mom: DriftMoM                                    # gasto/ingreso/neto vs mes anterior (abs + %)
    usd_share: float                                       # % del gasto del mes originado en USD
    pendientes: list[str]                                  # líneas de alerta: manuales sin confirmar
    markdown: str

@dataclass
class ResultadoImport:
    ok: bool
    insertadas: int                                        # 0 si !ok o dry_run
    tags_creados: list[str]
    errores: list[ErrorFila]                               # ErrorFila(linea: int, motivo: str)
    dry_run: bool
```

**Formato CSV propio** (cabecera obligatoria, exacta):
```
date,type,payee,amount,currency,account,category,tags,notes
```

| Columna | Significado / contrato |
|---|---|
| `date` | `YYYY-MM-DD`. Inválida → error con línea. |
| `type` | ∈ `expense` / `income` / `transfer`. Otro → error. |
| `payee` | texto libre; opcional. |
| `amount` | número en la **moneda original**, positivo (signo lo da `type`). ≤0 o no-numérico → error. |
| `currency` | `COP` / `USD`. Debe existir tasa vigente si `USD` → si no, error (`MissingRate`). |
| `account` | **nombre** de Account existente (no archivada). No existe → error con línea. |
| `category` | **nombre** de Category existente. No existe → error con línea (vacía permitida sólo si `type=transfer`). |
| `tags` | lista separada por `;`; **se auto-crean** si no existen. |
| `notes` | texto libre; opcional. |

## Lógica y reglas clave

**Reportes**
- **Solo `posted`** en todo agregado/balance (convención §5). `planned` nunca suma a ingreso/gasto/neto.
- Todo número en **`to_base` (COP)** ya congelado en cada tx; el reporte **no reconvierte** FX.
- **Transferencias excluidas** de ingreso/gasto/por-categoría (igual que en §5). Sí afectan balances de cuenta.
- Respeta `exclude_from_totals` / `exclude_from_budget` al agregar (lo aplica el helper de categoría/presupuesto, alineado con P4).
- `por_categoria`: agrupa expenses posted del mes por categoría, ordena desc, `pct` sobre gasto total.
- **Drift MoM**: compara ingreso/gasto/neto del mes vs el mes calendario anterior (abs y %); si no hay datos previos, `pct=None`.
- **USD share**: `Σ to_base(expenses posted del mes con currency=USD) / gasto total`. Si gasto=0 → `0.0`.
- **Presupuestos / metas**: se piden a `estado_presupuesto` y `progreso_metas` (P4); P5 sólo los formatea. ETA/on-track sólo en metas **definidas** (las indefinidas muestran sólo acumulado).
- **Pendientes**: si `por_pagar` (P3) reporta recurrentes manuales del mes sin confirmar, emite línea de alerta (cuenta + total estimado).
- `markdown` se genera con el renderer puro a partir de `datos`; las dos vistas (chat MCP / frontend P6) consumen el mismo objeto.

**Importer**
- **Atómico (todo o nada):** parsea y valida las N filas en memoria; **si una sola falla, no inserta ninguna** y devuelve `ok=False` con todos los `errores`. Sólo si 0 errores abre una transacción DB y la confirma (commit) o revierte (rollback) en bloque.
- **Validación fila por fila** acumulando errores (no aborta al primero) → el usuario ve todos los problemas de una.
- Resuelve `account`/`category` por **nombre** vía maestros de P0; **tags se auto-crean** (registrados en `tags_creados`).
- Calcula `to_base` con **`tasa_vigente`** de la fecha de la fila (FX de P0); USD sin tasa → error de esa línea.
- Inserta vía services de P0 (`registrar_gasto/ingreso/transferir`) → reusa signo-por-`type`, balance y atomicidad ya probados. `source=import`.
- **`dry_run=True`**: ejecuta todo el pipeline de validación (incl. resolución de nombres y tasas) y **no inserta**; alimenta la validación previa de la pantalla `/import` y la tool.
- Cabecera ausente/distinta o CSV vacío → error global (línea 0/1), no se importa nada.

## Errores

- Errores de fila se acumulan en `ResultadoImport.errores` como `ErrorFila(linea, motivo)` — **no** se lanzan; permiten el reporte completo.
- Errores tipados de `domain` que sí se propagan en reportes: `MissingRate` (FX faltante al agregar USD si hiciera falta), `ValidationError` (mes mal formado). API (P1) los mapea a 4xx; MCP (P2) los devuelve como texto estructurado.
- Importer: `MissingRate` por fila → motivo "sin tasa usd_cop para `<fecha>`". Nombre inexistente → "cuenta/categoría `<n>` no existe". `type`/`amount`/`date` inválidos → motivo específico con la línea.
- Cualquier fallo en el commit (improbable, ya validado) → rollback total y `ok=False`.

## Testing y criterio de "listo"

`pytest` sobre `services` + renderer con SQLite in-memory.

**Reportes**
- Agregados correctos: ingreso/gasto/neto sólo con `posted`; `planned` y `transfer` excluidos de ingreso/gasto.
- Por categoría ordenado y con `pct` correcto; respeta `exclude_*`.
- **Drift MoM** con y sin mes anterior; **USD share** correcto y `0.0` si gasto 0.
- Presupuestos/metas formateados desde P4 (definida con ETA, indefinida sin ETA).
- Línea de pendientes aparece sólo si hay manuales sin confirmar.
- Renderer markdown determinista para un `ReporteMensual` dado.

**Importer**
- Validación: filas malas (date/type/amount/currency) reportan línea + motivo correctos.
- **Atomicidad**: una fila inválida ⇒ **0 insertadas**, DB intacta.
- Mapeo de nombres: cuenta/categoría por nombre resueltos; inexistente ⇒ error con línea.
- Tags: auto-creación y reporte en `tags_creados`.
- `to_base` con tasa vigente; `source=import` en todas.
- `dry_run` valida sin insertar (insertadas=0, errores poblados igual).

**Listo cuando:** todos los tests verdes; `reporte_mensual` e `importar_csv` con sus contratos estables; renderer puro sin I/O; documentado el formato CSV. Wire de tools (P2), endpoints (P1) y contrato de pantallas `/reports` y `/import` (P6) referenciados y disponibles.

## Integración con otros sub-proyectos

- **P0**: consume reads de transactions, `money`/`fx` (`to_base`, `tasa_vigente`), maestros (resolver por nombre) y `registrar_*` para insertar el import. No toca DB directo (regla de oro §3).
- **P3**: `reporte_mensual` lee `por_pagar`/occurrences para la línea de pendientes; no dispara rollover.
- **P4**: toma `estado_presupuesto` y `progreso_metas` ya calculados; P5 sólo formatea.
- **P1**: expone `GET /reports?mes=YYYY-MM` (devuelve datos + markdown) y `POST /import` (body CSV, `?dry_run`); espejo directo de los services.
- **P2**: tools MCP `reporte_mensual` (muestra `.markdown` en el chat) e `importar_csv` (acepta dry-run); adaptadores delgados 1:1.
- **P6**: pantalla `/reports` renderiza datos + markdown con selector de mes; `/import` sube CSV, muestra validación previa (dry-run) y errores con línea antes de confirmar.

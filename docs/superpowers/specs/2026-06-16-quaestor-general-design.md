# Quaestor — Diseño General (paraguas)

> *Quaestor*: el magistrado romano a cargo del tesoro. Le hablas a tu Quaestor para registrar, consultar y planear tu plata.

**Fecha:** 2026-06-16
**Estado:** diseño aprobado, pendiente plan de implementación
**Autor:** angelozam17 (+ asistente)

Este es el **diseño general**. Fija lo transversal (objetivo, arquitectura, modelo de datos, convenciones de dinero, auth, despliegue) y descompone el sistema en **8 sub-proyectos**, cada uno con su propio design. Ver [§12 Sub-proyectos](#12-sub-proyectos).

Sub-specs (en esta misma carpeta):
- `2026-06-16-P0-core-design.md`
- `2026-06-16-P1-api-auth-design.md`
- `2026-06-16-P2-mcp-design.md`
- `2026-06-16-P3-motor-temporal-design.md`
- `2026-06-16-P4-presupuestos-metas-design.md`
- `2026-06-16-P5-reportes-importer-design.md`
- `2026-06-16-P6-frontend-design.md`
- `2026-06-16-P7-despliegue-design.md`

---

## 1. Objetivo y contexto

Sistema personal de finanzas, **single-user**, que reemplaza a Lunch Money como sistema de registro propio. Cubre gastos, ingresos, recurrentes (auto y manual), transferencias, presupuestos, metas de ahorro y reportes mensuales.

Dos formas de interactuar:
- **Lenguaje natural** vía un **MCP server** (hoy Claude Code; mañana MiniMax u otro cliente MCP). El backend es LLM-agnóstico.
- **Frontend web** para CRUD completo + dashboards.

**Hoy** el usuario usa Claude Code + API key de Lunch Money ("solo el backend"). Quaestor recrea ese flujo —hablarle a un agente que escribe en un backend— pero sobre **base de datos propia**, desplegable en un VPS.

**Dolores que resuelve explícitamente:**
1. No saber **qué le falta por pagar** en un punto de la semana → vista "Por pagar".
2. Querer **ahorrar mes a mes** hacia una meta (viaje, tecnología) → metas con aporte mensual fijo.
3. Querer **reportes mensuales** sin abrir una UI ajena → reporte markdown en el chat + frontend.

### Fuera de alcance (v1)
- Multi-usuario, roles, compartir.
- Reportes con gráficos HTML/PDF (v2; v1 es markdown + tablas).
- Reglas de meta por % de ingreso (v1 solo **monto fijo**).
- Sync automático con bancos / Plaid.
- Migrador específico de Lunch Money (se arranca de cero + importer CSV genérico).

---

## 2. Decisiones cerradas

| Tema | Decisión |
|---|---|
| Relación con LM | Proyecto **nuevo y standalone**. No depende de LM ni del proyecto `my_finances`. |
| Capa AI | **MCP server** sobre DB propia. LLM-agnóstico (Claude Code hoy, MiniMax luego). |
| Stack backend | Python 3.12 · FastAPI · SQLModel (SQLAlchemy+Pydantic) · SDK oficial MCP · uv |
| Storage | **SQLite** (single-user, un archivo). Migrable a Postgres por connection string si hiciera falta. |
| Frontend | **Next.js** (App Router) · TypeScript · Tailwind · shadcn/ui |
| Fidelidad de datos | Completa: multi-moneda COP+USD, multi-cuenta+balances, transferencias internas, tags, presupuestos, recurrentes, metas |
| Arranque de datos | DB **desde cero** + **importer CSV bulk** (formato propio documentado) |
| Metas | Solo **monto fijo mensual**; meta **definida** (target+deadline) o **indefinida** |
| Recurrentes | Gasto **e** ingreso; modo **auto** y **manual** |
| Pagos futuros | `Transaction.status` ∈ `planned`/`posted`; vista "Por pagar" |
| Reportes | **Markdown en el chat** (MCP) + render en frontend |
| Despliegue | **VPS self-hosted**, Docker Compose detrás de **Caddy** (HTTPS auto) |
| Auth | Single-user: contraseña → sesión (frontend) + bearer token (`APP_TOKEN`) para API y MCP |

---

## 3. Arquitectura

Un solo SQLite como fuente de verdad. Core compartido (`domain` + `services`); dos adaptadores (MCP, HTTP API); un frontend.

```
        ┌───────────── domain (modelos + cálculos, puro) ─────────────┐
        │                    services (casos de uso)                   │
        └──────────────────────────┬───────────────────────────┬──────┘
                                    │                           │
                          MCP server (NL/agente)        HTTP API (FastAPI)
                                                                │
                                                          Frontend web (CRUD + reportes)
```

**Regla de oro:** API y MCP **nunca** tocan la DB directo. Ambos llaman a `services`. Toda la lógica (validar, convertir FX, cuadrar transferencias, calcular meta, rollover) vive en `services`/`domain` → testeable sin HTTP ni MCP, sin duplicar.

### Estructura del repo (monorepo)

```
quaestor/
├── backend/
│   ├── pyproject.toml            # uv, Python 3.12
│   ├── quaestor.db               # SQLite (gitignored)
│   ├── src/quaestor/
│   │   ├── domain/
│   │   │   ├── models.py         # SQLModel: Account, Category, Transaction...
│   │   │   ├── money.py          # Money (centavos, int), conversión FX
│   │   │   └── rules.py          # cálculo metas, presupuesto vs real, rollover
│   │   ├── db.py                 # engine SQLite, session, migraciones
│   │   ├── services/
│   │   │   ├── transactions.py   # registrar_gasto, registrar_ingreso, transferir
│   │   │   ├── planned.py        # planear_pago, confirmar_pago, por_pagar
│   │   │   ├── recurring.py      # crear_recurrente, listar
│   │   │   ├── budgets.py        # fijar_presupuesto, estado_presupuesto
│   │   │   ├── goals.py          # crear_meta, aporte, progreso
│   │   │   ├── rollover.py       # cerrar_mes
│   │   │   ├── reports.py        # reporte_mensual -> (datos, markdown)
│   │   │   ├── fx.py             # fijar_tasa, tasa_vigente
│   │   │   └── importer.py       # bulk CSV
│   │   ├── api/                  # FastAPI: routers REST sobre services
│   │   └── mcp/                  # MCP server: tools sobre services
│   └── tests/                    # pytest sobre domain + services
├── frontend/                     # Next.js (App Router, TS, Tailwind, shadcn/ui)
│   ├── app/                      # /transactions /por-pagar /budgets /goals /reports ...
│   └── lib/api.ts                # cliente tipado de la API
├── docker-compose.yml            # api · mcp · frontend · caddy
├── Caddyfile
└── docs/superpowers/specs/       # este documento
```

### Cómo corre (local dev)
- `uv run uvicorn quaestor.api:app` → API en `:8000`
- `uv run python -m quaestor.mcp` → MCP server
- `npm run dev` en `frontend/` → UI en `:3000`, pega a `:8000`
- Los tres comparten el mismo `quaestor.db`.

---

## 4. Despliegue y auth

Vive en un **VPS** con dominio + HTTPS. Nada corre en la laptop salvo el browser y el cliente MCP (Claude Code) apuntando a una URL remota.

```
   VPS (dominio, HTTPS)
   ┌─────────────────────────────────────────────┐
   │  Caddy (reverse proxy + HTTPS auto)          │
   │    ├── quaestor.tudominio.com     → Frontend │
   │    ├── /api/*                     → FastAPI  │
   │    └── /mcp                       → MCP (HTTP)│
   │  ─────────────────────────────────────────── │
   │  services + domain  →  quaestor.db (volumen) │
   └─────────────────────────────────────────────┘
        ▲                         ▲
        │ browser (login)         │ Claude Code / MiniMax
     laptop                    (URL MCP remota + token)
```

- **MCP remoto, no stdio local.** El MCP server se expone vía transporte **streamable-HTTP** del SDK oficial, en `/mcp`, protegido por token. Claude Code se conecta a la URL remota con header de auth. (Se descarta el shim stdio local porque obligaría a tener algo corriendo en la laptop.)
- **Auth:**
  - Frontend: una **contraseña** → cookie de sesión. Sin registro ni usuarios.
  - API y MCP: **bearer token estático** (`APP_TOKEN` en env). El frontend lo usa vía sesión; Claude Code lo manda en el header.
  - Todo detrás de HTTPS (Caddy saca y renueva cert solo).
- **Despliegue:** `docker-compose.yml` con servicios `api`, `mcp`, `frontend`, `caddy`. `quaestor.db` en **volumen persistente**. Deploy = `git pull && docker compose up -d --build`.
- **Backups:** **Litestream** replica el `.db` en continuo a un bucket (S3/R2/Backblaze). Mínimo aceptable: cron `sqlite3 .backup` diario.

---

## 5. Modelo de datos

Montos = **enteros en centavos**, nunca float. Moneda base = **COP**.

| Entidad | Campos clave |
|---|---|
| **Account** | `name`, `type` (debit/credit/cash/savings), `currency`, `balance` (centavos), `archived` |
| **Category** | `name`, `group_name`, `is_income`, `exclude_from_budget`, `exclude_from_totals`, `archived` |
| **Transaction** | `date`, `payee`, `notes`, `type` (expense/income/transfer), `status` (planned/posted), `amount` (centavos, moneda original), `currency`, `fx_rate`, `to_base` (centavos COP), `account_id`, `category_id`, `recurring_id?`, `transfer_group_id?`, `source` (manual/agent/import), `created_at` |
| **Tag** + **TransactionTag** | `name`; relación m2m |
| **RecurringItem** | `name`, `payee`, `type` (expense/income), `mode` (auto/manual), `amount` (default), `currency`, `category_id`, `account_id`, `frequency` (monthly/weekly/biweekly/yearly), `due_day`, `start_date`, `end_date?`, `active` |
| **RecurringOccurrence** | `recurring_id`, `period` (YYYY-MM), `status` (posted/planned/skipped), `transaction_id?`, `created_at` — marca de idempotencia del rollover |
| **Budget** | `category_id`, `year_month` (YYYY-MM), `amount_base` (centavos COP) |
| **Goal** | `name`, `target_amount?` (COP), `deadline?`, `monthly_amount` (COP, fijo), `savings_account_id`, `status` (active/reached/paused) |
| **GoalContribution** | `goal_id`, `date`, `amount`, `source` (auto/manual), `transaction_id?` |
| **FxRate** | `date`, `usd_cop` (tasa) |
| **Settings** | `base_currency=COP`, config de la app |

### Reglas de dinero / FX / signo (en `domain`)
- **Signo explícito por `type`**, no signo en el monto. `amount` siempre positivo; el service sabe que expense resta y income suma. Evita la confusión de signos de LM.
- **Todo agregado usa `to_base` (COP).** Tx en USD calcula `to_base = amount × fx_rate` al registrar y lo **congela** → reportes históricos estables aunque cambie la tasa.
- **Balance de cuenta** lo actualiza el service en cada tx `posted` (no se recalcula desde cero).
- FX sin tasa para la fecha → error claro "fija la tasa usd_cop" (o usa última vigente, configurable).

### Transferencias internas
Par de transactions con mismo `transfer_group_id`, `type=transfer` → una resta en cuenta origen, otra suma en destino. **Excluidas de ingreso/gasto** en todo reporte. El service las crea **atómicas** (las dos o ninguna).

### Estados de transacción: `planned` vs `posted`
- `posted` = ocurrió de verdad (default al registrar). Afecta balance y reportes.
- `planned` = obligación futura. **No toca balance ni totales** hasta confirmarse. Tiene fecha de vencimiento.
- **Regla firme:** todo agregado/balance/reporte cuenta **solo `posted`**.

---

## 6. Lógica temporal

### `cerrar_mes(YYYY-MM)` — idempotente
1. **Recurrentes:** por cada `RecurringItem` activo que toca el periodo y no tiene `RecurringOccurrence`:
   - `mode=auto` → postea transaction `posted` con el monto definido; occurrence `status=posted`.
   - `mode=manual` → crea transaction **`planned`** (con `due_day`) **sin afectar balance**; occurrence `status=planned`. Aparece en "Por pagar".
2. **Metas:** por cada `Goal` activa → crea `GoalContribution` por `monthly_amount` + transfer a `savings_account_id`.
3. Re-ejecutar no duplica (la occurrence ya existe).

### Recurrentes (gasto/ingreso, auto/manual)
- `type` distingue gasto (renta, subs, Netflix) de ingreso (sueldo, freelance fijo).
- `mode=auto` → se postea solo en el rollover.
- `mode=manual` → cae como `planned`; lo confirmas con el monto real (útil para variables: luz, agua, tarjeta).

### Pagos futuros / "Por pagar"
- `por_pagar(desde, hasta)` → lista de transactions `planned` en la ventana + total. Resuelve "¿qué me falta por pagar esta semana?".
- `confirmar_pago(tx_id, amount?, date?)` → `planned` → `posted` (ajustas monto real).
- `planear_pago(...)` → pago suelto futuro (ej. "le debo a un amigo el viernes"), sin recurrente.

### Metas (monto fijo)
| Tipo | `target_amount` | `deadline` | `monthly_amount` | Cálculo |
|---|---|---|---|---|
| **Definida** | sí | sí | sí | aporte fijo + **on-track/atrasado + ETA** vs deadline (compara requerido `(target−ahorrado)/meses` contra el monto fijo) |
| **Indefinida** | no | no | sí | solo acumula el monto fijo; **sin ETA ni requerido**, solo total ahorrado |

`aporte_meta(goal_id, amount, date)` permite aportes manuales además del automático del rollover.

### Presupuesto
`estado_presupuesto(categoría, mes)` = `Σ to_base(expense de esa cat, ese mes, posted, respetando exclude_flags)` vs `Budget.amount_base` → % usado, restante, over/under.

---

## 7. Services, MCP y API

### Capa `services` (el cerebro)
`registrar_gasto · registrar_ingreso · transferir · planear_pago · confirmar_pago · por_pagar · crear_recurrente · listar_recurrentes · fijar_presupuesto · estado_presupuesto · crear_meta · aporte_meta · progreso_metas · fijar_tasa_fx · cerrar_mes · reporte_mensual · importar_csv` + reads (listar/consultar).

### Tools MCP
1 tool = 1 service (adaptador delgado). Mismos verbos. El agente registra, consulta, cierra mes, pregunta "¿qué me falta por pagar?", pide reporte — todo en lenguaje natural → tool → service.

### HTTP API (FastAPI)
Routers REST espejo de services: `/transactions /accounts /categories /tags /recurring /budgets /goals /planned /reports /import /fx /rollover /settings`. Mismos services, cero lógica duplicada.

---

## 8. Frontend (Next.js)

| Ruta | Qué hace |
|---|---|
| `/` **Dashboard** | ingreso vs gasto del mes + neto · **widget "Por pagar"** (esta semana / este mes + total + marcar pagado) · avance de metas · balances · presupuestos en riesgo |
| `/transactions` | CRUD completo, tabla filtrable (fecha/cuenta/categoría/tag/tipo/status) |
| `/por-pagar` | lista de `planned`, confirmar pago (monto real), planear pago suelto |
| `/recurring` | CRUD recurrentes (type, mode auto/manual, frequency+due_day) |
| `/budgets` | fijar presupuesto categoría×mes, estado vs real |
| `/goals` | CRUD metas (definida/indefinida), progreso/ETA, aporte manual |
| `/accounts` · `/categories` · `/tags` | CRUD maestros + flags + balances |
| `/reports` | reporte mensual (render markdown + tablas), selector de mes |
| `/import` | subir CSV bulk |
| `/settings` | moneda base, tasa FX (usd_cop), contraseña |

---

## 9. Reportes

`reporte_mensual(mes)` devuelve `(datos estructurados, markdown)`. MCP muestra el markdown en el chat; frontend renderiza datos + markdown.

**Contenido:** ingreso / gasto / neto · por categoría · presupuesto vs real · metas (acumulado + ETA en las definidas) · balances de cuentas · drift MoM · USD share · **recurrentes / pagos pendientes** (línea de alerta si hay manuales sin confirmar).

---

## 10. Importer CSV bulk

Formato propio documentado:

```
date,type,payee,amount,currency,account,category,tags,notes
```

- Valida fila por fila; reporta errores con número de línea.
- Transacción atómica: todo o nada.
- Expuesto como tool MCP (`importar_csv`) y pantalla `/import`.

---

## 11. Errores y testing

### Errores
- `domain` lanza errores tipados (`ValidationError`, `MissingRate`, `TransferImbalance`...). API los mapea a 4xx; MCP los devuelve como texto estructurado que el agente explica.
- Transferencias y rollover: **atómicos** (commit/rollback). Rollover **idempotente**.

### Testing
- `pytest` sobre `domain` + `services` con SQLite in-memory: dinero/FX, cálculo de meta (definida/indefinida), estado de presupuesto, **idempotencia del rollover**, cuadre de transferencias, `planned` no afecta balance, confirmar pago, importer.
- API: `TestClient` happy-path + validación.
- Frontend v1: prueba manual; tests de componentes después.

---

## 12. Sub-proyectos

El sistema se construye como **8 sub-proyectos**, cada uno con su propio design en esta carpeta. Cada uno tiene un propósito claro, una interfaz bien definida, y se entiende/testea de forma aislada.

| # | Proyecto | Qué incluye | Depende de | Spec |
|---|---|---|---|---|
| **P0** | **Core** | domain (models, money/FX, rules), db/SQLite, services base: accounts, categories, transactions, transfers | — | `…-P0-core-design.md` |
| **P1** | **HTTP API + Auth** | FastAPI REST espejo de services, token `APP_TOKEN`, contrato para el frontend | P0 | `…-P1-api-auth-design.md` |
| **P2** | **MCP server** | transporte remoto streamable-HTTP, auth, tools sobre services (interfaz en lenguaje natural) | P0 | `…-P2-mcp-design.md` |
| **P3** | **Motor temporal** | recurrentes (auto/manual), `planned`/Por-pagar, `cerrar_mes` (rollover) | P0 | `…-P3-motor-temporal-design.md` |
| **P4** | **Presupuestos + Metas** | budgets categoría×mes, metas (definida/indefinida, monto fijo) | P0 | `…-P4-presupuestos-metas-design.md` |
| **P5** | **Reportes + Importer** | `reporte_mensual` (markdown), importer CSV bulk | P0, P3, P4 | `…-P5-reportes-importer-design.md` |
| **P6** | **Frontend** | Next.js: dashboard, Por-pagar, CRUDs, reportes | P1 | `…-P6-frontend-design.md` |
| **P7** | **Despliegue** | Docker Compose, Caddy, Litestream, VPS | todos | `…-P7-despliegue-design.md` |

**Orden de build:** `P0 → (P1 ∥ P2) → P3 → P4 → P5 → P6 → P7`.
El frontend (P6) puede arrancar apenas exista el contrato de P1 y crecer feature por feature conforme aterrizan P3/P4/P5.

**Cómo se reparte el modelo de datos** (definido completo en §5): P0 crea Account, Category, Transaction (con `status`), Tag, FxRate, Settings. P3 agrega RecurringItem, RecurringOccurrence y la semántica `planned`. P4 agrega Budget, Goal, GoalContribution. Cada sub-proyecto añade sus migraciones; ninguno redefine lo de otro.

**Convenciones transversales que todos respetan:** dinero en centavos (int), agregados en `to_base` COP, signo por `type`, **solo `posted` cuenta** en balances/reportes, transferencias y rollover atómicos e idempotentes. Cada sub-spec asume estas reglas; no las re-litiga.

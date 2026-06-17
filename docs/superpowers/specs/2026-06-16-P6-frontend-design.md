# Quaestor — P6 Frontend (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** P1 (contrato de la HTTP API + auth por sesión). Crece feature por feature conforme aterrizan P3 (recurrentes/Por-pagar), P4 (presupuestos/metas) y P5 (reportes/importer).
**Parte de:** `2026-06-16-quaestor-general-design.md` (frontend §8, auth §4, convenciones §12).

---

## Objetivo

**MCP-first (ADR-008):** el driver del producto es agent-native; el registro/CRUD del día a día se hace **hablándole al agente**. El frontend de **v1 es mínimo** y cubre solo lo que el chat hace mal: **revisar de un vistazo**. Dos vistas:
1. **Dashboard** con el **safe-to-spend** del mes y el widget **"Por pagar"** ("¿qué me falta por pagar esta semana?" + marcar pagado en un clic) — el dolor principal.
2. **Reporte mensual** (markdown + tablas).

El resto de pantallas (CRUD completo de todas las entidades) queda **documentado como backlog**: la tabla de *Interfaz pública* describe el destino completo, pero v1 entrega solo las dos vistas de arriba. El frontend sigue siendo un **cliente delgado de la API de P1**: cero lógica de negocio.

El frontend es un **cliente delgado de la API de P1**. No tiene lógica de negocio: validar, convertir FX, cuadrar transferencias, calcular metas, rollover — todo vive en `services` (backend) y se consume vía HTTP.

## Alcance

- **Stack:** Next.js (App Router) · TypeScript · Tailwind · shadcn/ui. SPA autenticada que pega a la HTTP API de P1.
- **Auth:** página de login (contraseña → cookie de sesión vía `/auth/login` de P1), guard de rutas, logout.
- **`lib/api.ts`:** cliente tipado de la API (un método por endpoint) + tipos espejo del contrato de P1.
- **Pantallas v1:** login, **dashboard** (safe-to-spend + Por-pagar), **reports**. (detalle en *Interfaz pública*).
- **Pantallas backlog:** transactions, por-pagar (vista dedicada), recurring, budgets, goals, accounts, categories, tags, import, settings — se construyen feature por feature después de v1; mientras tanto se operan por agente (MCP).
- **Formato de dinero:** todo monto que llega es **centavos (int)**; el frontend lo formatea a display por moneda. Nunca opera aritmética de negocio sobre montos.

**Fuera de alcance (v1):** todo el CRUD por UI (es backlog, se hace por agente — ADR-008); lógica de cálculo (vive en backend); tests automáticos de UI en v1 (prueba manual; tests de componentes después, §11 general); gráficos PDF/HTML (v2); PWA/offline; i18n más allá de es-CO.

## Aporte al modelo de datos

**Ninguno.** P6 no crea ni migra entidades. Consume exclusivamente el contrato REST de P1 (que a su vez espeja `services` sobre el modelo de §5). Los "tipos" que define `lib/api.ts` son representaciones TypeScript del JSON del API, no tablas: viven en el cliente y se actualizan cuando cambia el contrato, sin tocar la DB.

## Componentes

Organización en `frontend/`:

```
app/
  (auth)/login/page.tsx          # única ruta pública
  (app)/                          # layout con guard + nav; todo lo demás cuelga aquí
    layout.tsx  page.tsx          # shell + Dashboard (/)
    transactions/ por-pagar/ recurring/ budgets/ goals/
    accounts/ categories/ tags/ reports/ import/ settings/
  api/session/route.ts            # route handler: set/clear cookie httpOnly tras login/logout
lib/
  api.ts                          # cliente tipado (fetch + tipos del contrato P1)
  money.ts                        # formatCents(cents, currency) -> "$ 1.234.567" / "US$ 12.34"
  query.ts                        # QueryClient + keys
components/
  ui/                             # shadcn/ui (button, dialog, table, select, toast...)
  money-amount.tsx                # render de monto con signo por type y color
  data-table.tsx                  # tabla genérica filtrable/paginada (transactions, listas)
  por-pagar-widget.tsx            # toggle semana/mes + total + marcar pagado (reusado en / y /por-pagar)
  entity-form-dialog.tsx          # form CRUD reusable (account/category/tag/recurring/budget/goal)
  month-picker.tsx                # selector YYYY-MM (reports, budgets)
  empty-state.tsx  error-state.tsx  page-header.tsx
```

- **`MoneyAmount`** y **`money.ts`**: punto único de formateo centavos→display; expense en rojo, income en verde, signo derivado de `type` (no del monto, que siempre es positivo — convención §5).
- **`DataTable`**: encapsula filtros, orden y paginación; configurable por columnas. La página solo aporta el fetch y las columnas.
- **`PorPagarWidget`**: el componente estrella; compartido entre Dashboard y `/por-pagar`.
- **`EntityFormDialog`**: un solo patrón de modal CRUD parametrizado por schema, evita 8 formularios casi iguales.

## Interfaz pública (pantallas / rutas)

> **v1** = `/login`, `/` Dashboard, `/reports`. Todo lo demás es **backlog** (ADR-008): destino completo, no v1.

| Ruta | v1? | Qué hace | Endpoints P1 |
|---|---|---|---|
| `/login` | **v1** | contraseña → sesión; redirige a `/` | `POST /auth/login` |
| `/` **Dashboard** | **v1** | **safe-to-spend del mes** · **widget Por pagar** (toggle esta-semana/este-mes + total + marcar pagado) · ingreso/gasto/neto · avance de metas · balances · sobres en riesgo | `/reports?month`, `/budgets/safe-to-spend`, `/planned`, `/goals`, `/accounts`, `/budgets` |
| `/reports` | **v1** | reporte mensual: render markdown + tablas (incl. safe-to-spend + sobres); **selector de mes** | `GET /reports?month` |
| `/transactions` | backlog | CRUD completo; tabla filtrable por fecha/cuenta/categoría/tag/tipo/status | `GET/POST/PATCH/DELETE /transactions` |
| `/por-pagar` | backlog | lista de `planned`; **confirmar pago** (monto real, fecha) y **planear pago suelto** | `GET /planned`, `POST /planned/{id}/confirm`, `POST /planned` |
| `/recurring` | backlog | CRUD recurrentes (type, mode auto/manual, frequency + due_day) | `…/recurring` |
| `/budgets` | backlog | asignar sobres categoría×mes; estado con rollover; safe-to-spend | `GET/PUT /budgets`, `GET /budgets/status?month`, `GET /budgets/safe-to-spend?month` |
| `/goals` | backlog | CRUD metas (definida/indefinida), progreso + ETA, **aporte manual** (el mensual se confirma en Por-pagar) | `…/goals`, `POST /goals/{id}/contribute` |
| `/accounts` `/categories` `/tags` | backlog | CRUD maestros + flags (archived, is_income, exclude_*) + balances | `…/accounts` `…/categories` `…/tags` |
| `/import` | backlog | subir CSV bulk; muestra **errores por línea** del validador de P5 | `POST /import` (multipart) |
| `/settings` | backlog | moneda base, **tasa FX usd_cop** (auto-fetch + override manual), cambiar contraseña | `…/settings`, `…/fx`, `POST /auth/change-password` |

Toda ruta salvo `/login` exige sesión: sin cookie válida → redirect a `/login`.

## Lógica y reglas clave

- **Cero lógica de negocio en el cliente.** El frontend orquesta fetch + render + formato. Cualquier cálculo (neto, % de presupuesto, ETA de meta, total por pagar) llega ya resuelto del API; el frontend lo muestra, no lo recomputa.
- **Data fetching — recomendación: React Query (TanStack Query).** Justificación: la app es una **SPA muy interactiva, single-user, mutación-pesada** (marcar pagado, confirmar, CRUD constante) donde importan cache, invalidación y *optimistic updates* — fortalezas de React Query que los Server Components no cubren bien. RSC brilla para páginas mayormente estáticas con render en servidor; aquí casi todo es interacción post-login tras un guard de sesión, así que el server-render aporta poco y complica el manejo de la cookie de sesión hacia el API. Las páginas son Client Components que consumen `lib/api.ts` vía hooks de React Query; la sesión se setea con un route handler (cookie httpOnly).
- **Auth flow:** `/login` postea la contraseña → P1 responde sesión → un route handler guarda la cookie **httpOnly**; el guard del layout `(app)` valida en cada navegación. Logout limpia cookie y cache de React Query. El token `APP_TOKEN` nunca toca el cliente: el browser maneja sesión, el route handler intermedia con el API.
- **Dinero:** `formatCents` formatea por moneda (COP sin decimales y miles con punto; USD con `US$` y 2 decimales). Montos USD muestran también su `to_base` (COP) cuando el contexto es agregado, ya congelado por el backend.
- **`planned` vs `posted`:** la UI los distingue visualmente (badge); marcar pagado/confirmar dispara la mutación e invalida las queries de Por-pagar, dashboard y balances.
- **Invalidación:** cada mutación invalida sus query keys relacionadas (ej. confirmar pago → `planned`, `dashboard`, `accounts`) para reflejar balances al instante.
- **Orden de construcción:** **v1 = Dashboard (safe-to-spend + Por-pagar) + Reports** (las dos vistas que el chat hace mal). Backlog después: CRUDs (transactions, masters, recurring, budgets, goals) e import — feature por feature, operados por agente mientras tanto.

## Errores

- **Errores del API:** P1 mapea los errores tipados de `domain` (`ValidationError`, `MissingRate`, `TransferImbalance`…) a 4xx con cuerpo estructurado. `lib/api.ts` los normaliza a un `ApiError { status, code, message }`; la UI muestra el `message` en un **toast** (mutaciones) o en `ErrorState` (cargas de página).
- **FX sin tasa (`MissingRate`):** mensaje accionable que enlaza a `/settings` para fijar `usd_cop`.
- **Import (P5):** la respuesta trae errores **por número de línea**; `/import` los lista en tabla (línea + motivo) y deja claro que la operación es **atómica** (todo o nada): nada se importó si hubo errores.
- **Sesión expirada (401):** intercepta en el cliente API → limpia cache y redirige a `/login`.
- **Red / 5xx:** `ErrorState` con botón *reintentar* (refetch de React Query); las mutaciones revierten su optimistic update.
- **Validación de formularios:** validación de forma en el cliente (campos requeridos, formatos) para UX; la validación **autoritativa** es siempre la del backend.

## Testing y criterio de "listo"

**Testing v1:** prueba manual end-to-end contra una API de P1 real (alineado con §11 del general: "Frontend v1: prueba manual; tests de componentes después"). Smoke checklist por pantalla: carga, CRUD, filtros, formato de dinero, manejo de error.

**Criterio de "listo" v1 (mínimo aceptable, ADR-008):**
1. **Login funciona:** contraseña → sesión → acceso al shell; rutas protegidas redirigen sin sesión; logout limpia.
2. **Dashboard muestra el safe-to-spend del mes + "Por pagar"** con toggle esta-semana/este-mes + total, y **permite marcar pagado** reflejando el cambio (Por-pagar, safe-to-spend y balances se actualizan).
3. **`/reports` renderiza el reporte mensual** (markdown + tablas, incl. safe-to-spend y sobres) con selector de mes, degradando con elegancia en arranque en frío (sin drift MoM).

**Backlog (post-v1):** CRUD de transacciones y el resto de pantallas (por-pagar dedicada, recurring, budgets, goals, masters, import, settings) operativas contra sus endpoints — se construyen feature por feature; mientras tanto se operan por agente.

## Integración con otros sub-proyectos

- **P1 (HTTP API + Auth):** dependencia dura. Único punto de contacto del frontend con el backend; P6 arranca apenas P1 publica el contrato. Cualquier cambio de contrato se refleja en `lib/api.ts` y sus tipos.
- **P3 (Motor temporal):** habilita `/por-pagar`, el widget del dashboard y el CRUD de `/recurring` (endpoints `/planned`, `/recurring`). Hasta que P3 aterrice, esas vistas quedan stubbeadas.
- **P4 (Presupuestos + Metas):** habilita `/budgets` y `/goals` y las tarjetas "metas" y "presupuestos en riesgo" del dashboard.
- **P5 (Reportes + Importer):** habilita `/reports` (render del markdown + datos) y `/import` (con errores por línea del validador).
- **P2 (MCP):** sin acoplamiento — vía alterna de entrada al mismo backend; el frontend lo ignora. (Lo registrado por el agente aparece igual en la UI porque comparten DB.)
- **P7 (Despliegue):** el frontend es un servicio de `docker-compose`; Caddy enruta `quaestor.tudominio.com` → frontend y `/api/*` → FastAPI. El frontend lee la base URL del API de una env var (`NEXT_PUBLIC_API_URL` o proxy interno).

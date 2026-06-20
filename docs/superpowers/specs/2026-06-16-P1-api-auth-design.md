# Quaestor — P1 HTTP API + Auth (sub-project)

**Date:** 2026-06-16
**Depends on:** P0 (Core: domain + services + db)
**Part of:** `2026-06-16-quaestor-general-design.md` (see §3 architecture, §4 auth, §5 data model, §11 errors)

---

## Objective

Expose the P0 services as an **HTTP REST API** (FastAPI), protected by single-user auth, ready for the frontend (P6) and any programmatic client (curl, Claude Code) to consume. The API is a **thin adapter**: it translates HTTP ↔ services and contains no business logic.

---

## Scope

**Includes:**
- FastAPI app + REST routers mirroring the P0 services: `/transactions`, `/accounts`, `/category-groups`, `/categories`, `/tags`, `/fx`, `/settings`.
- Dual-path single-user auth: static bearer token (`APP_TOKEN`) **and** cookie session (login/logout with a password).
- CORS for the frontend origin.
- Pydantic request/response schemas (reusing the P0 SQLModel models).
- Mapping of domain errors → 4xx responses with a clear JSON body.

**Does not include (other sub-projects add these, leaving the structure ready to grow):**
- Feature routers: `/recurring`, `/planned`, `/rollover` (P3); `/budgets` (incl. `/budgets/safe-to-spend`), `/goals` (P4); `/reports`, `/import` (P5). They are registered as new `APIRouter`s without touching anything in P1.
- MCP (P2), frontend (P6), deployment/Caddy (P7).

---

## Contribution to the data model

**None.** P1 neither creates nor migrates entities; it consumes those of P0 (Account, Category, Transaction, Tag, FxRate, Settings). The only new configuration lives in **env vars**, not in the DB: `APP_TOKEN` (bearer), `APP_PASSWORD` (frontend login), `SESSION_SECRET` (cookie signing), `FRONTEND_ORIGIN` (CORS).

---

## Components

Inside `backend/src/quaestor/api/`:

```
api/
├── __init__.py        # creates and configures the FastAPI app (create_app() factory)
├── deps.py            # dependencies: get_session, require_auth
├── auth.py            # /auth router (login/logout) + session/cookie logic
├── errors.py          # exception handlers: domain -> 4xx JSON
├── schemas.py         # Pydantic request/response models (in/out)
└── routers/
    ├── transactions.py
    ├── accounts.py
    ├── categories.py
    ├── tags.py
    ├── fx.py
    └── settings.py
```

- **`create_app()`**: instantiates FastAPI, mounts CORS, registers exception handlers, includes routers. Single place where P3/P4/P5 add their routers.
- **`deps.get_session`**: yields a SQLModel `Session` (from `quaestor.db`), closed at the end of the request.
- **`deps.require_auth`**: global dependency applied to **all** business routers; accepts a bearer token or a valid session (see §7).
- **`schemas.py`**: `XxxCreate`, `XxxUpdate`, `XxxOut`. `Out` derives from the SQLModel models; amounts travel in **cents (int)** exactly as in the domain (§5).

---

## Public interface

Base path: `/api`. Every endpoint (except `/auth/login`) requires auth. Uniform REST convention per resource.

### Auth (`/auth`)
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Body `{password}`. If it matches `APP_PASSWORD` → sets a signed session cookie (`HttpOnly`, `Secure`, `SameSite=Lax`); responds `200 {ok:true}`. Otherwise → `401`. |
| `POST` | `/auth/logout` | Invalidates/clears the session cookie; `200 {ok:true}`. |
| `GET` | `/auth/me` | `200 {authenticated:true}` if there is a valid session/token; used by the frontend to decide whether to prompt for login. |

### Core resources (all under auth)
| Resource | Endpoints |
|---|---|
| **Transactions** | `GET /transactions` (filters: `date_from`, `date_to`, `account_id`, `category_id`, `tag`, `type`, `status`) · `GET /transactions/{id}` · `POST /transactions` (expense/income, dispatches to `record_expense`/`record_income` based on `type`) · `POST /transactions/transfer` → `transfer` (creates the atomic pair) · `PATCH /transactions/{id}` · `DELETE /transactions/{id}` |
| **Accounts** | `GET /accounts` (`?archived=`) · `GET /accounts/{id}` · `POST /accounts` · `PATCH /accounts/{id}` · `DELETE /accounts/{id}` (archives) |
| **CategoryGroups** | `GET /category-groups` · `POST /category-groups` · `PATCH /category-groups/{id}` · `DELETE /category-groups/{id}` (archives) — group entity (ADR-023) |
| **Categories** | `GET /categories` · `GET /categories/{id}` · `POST /categories` (accepts `group_id?`) · `PATCH /categories/{id}` · `DELETE /categories/{id}` (archives) |
| **Tags** | `GET /tags` · `POST /tags` · `PATCH /tags/{id}` · `DELETE /tags/{id}` |
| **FX** | `GET /fx?date=` → current rate (`current_rate`) · `POST /fx` → `set_rate` (`{date, usd_cop}`), **manual override** (the rate is populated by a daily job, P7/ADR-011) |
| **Settings** | `GET /settings` · `PATCH /settings` (base currency, config) |

Responses: `200` (read/update), `201` (create), `204` (delete/archive with no body). Bodies = `Out` schemas.

---

## Key logic and rules

- **Every endpoint calls a P0 service; it NEVER touches the DB directly.** The router receives the `Session` via dependency and passes it to the service. Zero SQL queries or mutations in the `api/` layer. This preserves the general design's "golden rule" (§3).
- **No business logic in the API.** Sign by `type`, `to_base` computation, FX freezing, transfer balancing, and balance updates all live in services/domain. The router only (de)serializes and maps errors.
- **Dual auth, single authorization.** `require_auth` authorizes if **either** of the two paths is valid:
  - **Bearer token** (`Authorization: Bearer <APP_TOKEN>`) → programmatic path: Claude Code, curl, scripts. Constant-time comparison.
  - **Session cookie** (signed with `SESSION_SECRET`) → browser path: the frontend does `POST /auth/login` once and then sends the cookie automatically; it never sees the `APP_TOKEN`.
  - Both paths reach the same set of endpoints with the same permissions (single-user, no roles).
- **CORS** restricted to `FRONTEND_ORIGIN`, with `allow_credentials=True` so the cookie travels. Methods `GET/POST/PATCH/DELETE`.
- **Filters and pagination** are translated into arguments of the read services; the API does not build its own queries.

---

## Errors

`api/errors.py` registers exception handlers that convert typed domain errors (§11 of the general design) into consistent JSON responses:

| Domain exception | HTTP | Body `{error, detail}` |
|---|---|---|
| `ValidationError` | `422` | which field/rule failed |
| `MissingRate` | `409` | "no usd_cop rate for the date; set the rate" |
| `TransferImbalance` | `409` | "the transfer does not balance" |
| `NotFound` (nonexistent resource) | `404` | id not found |
| Missing/invalid auth | `401` | "credentials required or invalid" |
| Invalid Pydantic request | `422` | (FastAPI's default handler) |

Uniform format: `{"error": "<type>", "detail": "<readable message>"}`. The frontend and curl always receive the same shape.

---

## Testing and "done" criteria

**Tests (`pytest` + `TestClient`, SQLite in-memory):**
- **Happy-path CRUD** for each core resource with a bearer token (create → read → update → archive).
- **Auth rejected:** request with no credentials → `401`; wrong token → `401`.
- **Login:** `POST /auth/login` with the correct password → `200` + cookie; with the resulting cookie a protected endpoint is reached; wrong password → `401`; `logout` invalidates the session.
- **Validation:** invalid body → `422`; FX with no rate → `409 MissingRate`; unbalanced transfer → `409 TransferImbalance`.
- **Error mapping:** each domain exception produces the expected HTTP status and body.

**Done criteria:**
1. With `curl` + `Authorization: Bearer $APP_TOKEN` you can do **full CRUD** over the core (transactions, accounts, categories, tags, fx, settings).
2. `POST /auth/login` with the password yields a **valid session cookie** that authorizes the same endpoints without a token.
3. The `TestClient` suite passes (happy-path + auth rejected + validation) green.
4. No endpoint accesses the DB without going through a P0 service.

---

## Integration with other sub-projects

- **P0 (Core):** direct consumer. The API imports and calls services; if P0 changes a signature, P1 adjusts the adapter. Shares the `Session`/engine from `quaestor.db`.
- **P2 (MCP):** sibling adapter over the same services; reuses the **same bearer-token strategy** (`APP_TOKEN`). It does not share router code, but it does share the auth contract.
- **P3/P4/P5:** add their routers (`/recurring`, `/planned`, `/rollover`, `/budgets`, `/goals`, `/reports`, `/import`) by registering them in `create_app()` and reusing `require_auth` and `errors.py`. The P1 structure already accommodates them without a rewrite.
- **P6 (Frontend):** consumer of the contract. Uses the **cookie session** path (login with password); `lib/api.ts` types these endpoints. CORS enables its origin.
- **P7 (Deployment):** Caddy routes `/api/*` → this service; provides `APP_TOKEN`, `APP_PASSWORD`, `SESSION_SECRET`, `FRONTEND_ORIGIN` via env; HTTPS makes the `Secure` cookies secure.

# Quaestor — P1 HTTP API + Auth (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** P0 (Core: domain + services + db)
**Parte de:** `2026-06-16-quaestor-general-design.md` (ver §3 arquitectura, §4 auth, §5 modelo de datos, §11 errores)

---

## Objetivo

Exponer los services de P0 como una **HTTP API REST** (FastAPI), protegida por auth single-user, lista para que la consuma el frontend (P6) y cualquier cliente programático (curl, Claude Code). La API es un **adaptador delgado**: traduce HTTP ↔ services, no contiene lógica de negocio.

---

## Alcance

**Incluye:**
- App FastAPI + routers REST espejo de los services de P0: `/transactions`, `/accounts`, `/categories`, `/tags`, `/fx`, `/settings`.
- Auth single-user de doble camino: bearer token estático (`APP_TOKEN`) **y** sesión por cookie (login/logout con contraseña).
- CORS para el origin del frontend.
- Schemas Pydantic de request/response (reutilizando los modelos SQLModel de P0).
- Mapeo de errores de dominio → respuestas 4xx con cuerpo JSON claro.

**No incluye (lo agregan otros sub-proyectos, dejando la estructura lista para crecer):**
- Routers de features: `/recurring`, `/planned`, `/rollover` (P3); `/budgets`, `/goals` (P4); `/reports`, `/import` (P5). Se registran como nuevos `APIRouter` sin tocar lo de P1.
- MCP (P2), frontend (P6), despliegue/Caddy (P7).

---

## Aporte al modelo de datos

**Ninguno.** P1 no crea ni migra entidades; consume las de P0 (Account, Category, Transaction, Tag, FxRate, Settings). La única configuración nueva vive en **env vars**, no en DB: `APP_TOKEN` (bearer), `APP_PASSWORD` (login del frontend), `SESSION_SECRET` (firma de cookie), `FRONTEND_ORIGIN` (CORS).

---

## Componentes

Dentro de `backend/src/quaestor/api/`:

```
api/
├── __init__.py        # crea y configura la app FastAPI (factory create_app())
├── deps.py            # dependencies: get_session, require_auth
├── auth.py            # router /auth (login/logout) + lógica de sesión/cookie
├── errors.py          # exception handlers: dominio -> 4xx JSON
├── schemas.py         # modelos Pydantic request/response (in/out)
└── routers/
    ├── transactions.py
    ├── accounts.py
    ├── categories.py
    ├── tags.py
    ├── fx.py
    └── settings.py
```

- **`create_app()`**: instancia FastAPI, monta CORS, registra exception handlers, incluye routers. Punto único donde P3/P4/P5 añaden sus routers.
- **`deps.get_session`**: yield de una `Session` de SQLModel (de `quaestor.db`), cerrada al final del request.
- **`deps.require_auth`**: dependency global aplicada a **todos** los routers de negocio; acepta bearer token o sesión válida (ver §7).
- **`schemas.py`**: `XxxCreate`, `XxxUpdate`, `XxxOut`. `Out` deriva de los SQLModel; los montos viajan en **centavos (int)** tal cual el dominio (§5).

---

## Interfaz pública

Base path: `/api`. Todos los endpoints (salvo `/auth/login`) requieren auth. Convención REST uniforme por recurso.

### Auth (`/auth`)
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/login` | Body `{password}`. Si coincide con `APP_PASSWORD` → setea cookie de sesión firmada (`HttpOnly`, `Secure`, `SameSite=Lax`); responde `200 {ok:true}`. Si no → `401`. |
| `POST` | `/auth/logout` | Invalida/borra la cookie de sesión; `200 {ok:true}`. |
| `GET` | `/auth/me` | `200 {authenticated:true}` si hay sesión/token válido; usado por el frontend para saber si pedir login. |

### Recursos core (todos bajo auth)
| Recurso | Endpoints |
|---|---|
| **Transactions** | `GET /transactions` (filtros: `date_from`, `date_to`, `account_id`, `category_id`, `tag`, `type`, `status`) · `GET /transactions/{id}` · `POST /transactions` (gasto/ingreso, despacha a `registrar_gasto`/`registrar_ingreso` según `type`) · `POST /transactions/transfer` → `transferir` (crea el par atómico) · `PATCH /transactions/{id}` · `DELETE /transactions/{id}` |
| **Accounts** | `GET /accounts` (`?archived=`) · `GET /accounts/{id}` · `POST /accounts` · `PATCH /accounts/{id}` · `DELETE /accounts/{id}` (archiva) |
| **Categories** | `GET /categories` · `GET /categories/{id}` · `POST /categories` · `PATCH /categories/{id}` · `DELETE /categories/{id}` (archiva) |
| **Tags** | `GET /tags` · `POST /tags` · `PATCH /tags/{id}` · `DELETE /tags/{id}` |
| **FX** | `GET /fx?date=` → tasa vigente (`tasa_vigente`) · `POST /fx` → `fijar_tasa` (`{date, usd_cop}`) |
| **Settings** | `GET /settings` · `PATCH /settings` (moneda base, config) |

Respuestas: `200` (read/update), `201` (create), `204` (delete/archive sin cuerpo). Cuerpos = schemas `Out`.

---

## Lógica y reglas clave

- **Cada endpoint llama a un service de P0; NUNCA toca la DB directo.** El router recibe la `Session` por dependency y la pasa al service. Cero queries ni mutaciones SQL en la capa `api/`. Esto preserva la "regla de oro" del general (§3).
- **Sin lógica de negocio en la API.** Signo por `type`, cálculo de `to_base`, congelado de FX, cuadre de transferencias y actualización de balance viven en services/domain. El router solo (de)serializa y mapea errores.
- **Doble auth, una sola autorización.** `require_auth` autoriza si **cualquiera** de los dos caminos es válido:
  - **Bearer token** (`Authorization: Bearer <APP_TOKEN>`) → camino programático: Claude Code, curl, scripts. Comparación en tiempo constante.
  - **Cookie de sesión** (firmada con `SESSION_SECRET`) → camino browser: el frontend hace `POST /auth/login` una vez y luego manda la cookie automáticamente; nunca ve el `APP_TOKEN`.
  - Ambos caminos llegan al mismo conjunto de endpoints con los mismos permisos (single-user, sin roles).
- **CORS** restringido a `FRONTEND_ORIGIN`, con `allow_credentials=True` para que viaje la cookie. Métodos `GET/POST/PATCH/DELETE`.
- **Filtros y paginación** se traducen a argumentos de los services de lectura; la API no arma queries propias.

---

## Errores

`api/errors.py` registra exception handlers que convierten errores tipados del dominio (§11 del general) en respuestas JSON consistentes:

| Excepción de dominio | HTTP | Cuerpo `{error, detail}` |
|---|---|---|
| `ValidationError` | `422` | qué campo/regla falló |
| `MissingRate` | `409` | "no hay tasa usd_cop para la fecha; fija la tasa" |
| `TransferImbalance` | `409` | "la transferencia no cuadra" |
| `NotFound` (recurso inexistente) | `404` | id no encontrado |
| Auth ausente/ inválida | `401` | "credenciales requeridas o inválidas" |
| Pydantic request inválido | `422` | (handler por defecto de FastAPI) |

Formato uniforme: `{"error": "<tipo>", "detail": "<mensaje legible>"}`. El frontend y curl reciben siempre el mismo shape.

---

## Testing y criterio de "listo"

**Tests (`pytest` + `TestClient`, SQLite in-memory):**
- **Happy-path CRUD** de cada recurso core con bearer token (crear → leer → actualizar → archivar).
- **Auth rechazada:** request sin credenciales → `401`; token incorrecto → `401`.
- **Login:** `POST /auth/login` con contraseña correcta → `200` + cookie; con cookie posterior se accede a un endpoint protegido; contraseña incorrecta → `401`; `logout` invalida la sesión.
- **Validación:** body inválido → `422`; FX sin tasa → `409 MissingRate`; transferencia descuadrada → `409 TransferImbalance`.
- **Mapeo de errores:** cada excepción de dominio produce el HTTP y el cuerpo esperados.

**Criterio de listo:**
1. Con `curl` + `Authorization: Bearer $APP_TOKEN` se hace **CRUD completo** sobre el core (transactions, accounts, categories, tags, fx, settings).
2. `POST /auth/login` con la contraseña entrega una **cookie de sesión válida** que autoriza los mismos endpoints sin token.
3. La suite de `TestClient` pasa (happy-path + auth rechazada + validación) en verde.
4. Ningún endpoint accede a la DB sin pasar por un service de P0.

---

## Integración con otros sub-proyectos

- **P0 (Core):** consumidor directo. La API importa y llama services; si P0 cambia una firma, P1 ajusta el adaptador. Comparte la `Session`/engine de `quaestor.db`.
- **P2 (MCP):** adaptador hermano sobre los mismos services; reutiliza la **misma estrategia de bearer token** (`APP_TOKEN`). No comparte código de routers, sí el contrato de auth.
- **P3/P4/P5:** agregan sus routers (`/recurring`, `/planned`, `/rollover`, `/budgets`, `/goals`, `/reports`, `/import`) registrándolos en `create_app()` y reusando `require_auth` y `errors.py`. La estructura de P1 ya los acomoda sin reescritura.
- **P6 (Frontend):** consumidor del contrato. Usa el camino de **sesión por cookie** (login con contraseña); `lib/api.ts` tipa estos endpoints. CORS habilita su origin.
- **P7 (Despliegue):** Caddy enruta `/api/*` → este servicio; provee `APP_TOKEN`, `APP_PASSWORD`, `SESSION_SECRET`, `FRONTEND_ORIGIN` por env; HTTPS hace seguras las cookies `Secure`.

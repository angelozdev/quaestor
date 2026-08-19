---
slug: error-contract
checkpoint: 4
plan_status: proposed
created: 2026-08-18
---

# Plan — 016 error-contract

## Architecture

### La decisión de fondo

**El código y los datos viven en la excepción de dominio, no en un mapeo
aparte.** Registrada como **ADR-0059** (accepted). `QuaestorError` gana dos
campos opcionales que ningún sitio sin migrar necesita tocar:

```python
class QuaestorError(Exception):
    def __init__(self, message: str, *, code: str | None = None, data: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data or {}
```

Ninguna de las 6 subclases (`ValidationError`, `NotFound`, …) declara
`__init__` hoy, así que todas heredan esto sin tocarse. Un sitio que no pasa
`code=`/`data=` sigue exactamente como está — `code` queda `None`, y
`api/errors.py` cae al mismo `type(exc).__name__` que manda hoy.

### `api/errors.py`

```python
def _body(exc: QuaestorError, class_name: str) -> dict:
    code = exc.code or class_name
    body = {"error": code, "detail": str(exc)}
    if exc.data:
        body["data"] = exc.data
    return body
```

Gana un manejador nuevo, el último en registrarse:

```python
@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "Ocurrió un error inesperado. Intenta de nuevo."})
```

FastAPI resuelve por el handler más específico (MRO), así que este **nunca**
intercepta lo que `QuaestorError`, `Unauthorized` o `RequestValidationError`
ya cubren — solo lo que hoy cae al default de Starlette.

### `_format_validation` — el código+datos que Pydantic ya regala

Verificado contra esta versión (Pydantic 2.13, corrido en el proyecto): cada
error trae `type` (`"missing"`, `"greater_than"`, `"int_parsing"`…) y `ctx`
cuando aplica (`{"gt": 0}`). Mismo patrón, gratis:

```python
_PYDANTIC_ES: dict[str, str] = {
    "missing": "Este campo es obligatorio",
    "int_parsing": "Debe ser un número entero",
    "greater_than": "Debe ser mayor que {gt}",
    # … el resto de los tipos que las requests de este proyecto pueden disparar
}

def _spanish_for(err: dict) -> str:
    template = _PYDANTIC_ES.get(err["type"])
    if template is None:
        return err.get("msg", "invalid")  # respaldo: el inglés de Pydantic, sin excepción
    return template.format(**err.get("ctx", {}))
```

Mismo respaldo que el resto del contrato: un `type` que el diccionario no
cubre cae al `msg` de Pydantic, nunca a un genérico ni a un vacío.

### La limpieza que hace literal "una sola vez, cinco puertas"

> **Corregido en CP6 (refine, 2026-08-19):** el diseño de abajo deja
> `require_positive` en `transactions.py`. `lint-imports` encontró que eso
> rompe un contrato de capas — `metas.py` llegaba a `funds.py` por
> transitividad, algo que el propio código prohíbe. La función terminó
> viviendo en `domain/errors.py`, su lugar correcto de todos modos (lógica
> pura, sin sesión). Ver el handoff de refine para el detalle; esta sección
> queda como el registro de CP4, no reescrita.

Medido, no asumido: **`require_positive` existe en `transactions.py` y solo
`transactions.py` lo llama.** `recurring.py` (dos sitios), `metas.py` (dos
sitios) y `funds.py` (un sitio) cada uno reimplementa a mano
`if amount <= 0: raise ValidationError(...)`, con su propio texto en inglés.
AC-3 exige que el código+dato sea el mismo sin importar cuál de las cinco
puertas dispare el rechazo — así que antes de agregarle `code=` a cinco
copias, las cuatro que faltan pasan a llamar la función que ya existe:

```python
# recurring.py, metas.py, funds.py — antes
if amount <= 0:
    raise ValidationError("amount must be > 0")  # o su variante local

# después
require_positive(amount)
```

`require_positive` gana el código una sola vez:

```python
def require_positive(amount: int) -> None:
    if amount <= 0:
        raise ValidationError("amount must be > 0", code="amount_not_positive")
```

La especificidad que se pierde (`"a meta needs an amount above zero"` vs
`"amount must be > 0"`) solo vivía en el inglés que nadie del lado del
dueño lee — la frase en español que sí ve es idéntica en las cinco puertas
por diseño (AC-3).

### `services/categories.py` — los dos códigos de duplicado

```python
# _refuse_name_already_held
if held.archived:
    raise ValidationError(
        f"an archived {direction} category is already named {held.name!r} — restore it instead of creating a second one",
        code="category_duplicate_archived",
        data={"name": held.name, "direction": direction},
    )
raise ValidationError(
    f"an {direction} category named {held.name!r} already exists",
    code="category_duplicate_active",
    data={"name": held.name, "direction": direction},
)
```

### Frontend

`ApiError` (`frontend/lib/api/types.ts:473`) gana un quinto campo:

```typescript
export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>
  data: Record<string, unknown>
  constructor(status, code, message, fields?, data?) { … this.data = data ?? {} }
}
```

`client.ts:32` pasa `data?.data` igual que ya pasa `data?.fields`. Catálogo
nuevo, una función pura por código:

```typescript
// frontend/lib/api/error-catalog.ts
export const ERROR_CATALOG: Record<string, (data: Record<string, unknown>) => string> = {
  category_duplicate_active: (d) => `Ya existe una categoría de ${d.direction === "income" ? "ingreso" : "gasto"} llamada «${d.name}»`,
  category_duplicate_archived: (d) => `Ya existe una categoría de ${d.direction === "income" ? "ingreso" : "gasto"} archivada llamada «${d.name}». Restaurarla en vez de crear otra.`,
  amount_not_positive: () => "El monto debe ser mayor que cero",
}

export function translateApiError(err: ApiError): string {
  return ERROR_CATALOG[err.code]?.(err.data) ?? err.message
}
```

Sin entrada en el catálogo → `err.message` (el `detail` de siempre, en
inglés si el sitio no está migrado). Mismo respaldo, ahora en el cliente.

Las dos pantallas tocadas llaman `translateApiError` en su `onError` y
ponen el resultado con `form.setFieldMeta(campo, { error: … })` — el mismo
mecanismo que `applyApiErrorsToForm` ya usa para los errores de Pydantic,
no uno nuevo.

### Acoplamiento y radio de impacto

Medido:

| símbolo | sitios | qué pasa |
|---|---|---|
| `QuaestorError.__init__` | 1 definición, 0 llamadores rotos | las 6 subclases heredan sin cambiar |
| `require_positive` | 1 definición, gana `code=`; 3 sitios nuevos lo llaman (`recurring.py` ×2, `metas.py` ×2, `funds.py` ×1) en vez de reimplementarlo | `transactions.py`'s 5 llamadores existentes no cambian de firma |
| `_refuse_name_already_held` | 1 función, 2 `raise` | gana `code=`/`data=` en los dos |
| `api/errors.py::_domain` | 1 handler | lee `exc.code`/`exc.data` en vez de solo `type(exc).__name__` |
| `api/errors.py` | +1 handler (`Exception`) | no compite con los 3 ya registrados (MRO) |
| `_format_validation` | 1 función | gana la tabla `type → español`, misma firma de salida |
| `ApiError` | 1 clase, todos sus constructores (2 en `client.ts`, tests) | gana un campo opcional, nada obligatorio se rompe |
| `mandatory_categories.py` (feature 008) | 2 handlers (`then_told_category_exists`, `then_offered_to_restore`) | **fuera de esta feature, pero anotado en `spec.md`**: sus aserciones buscan `"exist"`/`"already"`/`"restore"` en inglés y van a fallar en cuanto AC-1/AC-2 manden español — se arreglan en la Rebanada 2 de este mismo plan, no en un plan aparte, porque romperían la 008 si no |

### Alternativas descartadas

Las cuatro opciones y su balance están en la **ADR-0059**. En una línea: un
registro centralizado se desincroniza del mensaje real; español directo
desde el servidor cierra la puerta a otro idioma (ya descartada por el dueño
el 2026-08-04); la librería RFC 9457 es de un solo mantenedor con 12 días de
vida.

## Charter Check

| # | Regla del charter | Estado | Evidencia |
|---|---|---|---|
| §1 | DAE con ATDD completo; ADRs para lo arquitectónico | ✅ | `feature.md`, `acs.md`, `spec.md` + IR existen. **ADR-0059 accepted** — la decisión que este plan implementa. |
| §2 | Posture local-only; capas `api/ → services/ → domain/ → db`; migraciones en `migrations/` | ✅ | Nada remoto. `domain/errors.py` gana `code`/`data` como atributos planos — no importa nada de `api/` ni de JSON, la capa sigue pura. Sin migración: ningún esquema cambia. |
| §3 | Inglés en el código; Python ≥3.12 + uv + pytest; pnpm; Biome; Conventional Commits | ✅ | Los códigos (`category_duplicate_active`, `amount_not_positive`) son identificadores `snake_case` en inglés — la copia visible es lo único en español, como siempre. |
| §4 | Un solo usuario, local | ✅ | No agrega superficie nueva; corrige una que ya existe. |
| §5 | Roles architect / implementer / acceptance-tester / reviewer | ✅ | CP4 architect (este plan), CP5 implementer, `spec.md` ya lo escribió el bridge de `atdd:atdd`, CP6–CP8 reviewer. |
| §6 | Nada mergea sin backend **y** frontend verdes en la superficie tocada | ✅ | Stream `mixed`: 6 escenarios `@backend` (5 generan pytest, AC-6 es unitaria) + 3 de pantalla (vitest). |
| §6 | Una pantalla que escribe plata se prueba contra una cuenta en otra moneda | N/A | Esta feature no calcula ni convierte ninguna cifra de dinero — cambia el **idioma** de un rechazo, nunca el monto que se guarda. AC-3 toca la corrección de un monto, pero el candado que dispara (`amount <= 0`) es el mismo sin importar la moneda de la cuenta; no hay una cifra nueva que pueda desviarse por moneda. |
| §6 | Una cifra que la app convierte se prueba en otra moneda también | N/A | Mismo motivo — ningún valor convertido nace de esta feature. |
| §6 | Verde no es verificado: se maneja en navegador antes de darla por hecha | ✅ | Programado en la Rebanada 5 / CP7: los tres avisos reales que `validation_method` nombra (categoría duplicada activa, archivada, monto inválido al corregir), leyendo el texto y el campo, no solo el código de estado. |
| §7 | Autonomía media con puertas de datos | ✅ | Ninguna rebanada toca `migrations/**` — el tope `low` del manifiesto no se activa. |
| §7 | Humano obligatorio para merges a `main` | ✅ | El merge es del dueño. |
| — | Postura de autonomía declarada | ✅ | `medium`, sin excepción — no hay migración que capar. |
| — | Independencia de la verificación | ✅ | `spec.md` se escribió y quedó en rojo (5 fallan, 1 pasa — el guardia de AC-5) **antes** de este plan (CP3, 2026-08-18). |
| — | Política de mutación | ✅ | Sweep chico en el CP8: los dos códigos de `categories.py` y el `require_positive` compartido son el blanco natural (una constante de código cambiada de lugar es exactamente lo que mutation testing atrapa). Recordatorio: la suite de backend no es hermética (`test_scheduler` toca `backend/quaestor.db` en disco) — correr el sweep sobre un worktree limpio. |

### Amendments

**Ninguna enmienda al charter.** Las dos filas marcadas N/A no son una
desviación de una regla aplicable — la regla existe para cifras que la app
calcula o convierte, y esta feature no produce ninguna cifra nueva, solo
cambia el idioma de un texto. No hay ⚠️ que arrastrar.

## Phasing

Cinco rebanadas — cada una atraviesa lo que hace falta de dominio, API y
pantalla, y cada una termina con sus escenarios en verde.

### Rebanada 1 — La base: código y datos viajan, y nada se rompe

*Sin AC propia — es la plomería que las demás usan. AC-5 (ya verde) es la
prueba de que nada cambió para lo que no se toca.*

`QuaestorError.__init__` gana `code`/`data`. `api/errors.py::_domain` los
lee. `ApiError` gana `data` en el frontend, `client.ts` lo pasa. Ningún
`raise` existente cambia todavía — esta rebanada es puro cableado.

Termina cuando el suite completo (backend + acceptance + vitest) sigue
exactamente en el mismo estado que hoy — ni un verde nuevo, ni un rojo
nuevo salvo los que ya estaban.

### Rebanada 2 — Categoría duplicada, y la 008 se pone al día

*AC-1, AC-2 · 4 escenarios (2 `@backend`, 2 vitest)*

`_refuse_name_already_held` gana los dos códigos. El catálogo del frontend
nace con sus dos primeras entradas. La pantalla de crear categoría llama
`translateApiError` y pone el resultado bajo el campo Nombre.

**Incluye el arreglo a `mandatory_categories.py`** (feature 008):
`then_told_category_exists` y `then_offered_to_restore` pasan a comprobar
`code` en vez de buscar `"exist"`/`"already"`/`"restore"` en inglés — se
haría igual sin esta feature en cuanto el texto cambiara, así que se arregla
aquí, no se deja como regresión para que alguien la encuentre después.

Termina cuando AC-1 y AC-2 pasan, y la suite completa de la 008 (211 casos
medidos en CP3) sigue en 100% verde.

### Rebanada 3 — Monto inválido, y las cinco puertas comparten un candado

*AC-3 · 3 escenarios (2 `@backend`, 1 vitest)*

`recurring.py`, `metas.py`, `funds.py` dejan de reimplementar el chequeo y
llaman `require_positive`, que gana `code="amount_not_positive"`. El
diálogo de corrección de movimientos llama `translateApiError` y pone el
resultado bajo el campo Monto.

Termina cuando corregir a 0 o a un número negativo se rechaza igual desde
cualquiera de las cinco puertas, y las cuatro suites que hoy pasan por
`require_positive`-equivalente (transacciones, recurrentes, metas, fondos)
siguen verdes.

### Rebanada 4 — Pydantic en español

*AC-4 · 1 escenario*

`_format_validation` gana la tabla `type → plantilla`. Cubre los tipos que
las requests reales de este proyecto pueden disparar (`missing`,
`int_parsing`, `greater_than`, `less_than`, `string_type` — confirmar la
lista exacta contra los schemas de `api/schemas.py` durante CP5).

Termina cuando declarar un fondo sin categoría responde en español, y
cualquier tipo de error de Pydantic no cubierto sigue cayendo a su `msg` en
inglés, sin excepción no manejada.

### Rebanada 5 — Lo que nadie previó, y el paso por navegador

*AC-6 · 1 test unitario, sin escenario Gherkin (acordado en CP3)*

El manejador `Exception` en `api/errors.py`, con `logging.getLogger(__name__).exception(...)`.
Un test unitario le pasa una excepción arbitraria y confirma `code:
internal_error`, el mensaje fijo, y que el log capturó la excepción real.

**Cierra con el paso por navegador de CHARTER §6**, contra el sandbox: los
tres avisos que `validation_method` nombra, leyendo el texto exacto y el
campo donde aparece — no solo que la petición responda 4xx.

## Performance budgets

Feature sin cifras de dinero ni consultas nuevas — el presupuesto es
literal, no medido:

| presupuesto | hoy | techo | por qué |
|---|---|---|---|
| consultas nuevas a la base | — | **cero** | `code`/`data` son atributos de un objeto Python ya en memoria; nada nuevo se lee ni se escribe |
| costo del catálogo del frontend | — | **O(1)** | acceso a una propiedad de un objeto plano, mismo costo que ya tiene leer `err.message` |
| tamaño de la respuesta de error | `{error, detail}` | `{error, detail, data?}` | `data` son 1–2 pares clave-valor cortos (un nombre de categoría, una dirección) — no cambia el orden de magnitud |

Si alguna rebanada termina agregando una consulta, está mal hecha — no hay
ninguna razón de dominio para que la haya.

## Collaboration schedule

| momento | quién | qué |
|---|---|---|
| antes de la rebanada 1 | dueño | aprueba este plan |
| fin de cada rebanada | agente | reporta escenarios verdes y qué queda rojo |
| fin de la rebanada 5 | **dueño + agente** | paso por navegador contra el sandbox (CHARTER §6) — sin este paso la feature no se da por hecha |
| merge a `main` | **dueño** | CHARTER §7 |

## Execution modes

- **Las cinco rebanadas:** autonomía `medium` — ninguna toca
  `migrations/**`, así que el tope `low` del manifiesto no se activa en
  ningún punto.
- **Sin dispatch remoto:** `remote.ready: false` en el manifiesto.
- **Una rebanada, un commit**, Conventional Commits, escenarios de esa
  rebanada verdes antes de la siguiente.

## Test strategy

`feature.md` declara un `validation_method` propio (corregido en este plan —
el original citaba el aviso de fondo, que `discover-acs` sacó del alcance):

> «Los tres flujos (pytest, aceptación generada, vitest), más una pasada en
> el navegador viendo al menos tres avisos reales (categoría duplicada
> activa, categoría duplicada archivada, monto inválido al corregir un
> movimiento) para confirmar que el texto sale en español, bajo el campo
> correcto, y con el dato correcto interpolado — CHARTER §6.»

Cuatro capas:

1. **Aceptación generada** — 5 escenarios `@backend`. Hoy 4 en rojo por
   ausencia de la feature, 1 verde (AC-5, el guardia de no-regresión — se
   queda verde toda la implementación, si se pone rojo algo migró un sitio
   que no debía).
2. **Vitest** — 3 escenarios de pantalla (categoría activa, archivada,
   monto en corrección), bound por nombre.
3. **Unitarias** — la segunda corriente de la ATDD, y donde vive AC-6
   entero (acordado en CP3: sin escenario Gherkin, ver Rebanada 5). También
   cubre la tabla `_PYDANTIC_ES` tipo por tipo, más específico de lo que un
   escenario de aceptación necesita ser.
4. **Paso por navegador antes de darla por hecha** (CHARTER §6) — los tres
   avisos reales del `validation_method`, leídos en pantalla, no solo en la
   respuesta HTTP.

**Mutación en el CP8.** Blanco natural: los literales de código
(`category_duplicate_active` vs `_archived`) y las plantillas de
`_PYDANTIC_ES` — exactamente el tipo de constante que una mutación cambia
de lugar sin que un assert débil lo note. Correr sobre un worktree limpio
(la suite de backend no es hermética).

**Durante el rojo de la ATDD no se tocan los handlers para que pase nada.**
Los 4 rojos de hoy (5 escenarios menos el guardia de AC-5) son el estado
esperado hasta que exista la conducta.

---
title: "Un error viaja con código y datos, y la pantalla arma la frase — en el idioma que sea"
slug: error-contract
number: 016
status: done
autonomy_level: medium
branch: error-contract
area: core
owner: angelo
assignee: local
tracker_ref: local
roadmap_ref: error-contract
acceptance_stream: mixed
relevant_adrs: [0001]
created: 2026-08-18
intake: roadmap
validation_method: "Los tres flujos (pytest, aceptación generada, vitest), más una pasada en el navegador viendo al menos tres avisos reales (categoría duplicada activa, categoría duplicada archivada, monto inválido al corregir un movimiento) para confirmar que el texto sale en español, bajo el campo correcto, y con el dato correcto interpolado — CHARTER §6. Corregido en plan (2026-08-18): el ejemplo original citaba el aviso de fondo, que discover-acs sacó del alcance."
---

# Un error viaja con código y datos, y la pantalla arma la frase — en el idioma que sea

## Outcome

Cuando algo falla — una categoría duplicada, un monto inválido, un fondo que
pide una cifra rara — el dueño lee el aviso en español, con los datos
correctos. El backend deja de mandar la frase ya armada en inglés
(`an expense category named 'Transporte' already exists`) y en su lugar manda
un código estable (`category_already_exists`) más los datos que hacen falta
para armar la frase (`{name: "Transporte"}`). La pantalla, no el servidor,
decide cómo contarlo — hoy en español, y el día que haga falta otro idioma,
sin tocar el backend.

## Por qué

Pedido el 2026-08-04, justo después de ver en el navegador el aviso en
inglés. El mismo hueco también mostró una cifra mal: el aviso de un fondo
imposible decía `100000000` junto a un formulario donde el dueño había
escrito `1000000` — cien veces más, en el momento exacto en que la app le
pedía reconsiderar.

No es un string suelto: **102 sitios en el backend lanzan un error, con 69
mensajes distintos**, concentrados en categorías (21), recurrentes (17),
transacciones (14), planeados (13) y fondos (11). `api/errors.py:59` manda
`str(exc)` tal cual al cliente. ADR-0001 fijó que el código y los
identificadores son en inglés, y dejó la copia visible al usuario
explícitamente fuera de su alcance — nadie retomó esa parte desde entonces.

**Verificado contra el estándar de la industria (2026-08-18):** el formato
RFC 9457 *"Problem Details for HTTP APIs"* — el que define cómo una API HTTP
debe reportar errores — separa exactamente así: un identificador estable
(`type`) que nunca cambia de idioma, más datos de la ocurrencia, y deja la
frase para quien la muestra. Es el mismo patrón que se decidió el 4 de
agosto, y el mismo que hoy se pidió explícitamente pensando en soportar más
de un idioma después. Se evaluó adoptar una librería que implementa la RFC
completa (`fastapi-problem-details`) y se descartó: versión 0.1.5, publicada
hace 12 días, un solo mantenedor — más riesgo que las ~40 líneas que ya
existen en `api/errors.py` y que solo hay que extender.

## Scope

**Dentro:**

- Una ADR (arquitectura de API, la exige CLAUDE.md) que fija la forma: cada
  error lleva un `code` estable y los datos que la frase necesita, inspirada
  en RFC 9457 pero sin su maquinaria completa (sin `application/problem+json`,
  sin URIs resolubles — esta API no tiene consumidores externos).
- `api/errors.py` deja de mandar `str(exc)`; cada excepción de dominio declara
  su `code` y sus datos.
- Un catálogo en el frontend que traduce `code` → texto en español, construido
  para poder sumar otro idioma después sin tocar el backend.
- **El piloto:** categoría duplicada y monto inválido — los dos sitios que el
  dueño ya encontró en vivo, más los que aparezcan al escribir las ACs
  mirando cada pantalla. Categoría duplicada son en realidad **dos mensajes**
  en el mismo sitio (`_refuse_name_already_held`): nombre ya activo en esa
  dirección, y nombre en una categoría **archivada** (que sugiere restaurarla
  en vez de crear otra) — los dos entran. El código+datos de "monto inválido" se arregla una
  sola vez en el backend (cubre por igual las cinco puertas que envían un
  monto), pero el comportamiento visible solo se puede probar donde hoy es
  alcanzable: **transacciones, recurrentes, fondos y metas ya bloquean el
  monto ≤ 0 en el navegador** (`positiveCents`, mensaje en español) — el
  rechazo del servidor nunca llega a esas pantallas. El diálogo de **corregir
  un movimiento ya guardado** (`transaction-edit-dialog.tsx`, feature 012) no
  tiene ese candado, así que es donde el AC se demuestra de verdad.
  Descubierto en discover-acs (2026-08-18); el candado que falta ahí queda
  fuera — no es un problema de idioma del error, es un hueco de validación de
  la 012.
- Los mensajes que arma Pydantic solo (`field required`, tipo inválido) —
  no nacen de un `raise` del dominio, pero se tocan en el mismo archivo
  (`_format_validation`) y se traducen ya, no solo se deciden en la ADR.
- **Un manejador para lo que nadie previó.** Hoy un bug real (no una excepción
  de dominio) cae en el default de FastAPI: `{"detail": "Internal Server
  Error"}`, en inglés y fuera de la forma `{error, detail}` del resto de la
  API — sin filtrar nada interno (no hay `debug=True`), pero sin contrato ni
  registro. Gana un `code: internal_error` estable, el mismo mensaje siempre
  ("Ocurrió un error inesperado. Intenta de nuevo."), y queda registrado en
  logs para poder diagnosticarlo — nunca el detalle real de la excepción
  hacia el cliente.
- **Los sitios sin migrar responden como hoy.** Mientras dura el barrido de
  los ~100 restantes, un error sin código todavía manda `detail` en inglés
  tal cual — decidido en discover-acs (2026-08-18): mejor el detalle real en
  inglés que un genérico en español que esconde qué pasó.

**Fuera:**

- **Los ~100 sitios restantes.** Migrar los 102 de una vez es una feature
  distinta; esta prueba el patrón y el resto queda como tarea de
  consolidación aparte una vez que el catálogo existe.
- **MCP.** Tiene su propio `domain_error_text` (`mcp/format.py`) y nunca cruza
  esta costura — el asistente además se va a deprecar.
- **`FundPreview.warning` en el backend.** Descartado en discover-acs
  (2026-08-18): `create-form.tsx` ya arma la frase en español con datos
  estructurados (`crowded`, `startMonth`), sin leer ese string. Su único
  consumidor hoy es el asistente, que se va a deprecar — arreglar el string
  en inglés no le sirve a nadie que vaya a quedar. El piloto se mueve a
  categoría duplicada + monto inválido.
- **Un selector de idioma real.** Esta feature deja el contrato listo para
  soportar otro idioma; no construye la pantalla para elegirlo.

## Charter signals

- Sin migración — ningún esquema cambia, así que el tope `low` de
  `migrations/**` no aplica.
- **Una pantalla que muestra dinero se prueba en el navegador** (CHARTER §6):
  el aviso del fondo lleva una cifra, y ya se demostró una vez que ese número
  puede salir mal sin que ningún test unitario lo note.

## Related code / design pointers

- `backend/src/quaestor/api/errors.py:59` — `str(exc)` directo al cliente, lo
  que esto reemplaza
- `backend/src/quaestor/domain/errors.py` — las excepciones de dominio, donde
  cada una gana su `code`
- `services/funds.py` — `FundPreview.warning`, el piloto
- `frontend/lib/api/types.ts:473` — `ApiError` (`status`, `code`, `message`,
  `fields`); `.fields` ya existe y ya alimenta errores por campo, el catálogo
  se apoya en el mismo lugar
- `frontend/lib/api/client.ts:32` — donde `data.error` (hoy el nombre de la
  clase Python, ej. `ValidationError`) se vuelve `ApiError.code`; el cableado
  ya existe, solo falta que el backend mande un código por sitio en vez de
  por clase
- `frontend/app/(app)/funds/create-form.tsx:102` — `announcementFor`: el
  mismo patrón ya construido una vez — el backend manda datos (`crowded`,
  `startMonth`) y el frontend arma la frase en español con `formatCents`.
  Precedente directo, no hay que inventar el patrón, solo generalizarlo.
  `FundPreview.warning` (el string en inglés, todavía vivo para el asistente)
  sigue sin este tratamiento.
- ADR-0001 — fija inglés para código, deja la copia visible fuera de alcance

## Riesgos

**Que la ADR se quede corta y el catálogo crezca sin regla.** Sin un patrón
para nombrar códigos (`snake_case`, un verbo o sustantivo estable) el
catálogo del frontend se vuelve tan desordenado como los 69 mensajes que
reemplaza. La ADR fija la convención antes del primer código.

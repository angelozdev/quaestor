# 0059. Un error de dominio lleva un código estable y sus datos; la copia en español vive en el cliente

- **Status:** accepted
- **Date:** 2026-08-18
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

La app es en español de punta a punta salvo por una costura: cuando el
backend rechaza algo, el texto que llega a la pantalla es el mensaje Python
crudo, en inglés. Encontrado el 2026-08-04 en el navegador: crear una
categoría que ya existe muestra *"an expense category named 'Transporte'
already exists"*. El mismo día, un aviso de fondo imposible mostró
`100000000` junto a un formulario donde el dueño había escrito `1000000` —
cien veces más, porque el número también viaja crudo.

No es un string suelto. `api/errors.py:59` manda `str(exc)` tal cual al
cliente para **102 sitios** de `services/` y `domain/`, con **69 mensajes
distintos**, concentrados en categorías (21), recurrentes (17), transacciones
(14), planeados (13) y fondos (11). Solo **6 clases** de excepción cubren los
102 — un código por clase no alcanza para distinguir "categoría duplicada"
de "monto inválido", las dos son `ValidationError`.

ADR-0001 fijó inglés para código e identificadores y dejó la copia visible al
usuario explícitamente fuera de su alcance ("a localization concern... may be
authored in any language or routed through i18n"). Nadie retomó esa parte
hasta hoy. El dueño ya había decidido informalmente el 4 de agosto, sobre la
alternativa de que el servidor escriba español directamente: el backend
manda un código estable más los datos que hacen falta, y el cliente arma la
frase — "porque el frontend debería poder mapearlos bien". El 18 de agosto,
al retomarlo, agregó una condición nueva: el contrato tiene que dejar espacio
para más de un idioma después, sin tocar el backend cada vez.

## Decision drivers

- **Nunca perder el detalle real.** Un sitio sin código todavía tiene que
  seguir contando la verdad (en inglés, hoy) — nunca un mensaje genérico que
  esconda qué pasó. Migrar 102 sitios de una sentada no es realista; el
  contrato tiene que sobrevivir meses de migración parcial.
- **Preparado para más de un idioma, sin reescribir el backend por cada uno.**
  Pedido explícito del dueño el 2026-08-18.
- **DRY — el código nace donde nace el mensaje.** Un registro aparte
  (excepción → código) se desincroniza del mensaje real con el tiempo; es la
  misma clase de bug que produjo los 69 mensajes de hoy.
- **Las capas del CHARTER §2 se respetan.** `domain/` no debe saber de HTTP
  ni de JSON; lo que agregue tiene que seguir siendo dominio puro.
- **No construir infraestructura nueva para un problema de 40 líneas.** La
  app es de un solo usuario, local, sin consumidores externos — no hay que
  vestirla como una API pública.
- **MCP no se toca.** Tiene su propio `domain_error_text` y una audiencia
  distinta (el asistente, que se va a deprecar); el contrato nuevo no puede
  obligar a MCP a cambiar nada.

## Considered options

1. **El código y los datos viven en la excepción de dominio.** `QuaestorError`
   gana `code: str | None` y `data: dict`, opcionales; cada `raise` que se
   migra los pasa junto con el mensaje que ya escribe hoy.
2. **Un registro centralizado en `api/errors.py`** que mapea cada clase de
   excepción (o un match sobre el mensaje) a un código, sin tocar los sitios
   que hacen `raise`.
3. **El servidor arma el texto en español directamente**, sin código
   intermedio — la alternativa que se le ofreció al dueño el 2026-08-04 y que
   descartó.
4. **Adoptar una librería que implementa RFC 9457 completo**
   (`fastapi-problem-details`) en vez de extender `api/errors.py` a mano.

## Decision outcome

Chosen option: **1 — el código y los datos viven en la excepción de
dominio**, porque es la única que cumple "nunca perder el detalle real" y
"DRY" a la vez: el mensaje en inglés, el código y los datos nacen en la misma
línea, así que no hay dos lugares que puedan desacordarse.

### Pros and cons of the options

**1 — En la excepción**
- Good, porque un sitio sin migrar simplemente no pasa `code=`/`data=` y
  sigue exactamente como hoy — el respaldo es gratis, no hay que
  construirlo.
- Good, porque no depende de parsear ni de matchear texto: el código es un
  dato explícito, no una inferencia sobre el mensaje.
- Bad, porque migrar un sitio sigue siendo trabajo manual, uno por uno — no
  hay atajo automático para los ~100 restantes.

**2 — Registro centralizado**
- Good, porque no toca los 102 sitios de `raise`.
- Bad, porque un registro por *clase* no alcanza (6 clases, 69 mensajes) y
  un registro por *texto del mensaje* es frágil — cambiar una palabra en el
  mensaje English rompe el mapeo sin que nada avise.
- Bad, porque el código y el mensaje quedan en archivos distintos, la
  definición misma de la deriva que este ADR busca evitar.

**3 — Español directo desde el servidor**
- Good, porque es el camino más corto para el caso de hoy.
- Bad, porque cierra la puerta a otro idioma sin tocar el backend — lo
  contrario de lo que se pidió el 2026-08-18.
- Bad, porque ya fue evaluada y descartada por el dueño el 2026-08-04.

**4 — Librería RFC 9457**
- Good, porque estandariza el formato con un nombre reconocido en la
  industria (verificado: RFC 9457, IETF, reemplaza RFC 7807).
- Bad, porque `fastapi-problem-details` está en v0.1.5, publicada 12 días
  antes de esta decisión, un solo mantenedor — más riesgo que las ~40 líneas
  que ya existen en `api/errors.py`.
- Bad, porque trae maquinaria pensada para APIs públicas con muchos
  consumidores (`application/problem+json`, URIs resolubles) que esta app no
  tiene.

## Consequences

- Good: un sitio migrado y uno sin migrar responden con la misma forma de
  JSON (`error`, `detail`, `data` opcional) — el cliente no necesita saber
  cuál es cuál, solo intentar el catálogo y caer al `detail` si el código no
  está.
- Good: agregar un idioma después es trabajo de frontend solamente — el
  catálogo `code → texto` se extiende, el backend no cambia.
- Good: el hallazgo de `require_positive` (duplicado a mano en
  `recurring.py`, `metas.py`, `funds.py`) se corrige de paso, porque migrar
  "monto inválido" una sola vez exige que las cinco puertas compartan la
  misma función.
- Bad / costo: los ~100 sitios restantes quedan en inglés hasta que se
  trabajen uno por uno — deuda explícita, trackeada en
  `.engineer/consolidation.md`, no escondida.
- Bad / costo: sin una convención, el catálogo del frontend crece
  desordenado. Se fija aquí: un código es `snake_case`, nombra la **causa**
  no el mensaje (`category_duplicate_active`, no
  `category_name_already_taken_error`), y no repite el nombre de la clase de
  excepción (una `ValidationError` puede tener cualquier código).

## Confirmation

- `features/016-error-contract/spec.md` AC-1, AC-2, AC-3 fijan tres códigos
  reales cruzando la costura; AC-5 fija que un sitio sin código sigue
  respondiendo en inglés, sin excepción.
- El catálogo del frontend (`frontend/lib/api/error-catalog.ts`) cae a
  `err.message` (el `detail` en inglés) para cualquier código que no
  reconozca — nunca una pantalla en blanco ni un mensaje genérico que
  esconda la causa.
- Revisión de código: un `raise` nuevo con `code=` sigue la convención de
  nombres de este ADR; un reviewer humano o el propio `plan.md` de la
  siguiente feature que toque `services/` la aplica.

---
ac_count: 6
high_priority_count: 4
discovered: 2026-08-18
reviewed: null
---

# Acceptance criteria — 016 error-contract

Descubiertos el 2026-08-18 con el dueño, a partir del roadmap `id:error-contract`
(pedido el 2026-08-04) y de leer el código real de `api/errors.py`,
`domain/errors.py`, `services/categories.py` y los schemas del frontend antes
de preguntar. Dos hallazgos de esa lectura cambiaron el alcance original:

**El piloto no es el aviso del fondo.** `FundPreview.warning` ya lo resuelve
`create-form.tsx` en el frontend con datos estructurados (`crowded`,
`startMonth`), sin leer el string en inglés del servidor; su único
consumidor real es el asistente, que se va a deprecar. El piloto pasa a ser
categoría duplicada y monto inválido, que sí siguen rotos.

**"Monto inválido" solo es alcanzable hoy en un lugar.** Transacciones,
recurrentes, fondos y metas ya bloquean el monto ≤ 0 en el navegador
(`positiveCents`, mensaje en español) — el rechazo del servidor nunca llega
ahí. El diálogo de corregir un movimiento ya guardado no tiene ese candado,
así que es donde el comportamiento se demuestra de verdad, aunque el
código+datos del lado del backend se arregla una sola vez para las cinco
puertas por igual.

---

## AC-1: Categoría duplicada activa se rechaza en español, con el nombre real

**Priority:** high · **Type:** error

El dueño intenta crear una categoría de gasto llamada "Transporte" y ya existe
una activa con ese nombre. Hoy ve, en inglés: *"an expense category named
'Transporte' already exists"*. Después ve un aviso en rojo **bajo el campo
Nombre**: "Ya existe una categoría de gasto llamada «Transporte»". El mismo
patrón aplica a una categoría de ingreso.

## AC-2: Categoría duplicada archivada sugiere restaurar en vez de crear otra

**Priority:** high · **Type:** error

El dueño intenta crear una categoría cuyo nombre ya lo tiene una categoría
**archivada** de la misma dirección. Hoy ve, en inglés, un mensaje distinto al
de AC-1 que ya sugiere restaurar en vez de crear. Después ve, en español, bajo
el campo Nombre: "Ya existe una categoría de gasto archivada llamada
«Transporte». Restaurarla en vez de crear otra." — con el dato de qué acción
lo resuelve, no solo la queja.

## AC-3: Corregir un movimiento a un monto de cero o menos se rechaza en español

**Priority:** high · **Type:** error

El dueño abre un movimiento ya guardado para corregirlo, escribe `0` en Monto y
guarda. Hoy no hay ningún candado en esa pantalla — la corrección viaja al
servidor, que la rechaza en inglés. Después ve un aviso en rojo **bajo el
campo Monto**: "El monto debe ser mayor que cero". El mismo código y el mismo
dato viajan sin importar cuál de las cinco puertas de escritura de monto
(transacción, recurrente, fondo, meta, corrección) dispare el rechazo —
transacciones, recurrentes, fondos y metas ya lo impiden antes de llegar al
servidor, así que ahí el comportamiento no cambia visiblemente; corrección es
donde se ve.

## AC-4: Lo que rechaza Pydantic también llega en español

**Priority:** medium · **Type:** functional

Un campo requerido falta o llega con el tipo equivocado en una petición (por
ejemplo, mandar el monto como texto en vez de número). Hoy el mensaje lo arma
Pydantic solo, en inglés ("field required", "value is not a valid integer").
Después llega en español, con el mismo mecanismo de aviso por campo que ya
existe.

## AC-5: Un error sin código todavía responde con el detalle real, nunca un genérico

**Priority:** high · **Type:** error

El dueño dispara un error que todavía no tiene código propio — uno de los
~100 sitios que esta feature no migra, o un código que el catálogo del
frontend aún no conoce. Ve el mismo `detail` en inglés que ve hoy, tal cual —
nunca un mensaje genérico en español que esconda cuál fue el problema, y
nunca una pantalla en blanco. El respaldo es honesto sobre lo que falta por
migrar, no lo disfraza.

## AC-6: Un error que nadie previó (un bug) responde con un código fijo, y queda en logs

**Priority:** medium · **Type:** error

Un bug real — no un rechazo de dominio — revienta a mitad de una petición.
Hoy el dueño ve `{"detail": "Internal Server Error"}`, en inglés y sin
relación con la forma `{error, detail}` del resto de la API. Después ve
siempre el mismo mensaje: "Ocurrió un error inesperado. Intenta de nuevo.",
con `code: internal_error`. La excepción real — su tipo, su mensaje, dónde
ocurrió — queda registrada en los logs del servidor para que se pueda
diagnosticar; nunca viaja hacia el cliente.

---

## Fuera de este descubrimiento

- **Los ~100 sitios restantes** de `services/`. Quedan con el respaldo de
  AC-5 hasta que se trabajen en el barrido de consolidación aparte.
- **MCP.** Tiene su propio `domain_error_text` y no cruza esta costura — el
  asistente se va a deprecar.
- **`FundPreview.warning` en el backend.** Su único consumidor es el
  asistente; la pantalla ya resuelve el mismo problema por su cuenta.
- **El candado que falta en `transaction-edit-dialog.tsx`.** Que hoy se pueda
  escribir `0` sin aviso antes de guardar es un hueco de validación de la
  012, no un problema de en qué idioma llega el rechazo. AC-3 corrige el
  idioma del rechazo del servidor; no agrega el candado del cliente.
- **Un selector de idioma real.** El catálogo queda listo para sumar otro
  idioma; nadie construye la pantalla para elegirlo todavía.

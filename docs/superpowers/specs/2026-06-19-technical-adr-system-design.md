# Quaestor — Sistema de ADR técnicos (diseño)

**Fecha:** 2026-06-19
**Depende de:** —
**Parte de:** infraestructura del repo (no es un sub-proyecto P0–P7)

---

## Objetivo

Dar a Quaestor un **sistema completo de Architecture Decision Records (ADR) técnicos**: un registro versionado de **propuestas y decisiones de ingeniería** (librerías, esquema de DB, migraciones, diseño de API/transport, auth, estrategia de tests, etc.), separado del registro de **decisiones de producto** que ya existe.

El entregable no es solo una plantilla: es un **guardarraíl** para que cualquier agente Claude que trabaje en Quaestor **registre y respete** las decisiones técnicas en lugar de improvisar. La regla siempre-activa (CLAUDE.md) obliga a usar el sistema; el skill define el cómo.

## Contexto y problema

- Hoy `docs/adr/2026-06-16-quaestor-adrs.md` reúne 24 "ADR", pero todos son **decisiones de producto** (modelo de presupuesto, safe-to-spend, metas…). Están mal etiquetados como ADR.
- No existe ningún lugar para registrar **decisiones técnicas**. Cuando un agente elige (p. ej.) cómo hacer migraciones o qué librería usar, la decisión se pierde o se rehace distinto en la siguiente sesión.
- La práctica recomendada por la comunidad ADR es **separar**: mantener los ADR enfocados en lo arquitectónico/técnico y poner las decisiones de producto en un registro aparte ("Significant Decision Record"). Ver `adr.github.io`, Martin Fowler (*Architecture Decision Record*), InfoQ (*Has Your ADR Lost Its Purpose?*).

## Decisiones de diseño (tomadas en brainstorming)

| # | Decisión | Alternativa descartada |
|---|---|---|
| 1 | ADR técnicos viven en `docs/adr/`, **uno por archivo** (`NNNN-slug.md`) + índice `README.md` | Archivo único creciente; `docs/tdr/` separado |
| 2 | El archivo de producto se **mueve** a `docs/decisions/product-decisions.md` para dejar `docs/adr/` 100% técnico | Dejarlo en `docs/adr/` (desorden) |
| 3 | Formato **Full MADR** | Minimal (Nygard) |
| 4 | **Un registro por decisión con campo `status`**: `proposed` = propuesta viva; `accepted/rejected` = decidido | Flujo de dos etapas RFC → registro |
| 5 | Entrega como **skill de proyecto** versionado: `quaestor/.claude/skills/adr/` | Skill global filtrado por descripción |
| 6 | **Guardarraíl**: `CLAUDE.md` en la raíz apunta al skill (regla siempre activa) | Solo skill, sin regla siempre-activa |
| 7 | **Script determinista** `new_adr.py` numera + crea archivo + actualiza índice | Crear ADR e índice a mano |
| 8 | Contenido del skill y de los ADR en **inglés**; comunicación con el usuario en español | — |

## Alcance

**En:**
- Skill de proyecto `quaestor/.claude/skills/adr/` (SKILL.md, TEMPLATE.md, scripts/new_adr.py).
- `docs/adr/README.md` (índice) y la carpeta lista para `NNNN-slug.md`.
- `CLAUDE.md` en la raíz de Quaestor (regla técnica siempre activa).
- Mover `docs/adr/2026-06-16-quaestor-adrs.md` → `docs/decisions/product-decisions.md`.

**Fuera:**
- Migrar/reescribir los 24 ADR de producto (solo se mueve el archivo, intacto).
- Crear ADR técnicos de contenido real (el sistema arranca vacío; los ADR se escriben cuando haya decisiones).
- Automatización CI (lint de ADR, validación en pre-commit) — backlog.

## Estructura de archivos

```
quaestor/
├── CLAUDE.md                       # NUEVO — regla siempre activa que apunta al skill
├── .claude/skills/adr/
│   ├── SKILL.md                    # workflow + disparadores + reglas
│   ├── TEMPLATE.md                 # plantilla Full MADR (inglés), la copia el script
│   └── scripts/
│       └── new_adr.py              # numera, crea archivo, actualiza índice
├── docs/adr/
│   ├── README.md                   # índice: tabla nº · título · estado · fecha
│   └── (vacío; aquí caen 0001-*.md, 0002-*.md, …)
└── docs/decisions/
    └── product-decisions.md        # archivo de producto movido (24 ADR intactos)
```

## Componente: el skill `adr`

### Descripción (frontmatter)

```
name: adr
description: Record and govern technical/architecture decisions for Quaestor as
  Architecture Decision Records (ADRs) in docs/adr/. Use when making, proposing,
  or revisiting an architecturally-significant technical decision — choosing a
  library, DB schema or migration approach, API/transport design, auth, testing
  strategy — or when the user mentions ADR, decision record, or "why did we do X".
```

### Criterio de disparo (qué amerita ADR)

El skill incluye una guía explícita para no inflar ni omitir:

- **Sí amerita ADR:** elección de librería/framework, estrategia de migraciones, forma del esquema de DB, diseño de API o transport (REST/MCP), modelo de auth, estrategia de tests, límites entre módulos, decisiones con costo de reversión alto o consecuencias dispersas por el código.
- **No amerita ADR:** renombrar variables, formateo, refactors locales sin cambio de contrato, fixes de bugs, decisiones triviales o fácilmente reversibles.

### Workflow (lo que el skill obliga a hacer)

1. **Antes de proponer un cambio técnico:** leer `docs/adr/README.md` y los ADR `accepted` relevantes. Si una decisión ya está tomada, respetarla o registrar un ADR que la **supersede** (no contradecirla en silencio).
2. **Crear ADR:** `uv run .claude/skills/adr/scripts/new_adr.py "<título>"` → genera `NNNN-slug.md` desde `TEMPLATE.md` en estado `proposed` y agrega la fila al índice.
3. **Rellenar** contexto, drivers, opciones consideradas (con pros/contras), decisión y consecuencias.
4. **Decidir:** cambiar `status` a `accepted` (o `rejected`). Si reemplaza a otro ADR, marcar el viejo como `superseded by NNNN` y enlazar ambos.
5. **Mantener el índice** sincronizado (el script lo hace al crear; al cambiar de estado se actualiza la fila).

### Reglas duras (guardarraíles)

- Numeración **estable**: nunca se renumera; los huecos por ADR `rejected` se conservan.
- Un ADR `accepted` **no se edita** en su decisión; se supersede con uno nuevo.
- Todo ADR enlaza al spec/PR/issue que lo motiva cuando exista.

## Componente: plantilla Full MADR (`TEMPLATE.md`)

Contenido en inglés. Estructura:

```markdown
# NNNN. <short title of the decision>

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who>
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

<What is the issue we're seeing that motivates this decision? 2–4 sentences,
framed as a problem or a question.>

## Decision drivers

- <driver / force / constraint>
- <driver / force / constraint>

## Considered options

1. <option A>
2. <option B>
3. <option C>

## Decision outcome

Chosen option: **<option X>**, because <justification — how it best meets the
drivers>.

### Pros and cons of the options

**<option A>**
- Good, because <pro>
- Bad, because <con>

**<option B>**
- Good, because <pro>
- Bad, because <con>

## Consequences

- Good: <positive consequence>
- Bad / cost: <negative consequence, follow-up work, risk>

## Confirmation

<How do we verify the decision is implemented and respected? e.g. a test, a CI
check, a code review item, a doc.>
```

### Estados (ciclo de vida)

```
proposed ──► accepted ──► (deprecated | superseded by NNNN)
   └──────► rejected
```

- `proposed`: el archivo **es la propuesta**, abierta a revisión.
- `accepted` / `rejected`: decidido; mismo archivo.
- `deprecated`: ya no aplica, sin reemplazo directo.
- `superseded by NNNN`: reemplazado por un ADR más nuevo (ambos se enlazan).

## Componente: índice `docs/adr/README.md`

Tabla mantenida por el script:

```markdown
# Architecture Decision Records (technical)

Technical/architecture decisions for Quaestor. Product decisions live in
`docs/decisions/product-decisions.md`.

| #    | Title | Status | Date |
|------|-------|--------|------|
| 0001 | <title> | accepted | YYYY-MM-DD |
```

## Componente: script `scripts/new_adr.py`

Operación determinista (Python 3.12 + uv, como el resto de Quaestor; sin dependencias externas, solo stdlib).

- **Entrada:** título del ADR como argumento.
- **Pasos:**
  1. Escanear `docs/adr/NNNN-*.md`, calcular el siguiente número (4 dígitos, cero-padded; el máximo + 1).
  2. Generar `slug` del título (minúsculas, guiones, sin acentos).
  3. Copiar `TEMPLATE.md` a `docs/adr/NNNN-slug.md`, sustituyendo `NNNN`, título y fecha. Fecha tomada del sistema **en tiempo de ejecución del script** (no del agente).
  4. Insertar la fila en la tabla de `README.md` con estado `proposed`.
- **Salida:** la ruta del archivo creado (para que el agente lo abra y lo rellene).
- **Idempotencia/seguridad:** si el slug ya existe, aborta sin sobrescribir.

## Componente: guardarraíl `CLAUDE.md`

Quaestor hoy no tiene `CLAUDE.md`. Se crea uno con una regla corta y siempre cargada (el resto del archivo puede crecer luego):

```markdown
## Technical decisions

Any architecturally-significant technical decision (library choice, DB schema,
migrations, API/transport design, auth, testing strategy) MUST be recorded as an
ADR in `docs/adr/` using the `adr` skill. Before proposing a technical change,
read the existing ADRs in `docs/adr/` and respect accepted ones (supersede with a
new ADR instead of silently contradicting them).

Product decisions live in `docs/decisions/product-decisions.md` — do not mix them
into `docs/adr/`.
```

## Migración del archivo de producto

- `git mv docs/adr/2026-06-16-quaestor-adrs.md docs/decisions/product-decisions.md`.
- Contenido **intacto** (los 24 ADR de producto siguen igual; solo cambia de carpeta).
- Ajustar cualquier referencia interna si existiera (revisar specs que citen la ruta vieja).

## Validación

- **Script:** una corrida de prueba crea `0001-*.md` con el número correcto, lo registra en el índice, y una segunda corrida produce `0002`. Borrar los de prueba al terminar.
- **Skill:** verificar que el `description` dispara en los escenarios objetivo (mencionar "ADR", "decision record", elegir una librería).
- **Guardarraíl:** confirmar que `CLAUDE.md` queda en la raíz y la regla es legible.
- **Migración:** `docs/adr/` queda sin el archivo de producto; `docs/decisions/product-decisions.md` existe con los 24 ADR.

## Plan de implementación (alto nivel)

1. Crear `quaestor/.claude/skills/adr/` con SKILL.md, TEMPLATE.md y scripts/new_adr.py.
2. Crear `docs/adr/README.md` (índice vacío) y `docs/decisions/`.
3. Mover el archivo de producto con `git mv`.
4. Crear/añadir la regla técnica en `CLAUDE.md`.
5. Probar el script (crear y borrar ADR de prueba), commit.

El detalle paso a paso lo produce el skill `writing-plans`.

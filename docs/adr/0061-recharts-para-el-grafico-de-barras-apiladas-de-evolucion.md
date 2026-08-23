# 0061. Recharts para el gráfico de barras apiladas de Evolución

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Feature 020 (`monthly-expense-trend`, `acs.md` AC-1/AC-2/AC-4) añade una
pestaña "Evolución" a Reportes: un gráfico de barras apiladas (una barra por
mes de los últimos 12, un color por grupo de categoría) más una tabla debajo.
El frontend hoy no tiene ninguna librería de gráficos instalada (confirmado
en `frontend/package.json` y por búsqueda en `frontend/components` y
`frontend/ui`) — esta es la primera vez que Quaestor renderiza un gráfico en
cualquier pantalla, así que la elección fija el patrón para cualquier gráfico
futuro, no solo este.

## Decision drivers

- **Ya se paga el costo de una librería nueva de todos modos** — cero
  gráficos hoy significa que cualquier opción es una dependencia nueva; la
  pregunta es solo cuál.
- **Encajar con el sistema de diseño ya existente, no crear uno paralelo.**
  `frontend/app/globals.css` y `frontend/ui/styles/tokens.css` ya declaran
  `--chart-1` a `--chart-5` (tema claro y oscuro, ADR-0004/0050) — tokens de
  color para gráficos que existen desde antes de esta feature y que ningún
  componente usa todavía. La librería elegida debe leer esos tokens en vez de
  traer su propio sistema de color.
- **El proyecto ya se apoya en el ecosistema shadcn/ui** (`shadcn` es
  dependencia de `frontend/package.json`; `@base-ui/react` para primitivos) —
  una librería de gráficos que ya sea la que ese ecosistema recomienda evita
  un patrón de theming aparte.
- **Debe correr como client component en Next.js 16 + React 19** sin parches
  ni versiones pineadas por incompatibilidad.
- **Necesita barras apiladas de fábrica** — la feature no pide líneas, radar
  ni gráficos de dispersión; una librería que resuelve exactamente ese caso
  con poca configuración es preferible a una de bajo nivel que obliga a
  construirlo a mano.

## Considered options

1. **Recharts.** Verificado contra industria: es la librería que `shadcn/ui`
   usa internamente para su propio componente de gráficos
   (ui.shadcn.com/charts), ~2.4M descargas semanales, soporte nativo de
   barras apiladas, se tematiza con variables CSS (`var(--chart-1)`, etc.),
   compatible con Next.js 16 + React 19 como client component.
2. **visx (Airbnb).** Conjunto de primitivos de bajo nivel sobre D3 — más
   control, pero cada gráfico (ejes, tooltips, leyenda, apilado) se construye
   a mano; sin integración con el sistema de tokens de shadcn.
3. **Nivo.** Componentes de alto nivel también, pero con su propio sistema de
   theming basado en objetos de configuración JS en vez de variables CSS —
   no lee `--chart-1..5` sin una capa de traducción.
4. **Chart.js / react-chartjs-2.** Renderiza sobre `<canvas>`, no SVG — no
   se tematiza con CSS custom properties tan directo (colores se fijan por
   config JS), y una integración React más fina (re-render por props) que un
   wrapper como Recharts.

## Decision outcome

Chosen option: **Recharts**, porque es la única de las cuatro que ya está
integrada, de fábrica, con el patrón de theming vía variables CSS que este
proyecto ya declaró (`--chart-1..5`) antes de que existiera un solo gráfico
que las usara, y porque `shadcn/ui` — el ecosistema del que este proyecto ya
depende — la eligió por la misma razón. Resuelve el caso pedido (barras
apiladas) sin construir apilado, ejes ni tooltip a mano, a diferencia de
visx; y sin una capa de traducción de theming, a diferencia de Nivo o
Chart.js.

### Pros and cons of the options

**Recharts**
- Good: barras apiladas de fábrica; lee `var(--chart-1..5)` directo, sin capa
  de traducción; mismo patrón que `shadcn/ui` ya usa; ~2.4M descargas/semana.
- Bad: una dependencia nueva de todos modos; SVG con muchas series puede
  costar más re-render que canvas en datasets grandes — no es el caso de 12
  barras x ~10 grupos.

**visx**
- Good: control total, sin opiniones de diseño impuestas.
- Bad: cada pieza (apilado, ejes, leyenda) se construye a mano — más código
  y más superficie para bugs, para un caso que una librería de alto nivel ya
  resuelve.

**Nivo**
- Good: también de alto nivel, también SVG.
- Bad: theming propio vía config JS, no vía CSS — no encaja con
  `--chart-1..5` sin traducir; sin precedente de uso en el ecosistema
  shadcn que este proyecto ya adoptó.

**Chart.js / react-chartjs-2**
- Good: muy usado, maduro.
- Bad: canvas en vez de SVG — no se tematiza con variables CSS directamente;
  wrapper de React menos idiomático (colores/datos se pasan como config, no
  como props declarativas por serie).

## Consequences

- Good: el patrón de theming vía `--chart-1..5` que el sistema de diseño ya
  declaraba, sin usar, queda por fin ejercitado — cualquier gráfico futuro
  reusa el mismo patrón sin decidir esto de nuevo.
- Good: cero configuración de theming nueva — Recharts consume los tokens
  CSS existentes tal cual están.
- Bad / cost: una dependencia nueva de frontend (`recharts`) a mantener
  parcheada.
- Bad / cost: hoy solo existen 5 tokens `--chart-N`; con ~10 grupos de
  categoría activos (AC-2), el plan de esta feature extiende la paleta a
  `--chart-1..10` (tema claro y oscuro) en vez de ciclar los 5 existentes —
  decidido con el dueño en CP4 — para que ningún par de grupos comparta color
  en el gráfico apilado. No es una limitación de Recharts, es un hueco del
  sistema de tokens que esta feature es la primera en tropezar y en cerrar.

## Confirmation

`frontend/package.json` lista `recharts` como dependencia; el componente de
la pestaña "Evolución" (feature 020) importa `BarChart`/`Bar` de `recharts` y
sus series leen color de `var(--chart-1)`..`var(--chart-5)` (o la paleta que
el plan de la feature defina para más de 5 grupos), no de valores hex
hard-codeados. Los escenarios de `features/020-monthly-expense-trend/spec.md`
etiquetados como pantalla (AC-4, AC-10) pasan en `vitest` contra ese
componente.

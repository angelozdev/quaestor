# Re-skin "Fintech premium oscuro" del frontend

**Fecha:** 2026-06-20
**Estado:** aprobado (brainstorming)

## Objetivo

Elevar toda la UI del frontend de Quaestor a una estética **fintech premium
oscura** (vibe Linear/Mercury): slate profundo, acento mint, números tabulares
nítidos, tipografía con carácter. Dark por defecto con toggle a un tema claro
pulido.

## Restricciones (no negociables)

- **ADR-0002** — `ui/` es un design system agnóstico. Todo el re-skin se hace
  por **tokens en la app** (`app/globals.css` + `<html>`), sin tocar los
  internals de `ui/`. La app provee el bloque `.dark` y los overrides de marca,
  que es exactamente lo que el contrato anticipa.
- **ADR-0001** — todo el código en inglés (nombres, comentarios).
- **AGENTS.md (frontend)** — leer `node_modules/next/dist/docs/` antes de tocar
  código Next. Hecho: fonts + layout confirmados, API sin cambios relevantes.
- Decisión arquitectónica significativa (extender el contrato de tokens con
  elevación; adoptar dark-first) → se registra en un ADR nuevo.

## Decisiones de diseño

### Modo de color
- **Dark por defecto + claro** vía `next-themes` (`attribute="class"`,
  `defaultTheme="dark"`). Hoy no hay `ThemeProvider` montado — se agrega.
- `<html suppressHydrationWarning>` para evitar el warning de hidratación que
  introduce next-themes al fijar la clase en cliente.

### Paleta (oklch, dos modos)
Dark (default):
- `--background` ≈ `#0E1116`, `--card` ≈ `#161B22`, `--foreground` ≈ `#E6EDF3`
- `--primary` / acento = **mint** ≈ `#3FE0A0` (botones, foco, barras, link activo)
- `--income` verde / `--expense` rojo, recalibrados para contraste sobre slate
- `--border`/`--input` sutiles (blanco a baja opacidad), `--ring` mint
- `--sidebar` un punto más oscuro que el fondo
- chart tokens al tono del nuevo set

Light (toggle): set claro pulido con el mismo mint de acento; conserva la
intención del minimal actual pero más refinado.

### Tokens de elevación (extensión del contrato)
- Nuevos: `--shadow-card` y `--shadow-pop`, definidos por tema (dark/light).
- Reemplazan las 5 sombras `rgba(0,0,0,…)` hardcodeadas que se ven mal en oscuro.

### Tipografía
- Display/heading: **Bricolage Grotesque** (`--font-figtree` → renombrar a
  `--font-heading`/`--font-sans` según corresponda).
- Body: **Manrope**.
- Reemplazan Figtree en `layout.tsx` y en las font vars de `globals.css`.
- `tabular-nums` se mantiene para todos los montos.

### Barrido de hardcodes ("todo de una")
- 5× `boxShadow: rgba(...)` → `var(--shadow-card)`:
  `app/(app)/page.tsx`, `app/(app)/reports/page.tsx`, `app/(auth)/login/page.tsx`,
  `components/to-pay-widget.tsx` (×2).
- `bg-white` en el header móvil de `components/app-shell.tsx` → token.
- Barra de meta en dashboard `background: var(--foreground)` → acento mint.
- Repaso de las 13 páginas tras el cambio de tokens para hardcodes residuales.

### Polish premium
- Hero "Disponible": número en degradado mint + glow radial sutil de fondo.
- Cards: borde 1px + sombra de token + hover-lift suave.
- Sidebar activo: pill mint translúcido.
- Focus rings mint accesibles (sin romper a11y).
- `animate-fade-up` escalonado afinado.
- Toggle de tema con icono lucide en el shell (sidebar desktop + header móvil).

## No-objetivos (YAGNI)
- No cambiar navegación, rutas ni estructura de páginas.
- No tocar data/estado (react-query, `lib/api`).
- No agregar librería de charts.
- No rediseñar formularios campo por campo (heredan tokens).

## Componentes / archivos afectados
- `app/globals.css` — paletas dark/light, fonts, tokens de elevación, acento.
- `app/layout.tsx` — fuentes (Bricolage Grotesque + Manrope), `suppressHydrationWarning`,
  clase dark inicial.
- `app/providers.tsx` — `ThemeProvider` de next-themes.
- `components/theme-toggle.tsx` — nuevo, conmuta dark/light.
- `components/app-shell.tsx` — token en header, pill activo, toggle.
- `app/(app)/page.tsx`, `reports`, `login`, `to-pay-widget` — sombras → token, polish.

## Verificación
- `pnpm build` y `pnpm lint` pasan.
- Revisión visual de las 13 páginas en dark y light (toggle).
- a11y: contraste AA en texto principal, focus visible en interactivos.

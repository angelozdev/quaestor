# 0004. Dark-first theming via next-themes with an app-level elevation token layer

- **Status:** accepted
- **Date:** 2026-06-20
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The frontend ships a single light, monochrome look. We are re-skinning the whole
app to a dark-first "fintech premium" aesthetic (see
`docs/superpowers/specs/2026-06-20-fintech-dark-reskin-design.md`), which requires
two things the app does not have yet: (1) a runtime theme mechanism — there is no
`ThemeProvider` mounted, so `next-themes` (already a dependency, already called by
`ui/components/sonner.tsx`) resolves to `"system"` and no `.dark` class is ever
set; and (2) a single source for card/popover elevation — today shadows are
hardcoded as `rgba(0,0,0,…)` in five places, which look wrong on a dark surface.
How should theming be wired, and where should elevation live, without violating the
`ui/` design-system contract from ADR 0002?

## Decision drivers

- **Respect ADR 0002.** Re-skinning must stay a matter of providing/overriding
  CSS-variable values in the app; `ui/` internals must not be edited.
- **No flash of wrong theme.** Next renders on the server; the initial theme must
  be applied before paint without a hydration mismatch.
- **Single source for elevation.** Shadows must be themeable per mode, not scattered
  as literals that only look right in light mode.
- **Use what is already there.** `next-themes` is an installed dependency the design
  system already assumes ("toggle a `.dark` class — next-themes does this").
- **Low future-maintenance.** New components should fall into the right look by
  default, not require copying shadow literals.

## Considered options

1. **next-themes (class strategy, dark default) + app-level elevation tokens**
   (`--shadow-card`, `--shadow-pop` defined per theme in `app/globals.css`).
2. **Hand-rolled theme toggle** (own `useState` + `localStorage` + manual class on
   `<html>`) with the same elevation tokens.
3. **Solo dark, no toggle** — bake the dark palette as the only `:root` theme, drop
   the provider, keep shadows as literals.

## Decision outcome

Chosen option: **next-themes (class strategy, `defaultTheme="dark"`) plus an
app-level elevation token layer**, because it satisfies every driver at once. The
theme is applied via the `.dark` class exactly as the `ui/` contract anticipates
(ADR 0002), so this is the app *exercising* the contract, not changing it.
next-themes handles SSR-safe application and persistence, avoiding the
flash-of-wrong-theme that a hand-rolled toggle (option 2) would have to re-solve.
Elevation becomes two tokens defined per theme — added in the **app** layer
(`app/globals.css`), consumed by **app** components; they are not added to the `ui/`
token contract, so ADR 0002's portable surface is unchanged. Option 3 throws away
the toggle the design called for and leaves elevation un-themed.

### Pros and cons of the options

**next-themes + elevation tokens (chosen)**
- Good, because it reuses an installed dependency the DS already assumes, and fixes
  Sonner's empty `useTheme()` as a side effect.
- Good, because SSR theming and persistence are handled; `suppressHydrationWarning`
  on `<html>` is the only concession.
- Good, because elevation is one themeable source; future shadows reference a token
  instead of pasting `rgba(...)`.
- Bad, because it adds `suppressHydrationWarning` on `<html>` and a provider to the
  tree.

**Hand-rolled toggle**
- Good, because no provider abstraction.
- Bad, because it re-implements SSR-safe application, persistence, and system-pref
  sync that next-themes already gives — more code, more ways to get the flash wrong.

**Solo dark, no toggle**
- Good, because simplest possible wiring.
- Bad, because it drops the light theme the design requires and leaves shadows as
  per-call literals.

## Consequences

- Good: a dark-first app with a working light toggle, themed elevation, and Sonner
  reading the real theme — all within ADR 0002's contract.
- Good: re-skin/extension is now "override token values" + "reference a shadow
  token", a pattern future work follows.
- Bad / cost: `<html suppressHydrationWarning>` is required; the elevation tokens are
  an app convention contributors must use instead of hardcoding shadows.
- Relation to ADR 0002: builds on it (app provides the `.dark` block, brand values,
  and its own non-contract tokens); does not supersede it. The `ui/` token contract
  is untouched.

## Confirmation

- `app/providers.tsx` mounts `ThemeProvider` (`attribute="class"`,
  `defaultTheme="dark"`); `app/layout.tsx` sets `suppressHydrationWarning` on `<html>`.
- No `boxShadow: ...rgba(0,0,0` literals remain in `app/` or `components/` — card
  elevation references `var(--shadow-card)` / `var(--shadow-pop)` (grep check).
- `ui/**` is unchanged by the re-skin; ADR 0002's ESLint boundary still passes.
- Code-review checklist: new card-like surfaces reference an elevation token, not a
  shadow literal.

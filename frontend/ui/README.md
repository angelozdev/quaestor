# `ui/` — design system

App-agnostic UI building blocks. This folder is decoupled enough that it could be
copied into another app — or extracted into a workspace package — with effectively
no code changes. Decision recorded in
[`docs/adr/0002`](../../docs/adr/0002-app-agnostic-frontend-design-system-in-ui-module.md).

## The rule

`ui/` depends only on **React, Tailwind, and generic UI libraries**
(`@base-ui/react`, `class-variance-authority`, `lucide-react`, `next-themes`,
`sonner`, `clsx`, `tailwind-merge`). It must **never** import app or domain code:

- ❌ `@/lib/*` (e.g. `@/lib/api`, `@/lib/money`)
- ❌ `@/app/*`
- ❌ `@/components/*` (those are domain components)
- ❌ `@/hooks/*`

This is enforced mechanically by an ESLint `no-restricted-imports` boundary scoped
to `ui/**` (see `eslint.config.mjs`). `pnpm lint` fails if the rule is broken.

Domain-specific components (anything that knows about transactions, money, auth, …)
belong in `components/`, **not** here.

## Layout

```
ui/
  index.ts            Public API — import from "@/ui"
  lib/cn.ts           Self-contained class-name merge helper
  styles/tokens.css   Design-token contract: @theme mapping + default theme
  components/          Primitives (button, card, input, badge, table, tabs, …)
```

## Usage

```tsx
import { Button, Card, CardHeader, CardTitle } from "@/ui"
```

## Tokens are a contract

`styles/tokens.css` declares the CSS variables every component reads (`--primary`,
`--muted-foreground`, `--radius`, `--font-heading`, …) plus a neutral default theme.
The consuming app *provides values* — it overrides those variables in its own global
stylesheet; it never edits component internals to re-skin.

The app must also:

1. Toggle a `.dark` class to switch themes (next-themes handles this).
2. Provide a `.dark { … }` override block for dark mode (components ship `dark:`
   utilities; the palette is the app's call).

In this repo, `app/globals.css` imports the contract and adds Quaestor's brand:

```css
@import "../ui/styles/tokens.css";
```

## Adding components with shadcn

`components.json` points shadcn here:

- `ui` → `@/ui/components`
- `utils` → `@/ui/lib/cn`

So `pnpm dlx shadcn add <component>` drops new primitives straight into `ui/`.

## Extracting to a package later

The layout maps 1:1 onto a `packages/ui` workspace package (the repo already has a
pnpm workspace). To upgrade the lint boundary into a hard dependency-graph boundary:
move `ui/` to `packages/ui/src`, add a `package.json` (`@quaestor/ui`), and repoint
`@/ui` → `@quaestor/ui`. No component code changes — that's the point of keeping this
module self-contained.

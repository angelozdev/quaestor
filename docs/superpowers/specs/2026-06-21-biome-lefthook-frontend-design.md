# Biome + Lefthook for Frontend Format & Lint

- **Date:** 2026-06-21
- **Status:** draft
- **Deciders:** Angelo
- **Related:** docs/adr/0002 (ui/ design-system boundary), docs/adr/0003 (pnpm)

## Goal

Replace the current ESLint flat config (`frontend/eslint.config.mjs`) with a
single, fast, opinionated toolchain based on **Biome** (formatter + linter) and
**Lefthook** (pre-commit hook runner). Eliminate JS-toolchain plugin churn,
speed up `pnpm lint` / `pnpm format`, and keep the import-boundary invariant
that protects the `ui/` design system (ADR-0002).

In scope: `frontend/` only. Backend (Python) already lives under a separate
toolchain discussion and is out of scope here.

## Architecture

### Files (added)

```
frontend/
├── biome.json          # format + lint + organize-imports in one config
└── lefthook.yml        # pre-commit hook (biome check --write on staged files)
```

### Files (removed)

```
frontend/
└── eslint.config.mjs   # superseded by biome.json
```

### Files (modified)

```
frontend/
└── package.json        # swap scripts; add @biomejs/biome + lefthook as devDeps
```

### Stack

- **`@biomejs/biome` v2.x** — single Rust binary for format, lint, and import
  organization. Replaces both ESLint and Prettier.
- **`lefthook` v1.x** — Go-based git hook manager. Faster than Husky, no JS
  dependency for the hook layer itself, declarative YAML.
- **pnpm** stays as the package manager (per ADR-0003). `packageManager` field
  in `package.json` is unchanged.

## Configuration

### `frontend/biome.json`

```jsonc
{
  "$schema": "https://biomejs.dev/schemas/2.x/schema.json",
  "files": {
    "includes": [
      "**",
      "!**/node_modules",
      "!**/.next",
      "!**/out",
      "!**/build",
      "!**/next-env.d.ts",
      "!**/tsconfig.tsbuildinfo"
    ]
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "correctness": {
        "noUnusedImports": "error",
        "noUnusedVariables": "error"
      },
      "style": {
        "useImportType": "error",
        "useNodejsImportProtocol": "error"
      },
      "suspicious": {
        "noExplicitAny": "warn"
      }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100,
    "lineEnding": "lf"
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "asNeeded",
      "trailingCommas": "all",
      "arrowParentheses": "always"
    }
  },
  "assist": {
    "actions": {
      "source": {
        "organizeImports": "on"
      }
    }
  },
  "overrides": [
    {
      "includes": ["ui/**/*.{ts,tsx}"],
      "linter": {
        "rules": {
          "style": {
            "noRestrictedImports": {
              "level": "error",
              "options": {
                "paths": {
                  "@/app":   "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/app/*": "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/lib":   "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/lib/*": "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/components":   "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/components/*": "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/hooks":   "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks.",
                  "@/hooks/*": "ui/ is the app-agnostic design system (ADR-0002): do not import @/app, @/lib, @/components, or @/hooks."
                }
              }
            }
          }
        }
      }
    }
  ]
}
```

### `frontend/lefthook.yml`

```yaml
pre-commit:
  parallel: true
  commands:
    biome-check:
      glob_strict: false
      run: pnpm biome check --write --no-errors-on-unmatched --files {staged_files}
      stage_fixed: true
```

`stage_fixed: true` re-stages any files Biome auto-fixed, so the commit
captures the corrected version (not a still-broken file that the hook quietly
patched).

### `frontend/package.json` scripts

Replace the existing `lint` script; add the rest:

```jsonc
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint":          "biome lint .",
  "format":        "biome format --write .",
  "format:check":  "biome format .",
  "check":         "biome check --write .",
  "check:ci":      "biome ci .",
  "prepare":       "lefthook install"
}
```

Dev deps to add:
- `@biomejs/biome`
- `lefthook`

Dev deps to remove:
- `eslint`
- `eslint-config-next`

## Import-boundary invariant (ADR-0002)

The current `eslint.config.mjs` enforces: files under `frontend/ui/**` must
not import from `@/app`, `@/lib`, `@/components`, or `@/hooks` (path aliases).
This is the primary automated guard for the app-agnostic design system
declared in ADR-0002.

The migration moves this rule into Biome's
`style.noRestrictedImports`, scoped to `ui/**/*.{ts,tsx}` via `overrides`.
Biome v2 supports the `paths` map form (alias → message), which is
functionally equivalent to ESLint's `patterns[].group` form for the alias
paths we need. The invariant is preserved.

## Migration steps

1. Create ADR: `docs/adr/0007-biome-and-lefthook-as-frontend-format-lint.md`,
   following the structure of ADR-0003.
2. `pnpm add -D @biomejs/biome lefthook` in `frontend/`.
3. Write `frontend/biome.json` (config above).
4. Write `frontend/lefthook.yml` (config above).
5. Update `frontend/package.json` scripts; add `prepare` script.
6. `pnpm install` (registers `lefthook install` via `prepare`).
7. Run `pnpm check` once over the whole repo. Biome will reformat and
   reorganize imports across the codebase. Review the diff.
8. Commit as **`chore(frontend): apply biome formatting`** — isolated commit
   so the diff is reviewable and revertable.
9. Delete `frontend/eslint.config.mjs`.
10. `pnpm remove eslint eslint-config-next` and any peer-only deps that fall
    out (Next.js does not require ESLint to run).
11. Verify: `pnpm lint`, `pnpm format:check`, and a sample commit (with a
    staged TSX file) trigger the hook and pass.
12. Confirm: a file under `frontend/ui/` that imports `@/lib/...` produces
    the boundary error.

## Risks & mitigations

- **Large reformatting diff on first run.** Mitigation: isolated commit, run
  `git diff --stat` before committing to gauge scope.
- **Biome v2 `noRestrictedImports` does not support glob groups.** We use
  the `paths` alias map form, which fully covers the alias surface used by
  the project. If a future contributor adds a non-aliased boundary, they
  must extend the map.
- **Hook blocks a contributor who has `pnpm install` but no hook install.**
  Mitigation: `prepare` script in `package.json` ensures `lefthook install`
  runs after every `pnpm install`, so fresh clones are wired automatically.
- **CI does not exist yet (per ADR-0003).** When CI is added, it must run
  `pnpm check:ci` (no `--write`) and fail on any lint, format, or import
  error. Tracked as a follow-up in the new ADR.
- **Next 16 breaking changes** (per `frontend/AGENTS.md`). Biome v2's
  TypeScript and JS parsing is current enough to handle Next 16 + React 19
  + App Router; no Next-specific plugins are required because we do not use
  ESLint's React Hooks plugin or Next-specific rules (the original config
  also did not enable either).

## Confirmation

- `pnpm check` returns 0 on a clean tree.
- `pnpm lint` and `pnpm format:check` both return 0.
- A `git commit` with a staged `frontend/lib/query.ts` file runs the hook
  and either passes or auto-fixes + re-stages.
- A file under `frontend/ui/` importing `@/lib/foo` fails with the
  ADR-0002 boundary message.
- `frontend/eslint.config.mjs` no longer exists; `eslint` and
  `eslint-config-next` are no longer in `package.json` devDependencies.
- ADR-0007 is committed.
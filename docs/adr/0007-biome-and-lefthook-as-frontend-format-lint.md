# 0007. Biome and Lefthook as the frontend format and lint toolchain

- **Status:** accepted
- **Date:** 2026-06-21
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The frontend currently uses ESLint via a flat config (`eslint.config.mjs`)
that extends `eslint-config-next`. There is no separate formatter, so style
is whatever each contributor or agent happens to leave behind. The
`eslint.config.mjs` does enforce one architectural invariant — files under
`frontend/ui/**` must not import from `@/app`, `@/lib`, `@/components`, or
`@/hooks` (per ADR-0002) — but everything else (formatting, unused-import
cleanup, basic correctness checks) relies on individual discipline. What
single tool should own format + lint + import organization for the frontend,
and how do we keep the ADR-0002 boundary enforced after the change?

## Decision drivers

- **Speed and developer experience.** Biome is a single Rust binary that
  formats and lints in one pass and is materially faster than ESLint +
  Prettier on cold runs.
- **Single config, single tool.** Format, lint, organize-imports, and the
  import-boundary rule all live in one `biome.json` file. No plugin chain,
  no `.eslintrc` + `.prettierrc` + `eslint-plugin-*` matrix.
- **Architectural invariant must survive the migration.** ADR-0002's
  `ui/` design-system boundary must still fail the build if violated.
  Biome v2's `style.noRestrictedImports` (with `paths` map) covers the
  alias-based boundary that the current ESLint rule enforces.
- **Pre-commit enforcement.** Hooks must run on every commit and re-stage
  auto-fixes, so contributors (and agents) cannot land unformatted code.
  Lefthook is faster than Husky, config is YAML, no JS dependency in the
  hook layer.

## Considered options

1. Keep ESLint, add Prettier.
2. Adopt Biome + Lefthook, remove ESLint.
3. Adopt Biome + Husky.

## Decision outcome

Chosen option: **Biome + Lefthook, remove ESLint**, because it satisfies
all decision drivers with one tool for format/lint and one declarative
YAML hook.

Concretely:

1. Add `@biomejs/biome` and `lefthook` as devDependencies in
   `frontend/`.
2. Add `frontend/biome.json` covering format, lint rules (recommended +
   `noUnusedImports`, `noUnusedVariables`, `useImportType`,
   `useNodejsImportProtocol`), and an `overrides` block that scopes
   `style.noRestrictedImports` to `ui/**/*.{ts,tsx}` with the ADR-0002
   alias map.
3. Add `frontend/lefthook.yml` running `pnpm biome check --write
   --no-errors-on-unmatched --files {staged_files}` with `stage_fixed:
   true` on `pre-commit`.
4. Replace the `lint` script in `frontend/package.json` with the
   Biome-based scripts (`lint`, `format`, `format:check`, `check`,
   `check:ci`) and add `prepare: lefthook install` so fresh clones wire
   the hook automatically.
5. Delete `frontend/eslint.config.mjs` and remove `eslint` and
   `eslint-config-next` from devDependencies.
6. Run `pnpm check` once across the repo and commit the formatting
   sweep as an isolated chore commit so the diff is reviewable.

### Pros and cons of the options

**ESLint + Prettier**
- Good, because every contributor already knows it.
- Bad, because two configs, two binaries, and Biome is materially
  faster; ESLint's Next-specific rules are not in use today, so nothing
  of value is lost by dropping it.

**Biome + Lefthook**
- Good, because format + lint + import-boundary in one config, one
  binary; the boundary rule moves cleanly into
  `style.noRestrictedImports`.
- Good, because Lefthook's YAML config keeps the hook layer free of JS
  deps and `stage_fixed` prevents half-fixed commits.
- Bad, because the first `pnpm check` reformats many files; mitigated by
  an isolated chore commit.
- Bad, because Biome's plugin ecosystem is smaller than ESLint's; we do
  not currently rely on any plugins.

**Biome + Husky**
- Good, because Husky is the de facto standard.
- Bad, because Husky requires JS in the hook layer (the `lefthook`
  binary is faster and self-contained), and Husky v9's lifecycle is
  more verbose than a single YAML file.

## Consequences

- Good: single tool owns format + lint + import organization; pre-commit
  hook enforces it; the ADR-0002 boundary is preserved.
- Good: `pnpm lint` and `pnpm check` are faster than the previous
  `pnpm lint` (ESLint only).
- Cost: one-time large diff from the initial `pnpm check` sweep —
  isolated chore commit keeps the history readable.
- Cost: contributors need Lefthook's hook installed; `prepare` script
  handles this on `pnpm install`.
- Cost / follow-up — **CI:** no CI exists yet. When CI is added, it
  must run `pnpm check:ci` and fail on any lint, format, or boundary
  violation. Tracked here as pending follow-up.

## Confirmation

- `pnpm check`, `pnpm lint`, and `pnpm format:check` all return 0 on a
  clean tree.
- A `git commit` with a staged TS file runs the pre-commit hook,
  auto-fixes where applicable, and re-stages the fixed file.
- A file under `frontend/ui/` that imports `@/lib/foo` fails with the
  ADR-0002 boundary message.
- `frontend/eslint.config.mjs` no longer exists; `eslint` and
  `eslint-config-next` are gone from `frontend/package.json`.
- ADR-0007 is committed.
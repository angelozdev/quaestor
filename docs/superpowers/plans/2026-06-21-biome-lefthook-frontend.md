# Biome + Lefthook for Frontend Format & Lint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ESLint with Biome (format + lint) and add Lefthook as a pre-commit hook runner on the frontend, preserving the `ui/` design-system import boundary from ADR-0002.

**Architecture:** Single Rust binary (Biome) replaces both ESLint and Prettier. A YAML-based hook runner (Lefthook) executes `biome check --write` on staged files before each commit. The import-boundary rule moves from `eslint.config.mjs` to Biome's `style.noRestrictedImports`, scoped to `ui/**` via an `overrides` block.

**Tech Stack:** `@biomejs/biome` v2.x, `lefthook` v1.x, pnpm (existing, ADR-0003).

**Spec:** `docs/superpowers/specs/2026-06-21-biome-lefthook-frontend-design.md`

## Global Constraints

- Frontend-only change. Backend Python toolchain is out of scope.
- pnpm is the only allowed package manager (ADR-0003). Use `pnpm add` / `pnpm remove`, never `npm` or `yarn`.
- The `ui/` design-system import boundary (ADR-0002) must remain enforced after migration. Files under `frontend/ui/**/*.{ts,tsx}` may not import from `@/app`, `@/app/*`, `@/lib`, `@/lib/*`, `@/components`, `@/components/*`, `@/hooks`, `@/hooks/*`.
- Biome formatter settings (locked by the spec, do not deviate):
  - `quoteStyle: "double"`
  - `semicolons: "asNeeded"`
  - `lineWidth: 100`
  - `indentStyle: "space"`, `indentWidth: 2`
  - `trailingCommas: "all"`
  - `arrowParentheses: "always"`
- Commit messages follow Conventional Commits (`chore(frontend): …`, `docs(adr): …`, etc.).

---

## File Structure

**Created:**
- `docs/adr/0007-biome-and-lefthook-as-frontend-format-lint.md` — the ADR that records the decision (follow the structure of ADR-0003).
- `frontend/biome.json` — format + lint + import boundary config.
- `frontend/lefthook.yml` — pre-commit hook definition.

**Modified:**
- `frontend/package.json` — replace `lint` script, add `format`, `format:check`, `check`, `check:ci`, `prepare`; swap devDeps.

**Deleted:**
- `frontend/eslint.config.mjs` — superseded by `biome.json`.
- `frontend/node_modules/eslint/**` and any leftover `eslint-config-next` files (cleaned by `pnpm remove`).

---

### Task 1: Write ADR-0007

**Files:**
- Create: `docs/adr/0007-biome-and-lefthook-as-frontend-format-lint.md`

**Context:** ADRs in this repo follow a fixed structure (see ADR-0003). Use it as a template. The ADR records *why* the toolchain change was made so future contributors do not re-litigate it.

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0007-biome-and-lefthook-as-frontend-format-lint.md` with the following content:

```markdown
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
```

- [ ] **Step 2: Commit the ADR**

```bash
cd /Users/angelozdev/me/quaestor
git add docs/adr/0007-biome-and-lefthook-as-frontend-format-lint.md
git commit -m "docs(adr): 0007 — biome + lefthook as frontend format/lint toolchain"
```

Expected: one new commit on `main`, no other changes.

---

### Task 2: Install Biome and Lefthook, write config files

**Files:**
- Create: `frontend/biome.json`
- Create: `frontend/lefthook.yml`
- Modify: `frontend/package.json` (scripts + devDeps)
- Create: `frontend/biome.json` (overrides block for `ui/` boundary — part of the same file)

**Context:** This task installs the toolchain and lays down the config files but does **not** apply the formatter sweep (that is its own task so the diff stays reviewable).

- [ ] **Step 1: Install devDependencies**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm add -D @biomejs/biome lefthook
```

Expected: `pnpm-lock.yaml` updated, `package.json` devDependencies now includes both packages with pinned versions.

- [ ] **Step 2: Verify install**

```bash
pnpm exec biome --version
pnpm exec lefthook version
```

Expected: both commands print a version (Biome prints something like `2.x.y`, Lefthook prints its version).

- [ ] **Step 3: Write `frontend/biome.json`**

Create `frontend/biome.json` with the following exact content:

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

- [ ] **Step 4: Write `frontend/lefthook.yml`**

Create `frontend/lefthook.yml` with the following exact content:

```yaml
pre-commit:
  parallel: true
  commands:
    biome-check:
      glob_strict: false
      run: pnpm biome check --write --no-errors-on-unmatched --files {staged_files}
      stage_fixed: true
```

- [ ] **Step 5: Update `frontend/package.json` scripts**

Open `frontend/package.json`. Replace the `"scripts"` block with:

```json
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

Leave `dependencies` and `devDependencies` alone — `pnpm add` already added `@biomejs/biome` and `lefthook` to `devDependencies`.

- [ ] **Step 6: Run `pnpm install` to trigger `prepare`**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm install
```

Expected: `lefthook install` runs as part of the `prepare` lifecycle and creates `.git/hooks/pre-commit`. Verify:

```bash
ls -la .git/hooks/pre-commit
head -5 .git/hooks/pre-commit
```

Expected: file exists, first line is the Lefthook shebang (`#!/usr/bin/env bash` or similar).

- [ ] **Step 7: Verify Biome can read the config**

```bash
pnpm exec biome check --help
pnpm exec biome lint . 2>&1 | head -20
```

Expected: `biome lint .` runs and prints lint findings across the repo (some will exist on the unformatted/unlinted tree — that is normal; Task 3 sweeps them). Crucially, the command **must not** error on the config file itself.

- [ ] **Step 8: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add frontend/biome.json frontend/lefthook.yml frontend/package.json frontend/pnpm-lock.yaml
git status
git commit -m "chore(frontend): add biome + lefthook config"
```

Expected: commit includes `biome.json`, `lefthook.yml`, updated `package.json`, and updated `pnpm-lock.yaml`. No `.ts`/`.tsx` source files are part of this commit.

---

### Task 3: Apply Biome format + lint sweep

**Files:**
- Modify: any `.ts`, `.tsx`, `.js`, `.mjs`, `.json`, `.css` file under `frontend/` that Biome reformats or reorganizes imports in.

**Context:** Running `pnpm check` reformats every file that does not match the Biome config. This produces a large diff; isolating it in one chore commit makes the change reviewable and trivially revertable.

- [ ] **Step 1: Run the formatter sweep**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm check
```

Expected: Biome prints a list of files it modified (formatting, import order, or lint fixes). Exit code 0 if everything was auto-fixed, non-zero if some fixes require manual intervention.

- [ ] **Step 2: Inspect the diff size**

```bash
cd /Users/angelozdev/me/quaestor
git diff --stat
```

Expected: a multi-file diff. If the diff is suspiciously small (<5 files for a project this size), re-run with `--verbose` to confirm Biome saw all files:

```bash
pnpm exec biome check . --verbose
```

- [ ] **Step 3: Verify no source files were deleted**

```bash
cd /Users/angelozdev/me/quaestor
git status --short | grep '^ D' || echo "no deletions"
```

Expected: `no deletions` (Biome reformats in place; it does not delete files).

- [ ] **Step 4: Verify biome now passes on the tree**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm lint
pnpm format:check
```

Expected: both commands exit 0 with no output. If `pnpm lint` reports issues (e.g. unused imports Biome could not auto-fix), resolve them manually before committing.

- [ ] **Step 5: Sanity-check the build still passes**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm build
```

Expected: Next.js build succeeds. If it fails, the failure is unrelated to format changes (Biome does not rewrite semantics) — investigate the error before committing.

- [ ] **Step 6: Commit the sweep**

```bash
cd /Users/angelozdev/me/quaestor
git add -A frontend/
git status
git commit -m "chore(frontend): apply biome formatting and import-organization sweep"
```

Expected: one chore commit touching only files under `frontend/`. No docs, no backend, no root config files.

---

### Task 4: Remove ESLint

**Files:**
- Delete: `frontend/eslint.config.mjs`
- Modify: `frontend/package.json` (devDependencies)
- Modify: `frontend/pnpm-lock.yaml` (cleaned by `pnpm remove`)

**Context:** Now that Biome owns format + lint and the ADR-0002 boundary, ESLint is dead weight. Remove the config file and the devDeps.

- [ ] **Step 1: Delete the ESLint config file**

```bash
cd /Users/angelozdev/me/quaestor/frontend
rm eslint.config.mjs
ls eslint.config.mjs 2>&1 || echo "removed"
```

Expected: `removed`.

- [ ] **Step 2: Uninstall ESLint devDependencies**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm remove eslint eslint-config-next
```

Expected: `package.json` no longer lists `eslint` or `eslint-config-next` in `devDependencies`. `pnpm-lock.yaml` updated.

- [ ] **Step 3: Verify no script references ESLint**

```bash
cd /Users/angelozdev/me/quaestor/frontend
grep -nE '\beslint\b' package.json pnpm-lock.yaml 2>&1 | head -20 || echo "no eslint references"
```

Expected: either empty output or only benign matches (e.g. `package.json` references from prior history). If any `eslint` script remains, remove it.

- [ ] **Step 4: Verify Biome still works**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm lint
pnpm format:check
```

Expected: both pass (exit 0).

- [ ] **Step 5: Verify the build still passes**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm build
```

Expected: Next.js build succeeds. Removing ESLint does not affect the build, but verify to be sure.

- [ ] **Step 6: Commit**

```bash
cd /Users/angelozdev/me/quaestor
git add -A frontend/
git status
git commit -m "chore(frontend): remove eslint in favor of biome"
```

Expected: one commit that removes `eslint.config.mjs`, drops `eslint` / `eslint-config-next` from `package.json`, and updates `pnpm-lock.yaml`.

---

### Task 5: Verify pre-commit hook and ADR-0002 boundary end-to-end

**Files:**
- Temporary files created and reverted during verification (do not commit them).

**Context:** Last step. Confirm that (a) the pre-commit hook fires on a real commit and re-stages auto-fixes, and (b) the ADR-0002 boundary rule actually fires when a `ui/` file tries to import from `@/lib`.

- [ ] **Step 1: Confirm the hook is installed**

```bash
cd /Users/angelozdev/me/quaestor
cat .git/hooks/pre-commit | head -20
```

Expected: file starts with a Lefthook shebang, references `lefthook run pre-commit` or similar.

- [ ] **Step 2: Stage a small intentional formatting violation**

Pick an existing file under `frontend/` and re-introduce a violation. Example using `frontend/lib/query.ts` (current state from `git show HEAD:frontend/lib/query.ts`):

```bash
cd /Users/angelozdev/me/quaestor
cp frontend/lib/query.ts /tmp/query.ts.bak
# Replace one line with a clearly-wrong format, e.g. double-space indent:
# Find any line like `  const x = ...` and change to `    const x = ...`.
# Do NOT change semantics.
```

If editing by hand is impractical, run:

```bash
pnpm exec biome format --write --help >/dev/null  # sanity
# Use sed to add a trailing space to a non-semantic line in frontend/lib/query.ts
```

- [ ] **Step 3: Stage the file and attempt a commit (expect auto-fix + re-stage)**

```bash
cd /Users/angelozdev/me/quaestor
git add frontend/lib/query.ts
git commit -m "test: verify pre-commit biome hook"
```

Expected: Lefthook runs `pnpm biome check --write --no-errors-on-unmatched --files {staged_files}`, Biome reformats the file, Lefthook re-stages the fix (`stage_fixed: true`), and the commit proceeds. Verify with:

```bash
git show HEAD --stat | head -10
git show HEAD:frontend/lib/query.ts | head -5
```

Expected: the file in the commit is the *fixed* version, not the broken one.

- [ ] **Step 4: Restore the original file and amend the test commit**

```bash
cd /Users/angelozdev/me/quaestor
cp /tmp/query.ts.bak frontend/lib/query.ts
git add frontend/lib/query.ts
git commit --amend --no-edit
```

Expected: amend replaces the broken-version file in the commit with the original. The commit message stays the same.

If you prefer to keep history clean, instead use:

```bash
git reset --soft HEAD~1
git restore --staged --worktree frontend/lib/query.ts
git status
```

Then re-commit without the test message:

```bash
git commit -m "chore(frontend): verify biome hook (no-op)"
```

Either path leaves the working tree clean.

- [ ] **Step 5: Verify the ADR-0002 boundary rule fires**

Pick a file under `frontend/ui/` (the design-system layer). Temporarily add a forbidden import. Example using `frontend/ui/button.tsx` if it exists; otherwise any `.tsx` file under `frontend/ui/`:

```bash
cd /Users/angelozdev/me/quaestor
ls frontend/ui
# Pick a real file, e.g. frontend/ui/<existing>.tsx
echo 'import { foo } from "@/lib/query";' >> frontend/ui/<chosen>.tsx
```

Run:

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm lint
```

Expected: Biome exits non-zero and prints a violation message containing the ADR-0002 string (`"ui/ is the app-agnostic design system (ADR-0002) …"`).

- [ ] **Step 6: Revert the boundary violation**

```bash
cd /Users/angelozdev/me/quaestor
# Undo the appended import line (use git restore to be safe):
git restore frontend/ui/<chosen>.tsx
pnpm exec biome lint frontend/ui/<chosen>.tsx 2>&1 | head
```

Expected: `pnpm lint` returns 0 for the file after restoration. If the original file had no other violations, output is empty.

- [ ] **Step 7: Final clean state check**

```bash
cd /Users/angelozdev/me/quaestor/frontend
pnpm lint
pnpm format:check
pnpm build
```

Expected: all three exit 0. The migration is complete.

- [ ] **Step 8: Commit any verification artifacts (if needed)**

If you used the "amend" path in Step 4, there is nothing to commit. If you used the "soft reset + new commit" path, the final commit is already in history. Verify the final tree:

```bash
cd /Users/angelozdev/me/quaestor
git status
git log --oneline -10
```

Expected: `git status` is clean. Recent commits include, in order:
1. `docs(adr): 0007 — biome + lefthook as frontend format/lint toolchain`
2. `chore(frontend): add biome + lefthook config`
3. `chore(frontend): apply biome formatting and import-organization sweep`
4. `chore(frontend): remove eslint in favor of biome`
5. (optional) `chore(frontend): verify biome hook (no-op)` — only if Step 4 took the soft-reset path.

---

## Self-Review

**1. Spec coverage:**
- Replace ESLint → Task 4.
- Add Biome + Lefthook → Task 2.
- Preserve `ui/` boundary (ADR-0002) → Task 2 (config), Task 5 (verification).
- Pre-commit hook re-stages auto-fixes → Task 2 (config), Task 5 (verification).
- `pnpm prepare` wires the hook automatically → Task 2 Step 6.
- ADR-0007 records the decision → Task 1.
- Initial format sweep as an isolated chore commit → Task 3.
- Formatter settings locked by spec (quote style, semicolons, lineWidth, etc.) → Task 2 Step 3 (verbatim in `biome.json`).

No gaps found.

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later", "fill in details".
- No "Add appropriate error handling" or "handle edge cases" without code.
- No "similar to Task N" — every step repeats the actual commands and file contents.
- All code blocks are concrete (full `biome.json`, `lefthook.yml`, scripts, ADR body).

No placeholders found.

**3. Type / signature consistency:**
- The only "interface" across tasks is the config file shape. Task 2 writes `biome.json` exactly as the spec mandates. Task 3 invokes `pnpm check` and `pnpm lint` / `pnpm format:check` — these map 1:1 to the scripts declared in Task 2 Step 5. Task 4 uninstalls `eslint` and `eslint-config-next` — these are the exact devDeps the spec says to remove. Task 5 invokes `pnpm lint` against `frontend/ui/`, which exercises the `overrides` block in Task 2.
- No function/method/property names are introduced across tasks (this is a tooling migration, not a feature), so there are no name-drift risks.

No consistency issues found.
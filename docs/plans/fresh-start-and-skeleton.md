# Fresh Start and Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the legacy data in a checked export under `~/.quaestor/legacy/`, then give `rebuild` a released `quaestor` CLI that runs from any folder, resolves its environment, migrates and backs up its store, and fails in a structured way.

**Architecture:** Functional core and imperative shell in concept folders, ported from Aletheia's final layout and renamed to Quaestor. Each skeleton task ports the Aletheia files it names with the deltas it lists; nothing Aletheia-only comes across.

**Tech Stack:** Node 26, pnpm 11.28.8, TypeScript 7.0.2 (type stripping), commander 15.0.0, `@toon-format/toon` 4.4.0, zod 4.6.7, `node:sqlite` with drizzle-orm 1.0.0-rc.5, vitest 5.0.5, oxlint 1.89.0, oxfmt 0.74.0, knip 6.43.0, jscpd 5.4.2, rolldown 1.2.15.

**Spec:** `docs/backlog.md` items 1 (The fresh start) and 2 (The skeleton), under `docs/architecture.md`, `docs/stack.md` and `docs/workflow.md`. Reference implementation, read and never changed: `~/me/aletheia` (`specs/000-skeleton/spec.md`, `specs/000-skeleton/contracts/cli.md`, the "Done as" notes in `specs/000-skeleton/tasks.md`, `src/`, `tests/`, `tools/lint/`).

Both items are named exceptions (shared setup): item 1 has no code and no tests; item 2 has no finance behaviour.

## Who does what

- Claude: the local tag, the copies into `~/.quaestor/legacy/`, the export and check scripts (written, not run), all code, all commits.
- Angelo: `docker start` and `docker stop` of the legacy container and running the scripts against it (`docs/workflow.md`: touching the legacy database), pushing the tag, merging `skeleton`, `pnpm release`.
- This plan and item 1's docs go to `rebuild` directly (docs only). Item 2 is built on branch `skeleton` off `rebuild`, committed after each green step.

## Decisions taken while planning (Angelo may veto)

1. Exit codes 0, 1 and 2, chosen by Angelo on 2026-11-23: 1 means refused (the call was wrong or a rule said no; Claude fixes the call and retries), 2 means failed (the environment broke; Claude stops and tells Angelo). The error is one object on stderr: `error` holding `code` first, then its data, then `message`; TOON by default, one line of JSON when `--json` is anywhere in argv. Commander's parse errors take the same shape with a code derived from commander's (`commander.unknownOption` → `unknown_option`). An error no class names is `unexpected`, exit 2.
2. `pnpm release` runs from a clean green `rebuild`, not `main`, until the backlog item "`rebuild` becomes `main`"; `architecture.md` and that item say so (Task 6).
3. `architecture.md`'s "Tests use `:memory:`" becomes temporary stores: the backup and migration tests must reopen or copy a file, and the opaque store gives a test no way into a `:memory:` one. Under vitest both entry points refuse named environments, as in Aletheia (Task 9).
4. The `just-*` boundary lint rule lands now; the utilities module `src/core/utils/` and its first `just-*` package land with their first consumer (`stack.md`: a dependency enters with the delivery that needs it; knip fails an unused module).
5. `backup` has no `--dry-run`: it changes no data. `--dry-run` arrives with the first write, in recording movements.
6. `--help` and `--version` open no store and print no `env:` line. A bare `quaestor` prints the same help on stdout and exits 0 (commander's default is help on stderr and exit 1).
7. Backups keep the newest 5 copies per env, the copy taken before migrating included, as in Aletheia.
8. Aletheia's final layout, directly: one folder per module holding `<name>.ts`, `<name>.test.ts` and, as needed, `.types.ts`, `.errors.ts`, `.constants.ts`, `.schema.ts`; every failure is an error class. Aletheia's iCloud stage and restructure are skipped.
9. Not ported: the skill copy, spec-id traceability (recording movements decides how feature docs are traced), stdin, time zone and random index in the context, the `date-fns` and `ts-fsrs` lint groups, `no-nested-calls`. `drizzle-kit`, `date-fns` and `just-*` enter with recording movements.
10. The legacy export is JSON Lines with every value as the text of its `row_to_json` rendering, or null, so `bigint` cents and `numeric(18,6)` keep every digit and Node needs no CSV parser.
11. After its check passes, Angelo makes `~/.quaestor/legacy/` read-only (`chmod -R a-w`), so nothing rewrites the export by accident.

## Global Constraints

- Node 26.x, ESM; `"packageManager": "pnpm@11.28.8"`; `saveExact: true`; every library a `devDependency` at the exact version in `docs/stack.md`; `@types/node` 26.6.5, as in Aletheia.
- A dependency is installed by the first task that needs it, never earlier.
- Names: `quaestor` (package and bin), `QUAESTOR_ENV`, `QUAESTOR_DB`, `~/.quaestor/` (release data), `data/` (sources data), `dist/quaestor.js`, `__QUAESTOR_RELEASE__`.
- Layout: `src/core/<concept>/`, `src/shell/<adapter>/<concept>/`, unit barrels reached as `#core/*` and `#shell/*`, relative `.ts` imports inside a unit.
- No code comments. Code, tests, docs and commit messages in English, Conventional Commits. No tables in any `.md`.
- No test touches `data/`, `~/.quaestor/`, the installed `quaestor` or the legacy database. Temp folders come from `tempDir` and are removed.
- Every message a task quotes is built by an error class in its module's `.errors.ts`; tests compare against the literal text.
- Claude never runs `pnpm release`, never merges, never pushes.
- From Task 5 on, `pnpm check` is green before every commit.

## Review Focus

1. Legacy names with emoji, accents or line breaks must come out of the export byte for byte → Task 2's `check.sh` compares account and category names with the live database.
2. A store file that is not SQLite → exit 2 `unexpected`, the file unchanged, no copy left → Task 12, where opening the store first reads it (`node:sqlite` opens such a file without error and fails on first use with `file is not a database`).
3. `QUAESTOR_DB` in a folder that does not exist → exit 2 `unexpected`, nothing created → Task 11.
4. A data folder whose path holds a space → `backup` works and prints the path → Task 9.
5. The release's first run, with no `~/.quaestor/` yet → the folder and the store are created, `env: prod` → Task 9.

---

## Item 1: The fresh start

Facts these tasks rely on (from `docs/handoff.md`, deleted with this plan's commit):

- Container `quaestor-db-1` (Postgres 18) on volume `quaestor_quaestor_pg_data`, stopped, no compose files. Start with `docker start quaestor-db-1`, stop with `docker stop quaestor-db-1`, read with `docker exec -i quaestor-db-1 sh -c 'psql -U "${POSTGRES_USER:-quaestor}" -d "${POSTGRES_DB:-quaestor}"'`. Never write.
- Last write 2026-11-08 21:08 UTC. Final dump: `~/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups/quaestor-legacy-final-2026-11-23.dump`, 74,597 bytes.
- Amounts and balances are integer cents (`bigint`) in the account's currency; `settings.usd_cop` is `numeric(18,6)` (3236.360000); `transaction.transfer_direction` holds `in_` and `out`.
- Tables on `main` (`backend/src/quaestor/domain/models.py`): `account`, `category`, `category_group`, `transaction`, `transaction_tag`, `tag`, `recurring_item`, `recurring_occurrence`, `fund`, `meta`, `meta_amendment`, `meta_contribution`, `settings`, plus `alembic_version`.

### Task 1: Tag `main` and copy the final dump

**Files:** none in the repo; creates `~/.quaestor/legacy/quaestor-legacy-final-2026-11-23.dump`.

- [ ] **Step 1:** `git tag -a legacy-final main -m "Legacy app, frozen on 2026-11-23"`. Verify: `git rev-parse 'legacy-final^{commit}'` prints the same SHA as `git rev-parse main`.
- [ ] **Step 2:** `mkdir -p ~/.quaestor/legacy`, then `cp -p` the dump into it. Verify: `stat -f %z` on the copy prints `74597`, and `shasum -a 256` prints the same hash for the original and the copy.
- [ ] **Step 3:** Hand Angelo `git push origin legacy-final`.

### Task 2: Export every legacy table with a checked manifest

**Files:** creates `~/.quaestor/legacy/export.sh` and `~/.quaestor/legacy/check.sh`; Angelo's run creates `~/.quaestor/legacy/tables/<table>.jsonl` and `~/.quaestor/legacy/manifest.json`.

- [ ] **Step 1: Write `export.sh`** (bash, `set -euo pipefail`):
  - Exits 1 with `export: refused: tables/ already exists` when `~/.quaestor/legacy/tables/` exists, so nothing is exported twice.
  - Waits up to 30 s for `docker exec quaestor-db-1 pg_isready` to succeed (`docker start` returns before Postgres accepts connections), else exits 1 with `export: refused: Postgres is not ready`.
  - Writes everything into `~/.quaestor/legacy/staging/`, first removing a `staging/` left by a failed run, and only when every step succeeded moves `staging/tables` and `staging/manifest.json` into `~/.quaestor/legacy/` and removes the empty `staging/`. A failed run leaves no `tables/`, so it can be rerun.
  - Sends SQL on stdin to `docker exec -i quaestor-db-1 sh -c 'psql -X -q -v ON_ERROR_STOP=1 -A -t -U "${POSTGRES_USER:-quaestor}" -d "${POSTGRES_DB:-quaestor}"'`.
  - Lists the tables with `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;` and writes each to `tables/<table>.jsonl`, one row per line, every value as the text of its `row_to_json` rendering or null (numbers keep every digit; timestamps and booleans come as `row_to_json` writes them):

    ```sql
    SELECT (SELECT json_object_agg(e.key, e.value) FROM json_each_text(row_to_json(r)) e)
    FROM "<table>" r
    ORDER BY r::text;
    ```

  - Writes `manifest.json` with jq. Row counts come from the files (`wc -l`), never from the database; `accounts` comes from `tables/account.jsonl`:

    ```json
    {
      "exportedAt": "<UTC instant>",
      "source": { "container": "quaestor-db-1", "volume": "quaestor_quaestor_pg_data", "lastWrite": "2026-11-08T21:08Z" },
      "format": "tables/<table>.jsonl: one JSON object per row; every value is the text of its row_to_json rendering, or null",
      "dump": { "file": "quaestor-legacy-final-2026-11-23.dump", "bytes": 74597, "sha256": "<hex>" },
      "tables": [{ "name": "account", "file": "tables/account.jsonl", "rows": 11, "sha256": "<hex>" }],
      "accounts": [{ "id": "<id>", "name": "<name>", "currency": "COP", "balance": "<cents>" }]
    }
    ```

- [ ] **Step 2: Write `check.sh`**, whose queries are independent of the export's. It prints `ok: <check>` or `mismatch: <check>: expected <x>, got <y>` per check and exits 1 on any mismatch:
  - `tables`: the live table list (the same `information_schema` query) equals the manifest's names.
  - `rows <table>`: the live `SELECT count(*) FROM "<table>"` equals the manifest's `rows`, for every table.
  - `expected rows`: the manifest gives the row count of every table, and lists `alembic_version`.
  - `sha256 <table>`: each file's sha256 equals the manifest's.
  - `accounts`: the live `SELECT id, name, currency, balance FROM account ORDER BY id` equals the manifest's accounts sorted by numeric id, fields joined by `|` on both sides.
  - `category names`: the live `SELECT id, name FROM category ORDER BY id` equals the same fields from `tables/category.jsonl` (Review Focus 1).
  - `emergency fund`: some manifest account has balance `3000000000` (COP 30,000,000.00).
  - `usd_cop`: the live `SELECT usd_cop::text FROM settings` equals `usd_cop` in `tables/settings.jsonl`, `3236.360000`.
  - `dump`: the copy is 74,597 bytes and its sha256 equals the manifest's.
- [ ] **Step 3:** `bash -n` on both scripts passes.
- [ ] **Step 4:** Hand Angelo `! docker start quaestor-db-1 && bash ~/.quaestor/legacy/export.sh && bash ~/.quaestor/legacy/check.sh; docker stop quaestor-db-1`. Expected: every line `ok:`, exit 0. A mismatch stops the task and goes to Angelo; an expected value is never adjusted to match.
- [ ] **Step 5:** Hand Angelo `! chmod -R a-w ~/.quaestor/legacy`.

### Task 3: `CLAUDE.md`, `LICENSE` and the legacy facts in `docs/`

**Files:** Create `CLAUDE.md`, `LICENSE`. Modify `docs/architecture.md` (Legacy data), `docs/backlog.md`.

- [ ] **Step 1:** `git show main:LICENSE > LICENSE` (MIT, 2026, Angelo Zambrano).
- [ ] **Step 2:** Write `CLAUDE.md`, exactly:

  ```markdown
  # Quaestor

  Before anything else, read `docs/`: `architecture.md`, `stack.md`, `workflow.md` and
  `backlog.md`, then the plan in `docs/plans/` if one is in progress, and
  `docs/features/<name>.md` for the feature at hand. They are the source of truth and
  override this file, which only points at them.
  ```

- [ ] **Step 3:** In `docs/architecture.md` § Legacy data, replace the bullet "Before anything is built, every table is exported once to `~/.quaestor/legacy/` …" with three bullets:
  - On `<export date>` every table was exported once to `~/.quaestor/legacy/`, outside the repo because it is real financial data, and the folder was made read-only. `tables/<table>.jsonl` holds one JSON object per row, every value the text of its `row_to_json` rendering or null (numbers keep every digit); `manifest.json` holds each file's row count and sha256 and each account's stored balance; the final dump and the `export.sh` and `check.sh` that made and checked the export sit next to them.
  - Legacy values are as stored: amounts and balances are integer cents in the account's currency, `settings.usd_cop` has six decimals, and `transaction.transfer_direction` holds `in_` and `out`.
  - The container `quaestor-db-1` (volume `quaestor_quaestor_pg_data`) stays stopped as a frozen copy, with the dump as its fallback. Reading it: `docker start quaestor-db-1`, `docker exec -i quaestor-db-1 sh -c 'psql -U "${POSTGRES_USER:-quaestor}" -d "${POSTGRES_DB:-quaestor}"'`, `docker stop quaestor-db-1`. Nothing writes to it.
- [ ] **Step 4:** In `docs/backlog.md`, delete "1. The fresh start" and renumber the rest.
- [ ] **Step 5:** Commit on `rebuild`: `docs: CLAUDE.md, LICENSE and the legacy export`.

---

## Item 2: The skeleton

Every "Port from" path below is under `~/me/aletheia`. Port means: read the Aletheia file and its test, write the test first with Quaestor's names and this plan's deltas, watch it fail, then port the code.

### Task 4: `pnpm quaestor --help` and `--version` from any folder

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `tsconfig.json`, `vitest.config.ts`
- Create: `src/shell/cli/main/{main.ts,main.types.ts,main.test.ts}`, `src/shell/cli/bin/{bin.ts,bin.constants.ts,bin.test.ts}`
- Create: `tests/support/streams/{streams.ts,streams.types.ts}`, `tests/support/temp-dir/{temp-dir.ts,temp-dir.types.ts,temp-dir.test.ts}`
- Modify: `docs/architecture.md` (Code layout)
- Port from: the same paths, plus `package.json`, `tsconfig.json`, `vitest.config.ts`

**Interfaces:**
- Produces: `main(argv: string[], context: CliContext): Promise<number>`; `type Output = { write(chunk: string): unknown }`; `type CliContext = { stdout: Output; stderr: Output; version: string }` (later tasks add fields); `REPO_ROOT` in `bin.constants.ts`; `captureStream(): CapturedStream` with `CapturedStream = Output & { text(): string }`; `tempDir(prefix: string, onFinished: OnTestFinished = onTestFinished): string`.

- [ ] **Step 1:** `git switch -c skeleton rebuild` (or a worktree on that branch).
- [ ] **Step 2:** Write `package.json`: `"name": "quaestor"`, `"version": "0.0.0"`, `"private": true`, `"type": "module"`, `"engines": { "node": "26.x" }`, `"packageManager": "pnpm@11.28.8"`, `"imports": { "#core/*": "./src/core/*/index.ts", "#shell/*": "./src/shell/*/index.ts" }`, `"bin": { "quaestor": "dist/quaestor.js" }`, `"files": ["dist", "migrations"]`, scripts `"quaestor": "node src/shell/cli/bin/bin.ts"`, `"test": "vitest run"`, `"typecheck": "tsc --noEmit"`. `pnpm-workspace.yaml`: `saveExact: true`. `tsconfig.json` and `vitest.config.ts` as Aletheia's. Verify: `pnpm --version` in the repo prints `11.28.8`.
- [ ] **Step 3:** `pnpm add -D typescript@7.0.2 @types/node@26.6.5 vitest@5.0.5 commander@15.0.0 @commander-js/extra-typings@15.0.0`.
- [ ] **Step 4: Write the failing tests**
  - `temp-dir.test.ts`: `the folder and its contents are gone once the test finishes`; `with the test context's onTestFinished the folder is gone once that test finishes`.
  - `main.test.ts`: `--help prints usage with --env and --json on stdout and exits 0` (`main(['--help'], ctx)` resolves `0`; stdout contains `Usage: quaestor`, `--env <name>` and `--json`; stderr is `''`); `--version from the sources prints dev` (stdout exactly `dev\n`, stderr `''`, `0`).
  - `bin.test.ts`: `the source bin prints help from a folder outside the repo` (`spawnSync(process.execPath, [join(REPO_ROOT, 'src/shell/cli/bin/bin.ts'), '--help'], { cwd: tempDir('quaestor-bin-'), encoding: 'utf8' })` → status 0, stdout contains `--env`, stderr `''`).
- [ ] **Step 5:** `pnpm test` fails: the modules do not exist.
- [ ] **Step 6: Implement.** `main` builds a `Command` from `@commander-js/extra-typings` named `quaestor` with `.version(context.version, '-V, --version')`, `--env <name>` ("use <name>.sqlite in the data folder"), `--json` ("JSON instead of TOON on stdout"), `.exitOverride()` and `.configureOutput({ writeOut, writeErr })` to the context's streams; a `CommanderError` whose exit code is 0 returns 0, anything else is rethrown (Task 8 handles it). `bin.ts`: shebang, `process.exitCode = await main(process.argv.slice(2), { version: DEV_VERSION, stdout: process.stdout, stderr: process.stderr })`, `DEV_VERSION = 'dev'` in `bin.constants.ts` until Task 6 moves it.
- [ ] **Step 7:** `pnpm test` and `pnpm typecheck` pass; `pnpm quaestor --version` prints `dev`.
- [ ] **Step 8:** `docs/architecture.md` § Code layout gains: "Inside a concept folder, one folder per module: `<name>.ts` (logic only), `<name>.test.ts`, and as needed `<name>.types.ts` (every type), `<name>.errors.ts` (every error class), `<name>.constants.ts` (every literal whose meaning is a convention) and `<name>.schema.ts` (zod and Drizzle schemas)."
- [ ] **Step 9:** Commit `feat(cli): quaestor --help and --version from the sources`.

### Task 5: `pnpm check` and the lint boundaries

**Files:**
- Create: `.oxlintrc.json`, `.oxfmtrc.json`, `knip.json`, `.jscpd.json`, `tools/lint/local.ts`, `tools/lint/no-comments.ts`
- Create: `tests/lint/{lint.test.ts,lint.types.ts}`, `tests/checks/checks.test.ts`
- Modify: `package.json` (scripts)
- Port from: the same paths. `local.ts` registers `no-comments` only. Unlike Aletheia, `tools/lint/` is tracked in git.

**Interfaces:**
- Consumes: `tempDir`, `OnTestFinished` (Task 4).
- Produces: `lintFixture(onFinished: OnTestFinished, files: Record<string, string>): LintResult` with `LintResult = { status: number; output: string }`, local to `tests/lint/`.

- [ ] **Step 1:** `pnpm add -D oxlint@1.89.0 @oxlint/plugins@1.89.0 eslint-plugin-sonarjs@4.2.2 oxfmt@0.74.0 knip@6.43.0 jscpd@5.4.2`.
- [ ] **Step 2: Write the failing tests.** `tests/lint/lint.test.ts` is `describe.concurrent`; each case lints a fixture with the repo's oxlint in a temp folder:
  - `fails naming a src/core file that imports node:*` (`src/core/sample/sample.ts` with `import { readFileSync } from 'node:fs'` → status ≠ 0, output contains that path)
  - `fails when src/core imports drizzle-orm or #shell/*`
  - `fails when a file outside src/shell/db imports node:sqlite or drizzle-orm, and passes inside src/shell/db`
  - `fails when a file outside src/core/utils imports a just-* package, and passes inside it` (`import groupBy from 'just-group-by'` fails in `src/shell/cli/sample.ts` and `src/core/sample/sample.ts`, passes in `src/core/utils/sample.ts`)
  - `fails naming a file with a comment, passes a shebang, and reports an oxlint-disable comment itself`
  - `fails a file name that is not kebab-case` (`src/shell/SampleFile.ts`)
  - `fails a function above cognitive complexity 15`
  - `fails when a test file imports %s instead of using tempDir` (`mkdtemp` and `mkdtempSync` from `node:fs`, `mkdtemp` from `node:fs/promises`, in `src/shell/cli/sample.test.ts` and `tests/sample/sample.test.ts`) and `passes mkdtempSync in tests/support/temp-dir and in non-test files`
  - `tests/checks/checks.test.ts`: `pnpm check runs test, lint, format:check, typecheck, dead-code and duplication in order` (`scripts.check` is exactly `pnpm test && pnpm lint && pnpm format:check && pnpm typecheck && pnpm dead-code && pnpm duplication`, and each of the six is a defined script)
- [ ] **Step 3:** `pnpm test` fails on every case above.
- [ ] **Step 4: Configure.** `.oxlintrc.json` is Aletheia's without the `date-fns` and `ts-fsrs` groups and with a `just-*` group ("only src/core/utils wraps just-* packages") everywhere except an override for `src/core/utils/**`. An override's `no-restricted-imports` replaces the top-level one, so each override repeats the groups it keeps. Scripts `lint` (`oxlint`), `format` (`oxfmt`), `format:check` (`oxfmt --check`), `dead-code` (`knip`), `duplication` (`jscpd`), `check`. `.oxfmtrc.json`: `semi: false`, `singleQuote: true`, ignore `**/*.md`, `docs/**`, `.claude/**`, `pnpm-lock.yaml`. `knip.json`: `vitest: true`, plus `ignoreDependencies` only for a package knip reports that only a config file loads. `.jscpd.json` as Aletheia's. Run `pnpm format` once.
- [ ] **Step 5:** `pnpm check` is green.
- [ ] **Step 6:** Commit `chore: pnpm check with lint boundaries, format, dead code and duplication`.

### Task 6: The release entry and the `pnpm release` refusals

**Files:**
- Create: `src/shell/cli/invocation/context/{context.ts,context.types.ts,context.constants.ts,context.test.ts}`, `src/shell/cli/released.ts`, `src/shell/cli/index.ts`, `src/shell/cli/main/main.constants.ts`
- Create: `src/shell/release/index.ts`, `src/shell/release/runner/runner.types.ts`, `src/shell/release/release/{release.ts,release.types.ts,release.constants.ts,release.errors.ts,release.test.ts}`, `tests/support/fake-runner/{fake-runner.ts,fake-runner.types.ts}`
- Modify: `src/shell/cli/bin/{bin.ts,bin.constants.ts}`, `knip.json` (entry `src/shell/cli/released.ts`), `docs/architecture.md` (Release), `docs/backlog.md`
- Port from: the same paths, without anything about the skill copy

**Interfaces:**
- Consumes: `main`, `CliContext`, `Output` (Task 4).
- Produces: `type Release = { version: string; commit: string; repoRoot: string }`; `releaseVersion(release: Release): string` (`` `${version} (${commit})` ``); `type InvocationContext = Omit<CliContext, 'stdout' | 'stderr'>`; `sourceContext({ repoRoot }): InvocationContext`; `releasedContext({ release, entryDir }): InvocationContext`; `ExitCode = { Success: 0, Refused: 1, Failed: 2 } as const`; `type Runner = (command: string, args: string[], options?: RunOptions) => Promise<RunResult>` with `RunResult = { status: number; stdout: string; stderr: string }` and `RunOptions = { cwd?: string }`; `release(deps: ReleaseDeps): Promise<number>` with `ReleaseDeps = { run: Runner; build(release: Release): Promise<void>; packageJson: { name: string; version: string; scripts: Record<string, string> }; repoRoot: string; makeTempDir(): string; removeTempDir(dir: string): void; stdout: Output; stderr: Output }`; `fakeRunner(responses)` as Aletheia's.

- [ ] **Step 1: Write the failing tests**
  - `context.test.ts`: `the release context prints <version> (<commit>) for --version` (`main(['--version'], { ...releasedContext({ release: { version: '0.0.0', commit: '2033257', repoRoot: '/r' }, entryDir: '/pkg/dist' }), stdout, stderr })` → stdout exactly `0.0.0 (2033257)\n`); `the source context prints dev`.
  - `release.test.ts`, with `fakeRunner`: `refuses off rebuild` (`git rev-parse --abbrev-ref HEAD` → `skeleton\n` → `1`, stderr `release: refused: on skeleton, not rebuild\n`); `refuses with uncommitted changes` (`git status --porcelain` → ` M src/x.ts\n` → `release: refused: uncommitted changes`); `refuses naming the failing check` (`pnpm run lint` → status 1 → `release: refused: lint failed`, no later check runs). In every refusal `build` is never called and neither `pnpm pack` nor `pnpm add -g` runs.
- [ ] **Step 2:** The tests fail.
- [ ] **Step 3: Implement.** `TRUNK_BRANCH = 'rebuild'` in `release.constants.ts`; `NotOnTrunkError` builds `release: refused: on <branch>, not rebuild`. The checks are the names in `scripts.check` split on `&&` with the `pnpm ` prefix dropped, each run as `pnpm run <name>` in `repoRoot`. Refusals return `ExitCode.Refused`. `released.ts`: shebang, `declare const __QUAESTOR_RELEASE__: Release`, `main` over `releasedContext({ release: __QUAESTOR_RELEASE__, entryDir: import.meta.dirname })`. `bin.ts` uses `sourceContext({ repoRoot: REPO_ROOT })`; `DEV_VERSION` moves to `context.constants.ts`.
- [ ] **Step 4:** `pnpm check` is green.
- [ ] **Step 5:** `docs/architecture.md` § Release: `pnpm release` runs "from a clean, green `rebuild` until it replaces `main`, then from `main`". `docs/backlog.md`, item "`rebuild` becomes `main`", gains: "`TRUNK_BRANCH` in `src/shell/release/release/release.constants.ts` becomes `main`."
- [ ] **Step 6:** Commit `feat(release): release entry and pnpm release refusals`.

### Task 7: `pnpm release` builds, packs, smoke-runs and installs

**Files:**
- Create: `src/shell/release/build/{build.ts,build.constants.ts}`, `src/shell/release/runner/runner.ts`, `src/shell/release/bin/{bin.ts,bin.constants.ts}`, `migrations/.gitkeep`
- Modify: `src/shell/release/release/{release.ts,release.errors.ts,release.constants.ts,release.test.ts}`, `package.json` (script `release`), `knip.json`
- Port from: the same paths

**Interfaces:**
- Consumes: `release`, `ReleaseDeps`, `Runner`, `Release`, `releaseVersion`, `ExitCode` (Task 6).
- Produces: `buildRelease(release: Release): Promise<void>`; `runCommand: Runner`.

- [ ] **Step 1:** `pnpm add -D rolldown@1.2.15`.
- [ ] **Step 2: Write the failing tests** in `release.test.ts`
  - `builds, packs, smoke-runs and installs from a clean green rebuild`. Fake: branch `rebuild`, clean tree, checks pass, `git rev-parse --short HEAD` → `2033257`, `tar -tzf` lists `package/package.json`, `package/dist/quaestor.js` and `package/migrations/.gitkeep`, both `--version` runs print `0.0.0 (2033257)`. Calls in order: the six checks; `build({ version: '0.0.0', commit: '2033257', repoRoot })`; `pnpm pack --pack-destination .release` (cwd `repoRoot`); `tar -tzf <repoRoot>/.release/quaestor-0.0.0.tgz`; `tar -xzf <tgz> -C <tmp>`; `node <tmp>/package/dist/quaestor.js --help` and `--version` (cwd `<tmp>`); `pnpm add -g <tgz>`; `quaestor --version` (cwd `<tmp>`). Stdout `release: 0.0.0 (2033257) installed\n`, exit 0.
  - `refuses before installing when the package has no migrations/` → `release: refused: package is missing migrations/`, exit 1, no `pnpm add -g`.
  - `refuses before installing when the packed CLI fails its smoke run`: packed `--version` prints `dev` → `release: refused: smoke run failed: --version printed "dev", expected "0.0.0 (2033257)"`; packed `--help` exits 3 → `release: refused: smoke run failed: --help exited 3`.
  - `reports a PATH mismatch after installing`: `quaestor --version` prints `0.0.0 (1111111)` → `release: failed: quaestor on PATH prints "0.0.0 (1111111)", expected "0.0.0 (2033257)"`, exit 2.
  - `removes its temp folder after its last command`, in the success, smoke-failure and PATH-mismatch cases.
- [ ] **Step 3:** The tests fail.
- [ ] **Step 4: Implement** Aletheia's `releaseSteps` after the refusals, without the skill copy; `PathMismatchError` returns `ExitCode.Failed`. `build.ts`: Rolldown with input `src/shell/cli/released.ts`, `platform: 'node'`, `external: [/^node:/]`, `transform.define` of `__QUAESTOR_RELEASE__`, output `dist/quaestor.js`, `format: 'esm'`, `minify: true`; the shebang must survive. The release `bin.ts` as Aletheia's without the skill copy, temp prefix `quaestor-release-`. Script `"release": "node src/shell/release/bin/bin.ts"`. Create `migrations/.gitkeep`.
- [ ] **Step 5:** `pnpm check` is green. Verify the build once by hand from the repo root: `node -e "import('./src/shell/release/build/build.ts').then(m => m.buildRelease({ version: '0.0.0', commit: 'manual', repoRoot: process.cwd() }))"`, then from a fresh `mktemp -d` folder `node <repo>/dist/quaestor.js --version` prints `0.0.0 (manual)` and `--help` lists `--env` and `--json`.
- [ ] **Step 6:** Commit `feat(release): build, pack, smoke-run and install`.

**Optional checkpoint:** Angelo may merge `skeleton` into `rebuild` now and run `pnpm release` there; then `cd /tmp && quaestor --version` prints `0.0.0 (<commit>)`. Work continues on `skeleton`.

### Task 8: Usage errors are structured and exit 1

**Files:**
- Create: `src/shell/cli/invocation/output/{output.ts,output.constants.ts}`, `src/shell/cli/invocation/failure/{failure.ts,failure.types.ts,failure.constants.ts}`
- Modify: `src/shell/cli/main/{main.ts,main.test.ts}`, `docs/architecture.md` (The CLI contract)

**Interfaces:**
- Consumes: `ExitCode` (Task 6).
- Produces: `failureOf(error: unknown): Failure` with `Failure = { exitCode: number; payload: FailurePayload }` and `FailurePayload = { error: { code: string; message: string } }` (Task 9 adds the data); `usageCode(commanderCode: string): string`; `writeFailure(stderr: Output, payload: FailurePayload, json: boolean): void`.

- [ ] **Step 1:** `pnpm add -D @toon-format/toon@4.4.0`.
- [ ] **Step 2: Write the failing tests** in `main.test.ts`
  - `an unknown option exits 1 with a structured error on stderr and nothing on stdout`: `main(['--nope'], ctx)` → `1`, stdout `''`, stderr exactly `encode({ error: { code: 'unknown_option', message: "unknown option '--nope'" } }) + '\n'`.
  - `with --json anywhere in argv the error is one line of JSON`: `main(['--nope', '--json'], ctx)` → stderr exactly `{"error":{"code":"unknown_option","message":"unknown option '--nope'"}}\n`.
- [ ] **Step 3:** The tests fail.
- [ ] **Step 4: Implement.** `configureOutput` gains `outputError: () => undefined`, so commander prints nothing itself. `main` catches what `parseAsync` throws, turns a `CommanderError` into a `Failure` with `failureOf` and writes it with `writeFailure(context.stderr, payload, argv.includes('--json'))`, returning its exit code; other errors are rethrown until Task 9. `usageCode` drops the `commander.` prefix and turns camelCase into snake_case; the message drops commander's `error: ` prefix. A `CommanderError` with exit code 0 (help, version) still returns 0 and writes nothing more.
- [ ] **Step 5:** `pnpm check` is green.
- [ ] **Step 6:** In `docs/architecture.md` § The CLI contract, replace "The exit-code numbering is fixed by the skeleton and documented here." with:
  - Exit codes, decided by Angelo on 2026-11-23: 0 success; 1 refused, the call was wrong or a rule said no, so Claude fixes the call and retries; 2 failed, the environment broke, so Claude stops and tells Angelo.
  - The error is one object on stderr, TOON by default and one line of JSON with `--json`: `error` holds `code` first, then the data needed to act on it, then `message`. The example is pasted, in a code block, from the real stderr of `pnpm quaestor --nope`, never written by hand (TOON quotes some values, `"--env"` for one).
  - Codes so far, each with its exit code: commander's parse errors as snake_case codes (`unknown_option`, `unknown_command`, `option_missing_argument`, …), 1.
- [ ] **Step 7:** Commit `feat(cli): structured usage errors that exit 1`.

### Task 9: `quaestor backup` copies the default env's store

**Files:**
- Create: `src/core/errors/{errors.ts,errors.types.ts,index.ts}`, `src/core/backups/{backups.ts,backups.constants.ts,backups.test.ts,index.ts}`
- Create: `src/shell/db/index.ts`, `src/shell/db/database/{database.ts,database.types.ts}`, `src/shell/db/backups/{backups.ts,backups.constants.ts,backups.types.ts,backups.test.ts}`
- Create: `src/shell/cli/invocation/env/{env.ts,env.types.ts,env.constants.ts,env.errors.ts}`, `src/shell/cli/invocation/env-backup/env-backup.ts`, `src/shell/cli/invocation/with-store/{with-store.ts,with-store.types.ts}`, `src/shell/cli/commands/backup/{backup.ts,backup.test.ts}`
- Create: `tests/support/run-cli/{run-cli.ts,run-cli.types.ts,run-cli.constants.ts}`, `tests/support/store/{store.ts,store.types.ts}`
- Modify: `main.{ts,types.ts,test.ts}`, `context.{ts,types.ts,constants.ts,test.ts}`, `bin.{ts,test.ts}`, `released.ts`, `failure.ts`, `output.ts`, `.oxlintrc.json` (Aletheia's `tests/support/store/**` override), `docs/architecture.md`
- Port from: the same paths, in their final form, minus migrations (Task 12) and the other env sources (Task 11)

**Interfaces:**
- Consumes: `main`, `failureOf`, `writeFailure`, the contexts, `ExitCode`, `tempDir`, `captureStream`.
- Produces:
  - `#core/errors`: `class RefusedError extends Error` with `code: string` and `data: ErrorData`, constructed as `(code: string, message: string, data?: ErrorData)`; `type ErrorData = Record<string, string | string[]>`.
  - `#core/backups`: `backupFileName(env: string, instant: Date): string`.
  - `#shell/db`: `openStore(path: string): Promise<Store>`; `closeStore(store: Store): void`; `backupStore(request: BackupRequest): Promise<BackupResult>` with `BackupRequest = { store: Store; env: string; root: string; now: Date }` and `BackupResult = { path: string; removed: string[] }`; `Store` opaque, as Aletheia's `database.types.ts`.
  - CLI: `CliContext` gains `vars: Vars`, `clock: () => Date`, `defaultEnv: string`, `dataDir: string | null`; `sourceContext({ repoRoot, vars })`; `releasedContext({ release, entryDir, vars, home })`; `type Env = { name: string; dbPath: string }`; `resolveEnv({ defaultEnv, dataDir }): Env`; `type GlobalOptions = { env?: string; json?: boolean }`; `withStore(context: CliContext, options: GlobalOptions, action: StoreAction): Promise<unknown>` with `StoreAction = (store: Store, env: Env) => Promise<unknown>`; `backUpEnv(context: CliContext, store: Store, env: Env): Promise<BackupResult>`; `type CliCommand = { name: string; description: string; run(context: CliContext, options: GlobalOptions): Promise<unknown> }`; `writeResult(stdout: Output, result: unknown, json: boolean): void`; `writeEnvLine(stderr: Output, env: Env): void`.
  - Tests: `runCli(argv: string[], overrides?: CliOverrides): Promise<CliRun>` with `CliRun = { code: number; stdout: string; stderr: string }` and a fixed clock at `2026-11-23T21:04:05.123Z`; `runSql(path: string, sql: string): void`; `selectAll(path: string, sql: string): Row[]`.

- [ ] **Step 1: Write the failing tests**
  - `src/core/backups/backups.test.ts`: `backupFileName('prod', new Date('2026-11-23T21:04:05.123Z'))` → `prod-2026-11-23T21-04-05-123Z.sqlite`.
  - `src/shell/db/backups/backups.test.ts`: `the copy opens as a store with the same content` (a temp store with a table and rows written by `runSql`; `backupStore({ store, env: 'test', root, now })` → `<root>/backups/test-<instant>.sqlite`, whose rows equal the store's by `selectAll`; `<root>/backups` created when missing; no `*.partial` left).
  - `backup.test.ts`, through `runCli(['backup'], { dataDir, defaultEnv: 'test' })` with `dataDir = tempDir('quaestor-cli-')`:
    - `backup copies the default env's store and prints the copy, TOON by default`: exit 0, `<dataDir>/test.sqlite` created, stdout exactly `encode({ path: '<dataDir>/backups/test-2026-11-23T21-04-05-123Z.sqlite', removed: [] }) + '\n'`.
    - `--json prints the same fields as one line of JSON`.
    - `stderr is exactly env: test and stdout holds only the result`.
    - `backup --help opens no store and prints no env line` (no `test.sqlite`, stderr `''`).
    - `an unknown command exits 1 as unknown_command` (`['nope']`).
    - `backup --bogus exits 1 and opens no store`.
    - `with no data folder backup exits 1 as named_env_disabled and creates nothing`: `dataDir: null` → stderr exactly `encode({ error: { code: 'named_env_disabled', source: 'default', env: 'test', message: 'named environments are disabled here (default: test); set QUAESTOR_DB to a temporary file' } }) + '\n'`.
    - `a data folder whose path holds a space works` (Review Focus 4): `tempDir('quaestor cli-')`.
    - `bare quaestor prints the help on stdout and exits 0` (`main([], ctx)` → `0`, stdout contains `Usage: quaestor` and `backup`, stderr `''`).
    - `an error no class names exits 2 as unexpected with its message`: `clock: () => { throw new Error('clock broke') }` → stderr ends with `encode({ error: { code: 'unexpected', message: 'clock broke' } }) + '\n'`, exit 2.
  - `context.test.ts`: `the source context defaults to test under <repoRoot>/data and the release context to prod under <home>/.quaestor`; `under vitest the contexts have no data folder` (`vars: { VITEST: 'true' }` → `dataDir: null`); `the release's first run creates ~/.quaestor and its store` (Review Focus 5: `releasedContext({ …, vars: {}, home: tempDir(…) })` and `backup` → stderr `env: prod\n`, `<home>/.quaestor/prod.sqlite` and a `<home>/.quaestor/backups/prod-….sqlite` exist).
  - `bin.test.ts`: `the source bin under vitest refuses its default env` (spawn `bin.ts backup` from a temp cwd with the inherited environment → status 1, stderr holds `code: named_env_disabled`).
  - `main.test.ts`: the `--help` test also asserts `backup` is listed.
- [ ] **Step 2:** The tests fail.
- [ ] **Step 3: Implement**
  - `RefusedError` in `src/core/errors/`. `failureOf` maps a `RefusedError` to exit 1 with `{ code, ...data, message }` and any other `Error` to exit 2 with `{ code: 'unexpected', message }`; `main` now catches everything.
  - `openStore(path)` over `new DatabaseSync(path)` (Drizzle arrives in Task 12). `backupStore`: `mkdir(<root>/backups, { recursive: true })`, `backup()` from `node:sqlite` into `<name>.partial`, then `rename`; `removed: []` until Task 10.
  - `resolveEnv`: `dataDir === null` throws `NamedEnvDisabledError` (`named_env_disabled`, data `{ source: 'default', env }`); otherwise `{ name: defaultEnv, dbPath: <dataDir>/<defaultEnv>.sqlite }`.
  - `withStore`: resolve the env, write `env: <name>`, create the store's folder, open, run the action, close in `finally`, return the action's result. `main` writes a command's result with `writeResult(context.stdout, result, json)`.
  - Contexts: source `defaultEnv: 'test'`, `dataDir: <repoRoot>/data`; release `defaultEnv: 'prod'`, `dataDir: <home>/.quaestor`; both `dataDir: null` when `vars.VITEST` is set; `clock: () => new Date()`. `bin.ts` and `released.ts` pass `vars: process.env` (and `home: homedir()` for the release).
  - `backup`: description "copy the current env's store to its backups folder"; it backs up into `context.dataDir`.
  - An empty argv is parsed as `['--help']`.
- [ ] **Step 4:** `pnpm check` is green; `pnpm quaestor backup` prints `env: test` on stderr and a path under `data/backups/` on stdout.
- [ ] **Step 5:** `docs/architecture.md`: in § Environments and data, "Tests use `:memory:` and can never reach a real store." becomes "Tests use temporary stores and folders that they remove, and under vitest both entry points refuse named environments, so a test can never reach a real store."; the contract's codes gain `named_env_disabled` (1) and `unexpected` (2).
- [ ] **Step 6:** Commit `feat(backup): quaestor backup copies the default env's store`.

### Task 10: Backups keep the newest 5 and fail cleanly

**Files:**
- Modify: `src/core/errors/*`, `src/core/backups/*`, `src/shell/db/backups/*` (create `backups.errors.ts`), `failure.ts`, `backup.test.ts`, `docs/architecture.md`
- Port from: `src/core/backups/`, `src/shell/db/backups/` (Aletheia T020, T021, T034)

**Interfaces:**
- Consumes: `RefusedError`, `ErrorData`, `backupStore`, `runCli` (Task 9).
- Produces: `class FailedError extends Error`, constructed like `RefusedError`; `copiesToRemove(env: string, names: string[], keep = 5): string[]`; `BackupNotWrittenError extends FailedError` (`backup_not_written`, data `{ folder, reason }`, message `cannot write backup to <folder>: <reason>`).

- [ ] **Step 1: Write the failing tests**
  - core: `copiesToRemove keeps the newest 5 copies of the env` (six `prod-…` names, two `test-…`, `notes.txt`, `prod-backup.sqlite`, a `prod-….sqlite.partial`, and env `pro` against `prod-…` names → only the oldest `prod-…`; five or fewer → `[]`).
  - db: `a sixth backup removes that env's oldest copy only` (the folder seeded with 5 older `prod-…`, 2 `test-…` and `notes.txt` → 5 `prod-…` remain, the rest untouched, `removed: [<absolute path of the oldest>]`).
  - CLI: `backup prints the copy it removed` (stdout `encode({ path, removed: [<oldest>] }) + '\n'`); `an unwritable backups folder exits 2 as backup_not_written, leaves no copy and leaves the store unchanged` (`<dataDir>/backups` at mode `0o500`, restored before `tempDir` removes it → exit 2, stdout `''`, stderr holds `code: backup_not_written` and `folder: <dataDir>/backups`, no `*.sqlite` or `*.partial` in that folder, the store's sha256 unchanged).
- [ ] **Step 2:** The tests fail.
- [ ] **Step 3: Implement** as Aletheia's final `copiesToRemove` and `backupStore` (only names matching `^<env>-<instant>\.sqlite$` count, `env` escaped; removal after the rename; `mkdir`, backup and rename failures become `BackupNotWrittenError`, and the `.partial` is removed). `failureOf` maps a `FailedError` to exit 2.
- [ ] **Step 4:** `pnpm check` is green.
- [ ] **Step 5:** `docs/architecture.md` § The CLI contract: codes gain `backup_not_written` (2), and a bullet says "Every failure is an error class in its module's `.errors.ts` that extends `RefusedError` (exit 1) or `FailedError` (exit 2) from `#core/errors` with its stable code."
- [ ] **Step 6:** Commit `feat(backup): keep the newest 5 copies and fail cleanly`.

### Task 11: The environment resolves by the contract

**Files:**
- Create: `src/shell/cli/invocation/env/{env.schema.ts,env.test.ts}`, `src/shell/cli/invocation/env-backup/env-backup.errors.ts`
- Modify: `env.{ts,errors.ts,constants.ts,types.ts}`, `env-backup.ts`, `with-store.ts`, `main.test.ts`, `backup.test.ts`, `docs/architecture.md`
- Port from: `src/shell/cli/invocation/env/`, `src/shell/cli/invocation/env-backup/` (Aletheia T022)

**Interfaces:**
- Consumes: `resolveEnv`, `withStore`, `backUpEnv`, `RefusedError` (Task 9).
- Produces: `resolveEnv({ flag, vars, defaultEnv, dataDir }: EnvSources): Env`; `InvalidEnvError extends RefusedError` (`invalid_env`, data `{ source, value }`) with its three messages; `BackupsDisabledError extends RefusedError` (`backups_disabled`, message `backups are disabled here (under vitest)`); `NamedEnvDisabledError` takes `--env` and `QUAESTOR_ENV` as sources too.

- [ ] **Step 1:** `pnpm add -D zod@4.6.7`.
- [ ] **Step 2: Write the failing tests**
  - `env.test.ts`: `--env wins over QUAESTOR_DB, QUAESTOR_DB over QUAESTOR_ENV, QUAESTOR_ENV over the default` (`it.each` over the cases); `--env x maps to <dataDir>/x.sqlite`; refusals with exactly `invalid --env "Prod": use lowercase letters, digits and dashes`, `invalid --env "custom": custom is reserved for QUAESTOR_DB`, `invalid QUAESTOR_ENV "a b": use lowercase letters, digits and dashes`, `invalid QUAESTOR_DB "rel/x.sqlite": must be an absolute path`; a named env with `dataDir: null` names its source (`(--env: prod)`, `(QUAESTOR_ENV: x)`).
  - CLI: `with --env, QUAESTOR_DB and QUAESTOR_ENV all set, backup uses --env` (stderr `env: staging`, `<dataDir>/staging.sqlite` created); `an invalid env exits 1 as invalid_env before any store is opened` (`--env Prod` → stderr exactly `encode({ error: { code: 'invalid_env', source: '--env', value: 'Prod', message: 'invalid --env "Prod": use lowercase letters, digits and dashes' } }) + '\n'`, `dataDir` still empty, stdout `''`); `--env without a value exits 1 as option_missing_argument`; `QUAESTOR_DB names a custom store shown as env: custom (<path>)` (the copy is `<dataDir>/backups/custom-….sqlite`); `QUAESTOR_DB with no data folder exits 1 as backups_disabled and writes no copy`; `QUAESTOR_DB in a folder that does not exist exits 2 as unexpected and creates nothing` (Review Focus 3).
- [ ] **Step 3:** The tests fail.
- [ ] **Step 4: Implement** as Aletheia's final `resolveEnv`: zod schemas `^[a-z][a-z0-9-]*$` for names and an absolute path for `QUAESTOR_DB`; `custom` is reserved for `QUAESTOR_DB`; `writeEnvLine` shows the path only for `custom`; a custom store's folder is never created; `backUpEnv` throws `BackupsDisabledError` when `dataDir` is null.
- [ ] **Step 5:** `pnpm check` is green; `pnpm quaestor backup --env Bad; echo $?` prints the `invalid_env` error and `1`.
- [ ] **Step 6:** `docs/architecture.md`: codes gain `invalid_env` (1) and `backups_disabled` (1).
- [ ] **Step 7:** Commit `feat(cli): resolve the env from --env, QUAESTOR_DB, QUAESTOR_ENV and the default`.

### Task 12: Migrations apply at startup, and `prod` backs up first

**Files:**
- Create: `src/shell/db/migrations/{migrations.ts,migrations.constants.ts,migrations.types.ts,migrations.test.ts}`, `tests/support/fixture-migrations/{fixture-migrations.ts,fixture-migrations.types.ts,fixture-migrations.constants.ts}`
- Modify: `database.{ts,types.ts}`, `src/shell/db/backups/backups.ts`, `with-store.ts`, `output.{ts,constants.ts}`, `context.{ts,types.ts,constants.ts,test.ts}`, `main.types.ts`, `run-cli.ts`, `tests/support/store/store.ts`, `backup.test.ts`, `docs/architecture.md`
- Port from: the same paths (Aletheia T024, T025, R007 in their final form)

**Interfaces:**
- Consumes: `openStore`, `withStore`, `backUpEnv`, `runCli` (Tasks 9–11).
- Produces: `openStore(request: StoreRequest): Promise<Store>` with `StoreRequest = { path: string; migrationsDir: string; beforeMigrating(store: Store, pending: string[]): Promise<void>; onMigrated(name: string): void }`; `pendingMigrations(db: Database, migrationsDir: string): string[]`; `applyMigrations(db: Database, migrationsDir: string): void`; `CliContext` gains `migrationsDir: string`; `writeMigrations(dir: string, migrations: Record<string, string>): string`, `noMigrations(): string`, `FIXTURE_MIGRATIONS` (`20261123000000_first`: `CREATE TABLE fixture_a (id integer primary key);`, `20261123000100_second`: `CREATE TABLE fixture_b (id integer primary key);`), `SHIPPED_MIGRATIONS` (the repo's `migrations/`).

- [ ] **Step 1:** `pnpm add -D drizzle-orm@1.0.0-rc.5`.
- [ ] **Step 2: Write the failing tests**
  - `migrations.test.ts`: `a new store is created with every migration applied` (`fixture_a` and `fixture_b` exist; `__drizzle_migrations` holds both names); `the shipped migrations folder opens a store`.
  - `backup.test.ts`: `backup on a new store applies the migrations first` (stderr `env: test`, `migrated: 20261123000000_first`, `migrated: 20261123000100_second`, in that order, exit 0); `in a non-prod env pending migrations apply without a backup` (only the command's own copy in `<dataDir>/backups/`, no `backup:` line); `a prod store with pending migrations is backed up before they apply` (`--env prod`, a clock that advances 1 ms per call → stderr exactly `env: prod`, `backup: <dataDir>/backups/prod-<first instant>.sqlite (before migrating)`, then the two `migrated:` lines; that copy has no fixture table; the command then writes its own copy); `a current store takes no backup and reports nothing about schema` (a second run → stderr only `env: prod`, one new copy); `a store file that is not SQLite exits 2 as unexpected and is left unchanged` (Review Focus 2: `<dataDir>/test.sqlite` holds `not a store\n` → exit 2, stdout `''`, stderr starts with `env: test\n` and ends with `encode({ error: { code: 'unexpected', message: 'file is not a database' } }) + '\n'`, the file's sha256 unchanged, nothing in `<dataDir>/backups/`).
- [ ] **Step 3:** The tests fail.
- [ ] **Step 4: Implement** as Aletheia's final `openStore`: `drizzle({ client: new DatabaseSync(path) })` from `drizzle-orm/node-sqlite`, `migrate()` from `drizzle-orm/node-sqlite/migrator`, `beforeMigrating` called with the pending names before they apply, `onMigrated` per applied name; `withStore` backs up first only when the env is `prod` and something is pending, and writes `backup: <path> (before migrating)` and `migrated: <name>`. The source context's `migrationsDir` is `<repoRoot>/migrations`, the release's `<entryDir>/../migrations`; the release `backup` test in `context.test.ts` sets `entryDir` to `<repo>/dist`. `runCli` defaults `migrationsDir` to `noMigrations()`.
- [ ] **Step 5:** `pnpm check` is green.
- [ ] **Step 6:** `docs/architecture.md` § The CLI contract gains the stderr diagnostic lines, in their order: `env: <name>` (or `env: custom (<path>)`), `backup: <path> (before migrating)`, `migrated: <name>` per migration applied, then the error object when the command fails.
- [ ] **Step 7:** Commit `feat(db): migrations at startup, backed up first in prod`.

### Task 13: A failing or unknown migration leaves the store unchanged

**Files:**
- Create: `src/shell/db/migrations/migrations.errors.ts`
- Modify: `migrations.{ts,test.ts}`, `database.ts`, `fixture-migrations.constants.ts`, `backup.test.ts`, `docs/architecture.md`
- Port from: the same paths (Aletheia T026, T027 and their "Done as" notes)

**Interfaces:**
- Consumes: `openStore`, `applyMigrations`, `FailedError`, `writeMigrations` (Tasks 10, 12).
- Produces: `MigrationFailedError extends FailedError` (`migration_failed`, data `{ migration, reason }`, message `migration <name> failed: <reason>`); `UnknownMigrationsError extends FailedError` (`unknown_migrations`, data `{ names }`, message `the store has migrations this code does not know: <names joined by ", ">`); `FAILING_MIGRATIONS` (`20261123000000_first` valid, `20261123000100_second` is `this is not sql;`).

- [ ] **Step 1: Write the failing tests**
  - `migrations.test.ts`: `a failing migration keeps none of the pending ones` (throws naming `20261123000100_second`; `fixture_a` absent; `__drizzle_migrations` holds neither name).
  - `backup.test.ts`: `a failing migration in prod exits 2 as migration_failed and keeps the copy taken before it` (stderr ends with `encode({ error: { code: 'migration_failed', migration: '20261123000100_second', reason: 'near "this": syntax error', message: 'migration 20261123000100_second failed: near "this": syntax error' } }) + '\n'`, stdout `''`, the pre-migration copy remains, `prod.sqlite` has no fixture table); `a store with migrations this code does not know exits 2 as unknown_migrations and is unchanged` (a store migrated with `first` and `second`, opened with a folder holding `first` and a pending `20261123000200_third`, `--env prod` → stderr holds `code: unknown_migrations` and `names[1]: 20261123000100_second`, the store's sha256 unchanged, no copy written, so the check runs before the pending ones).
- [ ] **Step 2:** The tests fail.
- [ ] **Step 3: Implement** as Aletheia's final: `migrate()` rolls back on failure; `applyMigrations` names the failing migration by matching the failing statement (`DrizzleQueryError.query`) against each pending migration's statements and takes the reason from `cause.message`; `openStore` refuses unknown migrations before computing the pending ones. If `migrate()` does not roll back, stop and report to Angelo before working around it.
- [ ] **Step 4:** `pnpm check` is green.
- [ ] **Step 5:** `docs/architecture.md`: codes gain `migration_failed` (2) and `unknown_migrations` (2).
- [ ] **Step 6:** Commit `feat(db): a failing or unknown migration leaves the store unchanged`.

### Task 14: Close

**Files:** Modify `CLAUDE.md`, `docs/architecture.md`, `docs/backlog.md`.

- [ ] **Step 1:** Check the contract against the code: every code built under `src/` appears in `architecture.md`'s list with its exit code and nothing else does; every stderr line `src/` writes is in the contract. Fix the docs, not the code, unless the code contradicts the docs; then ask Angelo.
- [ ] **Step 2:** `CLAUDE.md` gains:

  ```markdown
  ## Commands

  - `pnpm quaestor <command>` runs the sources against `data/test.sqlite`; the installed
    `quaestor` is the release and defaults to `prod`.
  - `pnpm test` runs the tests; `pnpm check` runs test, lint, format:check, typecheck,
    dead-code and duplication; `pnpm format` fixes formatting.
  - `pnpm release` is Angelo's.
  ```

- [ ] **Step 3:** `docs/backlog.md`: delete "The skeleton"; "Recording movements" gains "Measure TOON against compact JSON, in tokens, on real movement lists and single objects (expected on 2026-11-23: about 35 % saved on uniform lists, slightly worse on single objects)."
- [ ] **Step 4:** `pnpm check` is green; commit `docs: skeleton contract, commands and backlog`.
- [ ] **Step 5:** Hand Angelo: merge `skeleton` into `rebuild`, run `pnpm release` from `rebuild`, then from `/tmp`: `quaestor --version` prints `0.0.0 (<commit>)`; `quaestor backup` prints `env: prod` and creates `~/.quaestor/prod.sqlite` and `~/.quaestor/backups/prod-….sqlite`; `time quaestor --version` and `time quaestor backup` each finish under 1 s. `docs/workflow.md`'s check against a copy of the real data does not apply: the skeleton holds no finance data.
- [ ] **Step 6:** Once Angelo has released: `git rm docs/plans/fresh-start-and-skeleton.md` on `rebuild`, commit `docs: fresh start and skeleton done`.

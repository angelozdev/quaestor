# Architecture

## What Quaestor is

A local command-line tool, `quaestor`, whose only client is Claude. Angelo talks
to Claude in Spanish; Claude runs `quaestor` and reads what it prints. No server,
no web screens, no Docker, nothing that has to be running before it can answer.

```
Angelo ⇄ Claude (skills) ─► quaestor CLI ─► core ─► store adapter ─► SQLite file
                            commander        pure      Drizzle         node:sqlite
                            zod in           logic
                            TOON out
```

Facts live in code, judgment lives in Claude. Sums, balances, conversions and
anything else with one right answer is computed by `quaestor` and covered by
tests. Interpreting those figures for Angelo ("the trip fits if you keep this
pace") is Claude's job, never a hard-coded rule.

## Code layout

- Functional core and imperative shell, in concept folders: `src/core/<concept>/`
  holds pure logic, `src/shell/<adapter>/<concept>/` holds I/O (`db`, `cli`,
  `release`). Each folder exposes an `index.ts` barrel, reached through the
  `#core/*` and `#shell/*` subpath imports.
- Inside a concept folder, one folder per module: `<name>.ts` (logic only),
  `<name>.test.ts`, and as needed `<name>.types.ts` (every type),
  `<name>.errors.ts` (every error class), `<name>.constants.ts` (every literal
  whose meaning is a convention) and `<name>.schema.ts` (zod and Drizzle schemas).
- The core performs no I/O: no filesystem, SQL, network or direct clock. Time and
  persistence enter as injected ports. Lint forbids `node:*` under `src/core/`.
- Only `src/shell/db` imports `node:sqlite` and `drizzle-orm`. Only the utilities
  module imports `just-*`. Both are lint rules.
- `quaestor` is the only writer of data. Claude never opens the SQLite file.

## The CLI contract

Written for a reader that is a model, not a person.

- stdout carries the result and nothing else: TOON by default, one-line JSON with
  `--json`.
- stderr carries diagnostics and, for every command that opens a store, an
  `env: <name>` line. `--help` and `--version` open no store and print none.
- The stderr diagnostic lines, in their order: `env: <name>` (or
  `env: custom (<path>)`), `backup: <path> (before migrating)` (only in `prod`, and
  only when a migration is pending), `migrated: <name>` per migration applied, then
  the error object when the command fails. A call refused before a store is chosen,
  such as a usage error, `invalid_env`, `invalid_json` or `invalid_input`, writes only
  the error object.
- A failure leaves stdout empty, exits non-zero and writes a structured error with
  a stable `code` (for example `invalid_env`) and the data needed to act on it.
- Exit codes, decided by Angelo on 2026-11-23: 0 success; 1 refused, the call was
  wrong or a rule said no, so Claude fixes the call and retries; 2 failed, the
  environment broke, so Claude stops and tells Angelo.
- The error is one object on stderr, TOON by default and one line of JSON with
  `--json`: `error` holds `code` first, then the data needed to act on it, then
  `message`. The example is pasted from the real stderr of `pnpm quaestor --nope`,
  never written by hand (TOON quotes some values, `"--env"` for one):

  ```
  error:
    code: unknown_option
    message: unknown option '--nope'
  ```

- Codes so far, each with its exit code: commander's parse errors as snake_case
  codes (`unknown_option`, `unknown_command`, `option_missing_argument`, …), 1;
  `missing_command`, 1, when a call has global options and no command, or names a
  command group and no command in it, with the `commands` it can use; `invalid_env`,
  1, when `--env`, `QUAESTOR_ENV` or `QUAESTOR_DB` holds a value that cannot name a
  store, with the `source` and the `value`; `named_env_disabled`, 1, because a named env needs a data folder and the
  entry point has none (under vitest), with the `source` and the `env`;
  `backups_disabled`, 1, because a backup needs that same data folder;
  `backup_not_written`, 2, when a backup cannot be written, with the `folder` and
  the `reason`; `migration_failed`, 2, when a pending migration fails, with the
  `migration` and the `reason`, the store left as it was; `unknown_migrations`, 2,
  when the store holds migrations this code does not ship, with their `names`, the
  store left as it was; `already_exists`, 1, when a name is already taken, with the
  `kind` and the `name`; `not_found`, 1, when a code or a name names nothing live, with the
  `kind` and the `value`; `missing_rate`, 1, when a report counts a foreign currency with no
  rate, with every such `currencies`; `group_not_empty`, 1, when a group to delete still holds
  a category, archived ones included, with the `group` and its `categories`; `invalid_input`, 1, when a flag or a field is wrong, with
  every problem as `issues`, each `<field>: <what is wrong>` (`movements[0].amount` for a
  field inside a list), found before a store is opened; `invalid_json`, 1, when stdin
  holds no valid JSON, found before a store is opened, with the reason on one line in its
  message; `refused`, 1, when a write breaks a rule, with every item at fault as `errors`,
  each `{code, item, message}` where `item` is the position (`delete[0]`,
  `movements[2]`, `transfers[0].from`) and `code` is `not_found`, `currency_mismatch`,
  `before_opening`, `same_account_transfer` or `archived`, and nothing written;
  `unexpected`, 2, for any error no class names, with its message.
- Quaestor's own failures are error classes in their module's `.errors.ts`, each
  extending `RefusedError` (exit 1) or `FailedError` (exit 2) from `#core/errors`
  with its stable code. Commander's parse errors are not classes: `failure.ts` maps
  them to snake_case usage codes, exit 1. Anything else that is thrown is
  `unexpected`, exit 2. `pnpm release` is outside this contract: it prints its own
  `release: refused: …` (exit 1) and `release: failed: …` (exit 2) lines.
- Nothing is interactive. Every input is a flag, or JSON on stdin when it is long
  or nested. No prompts, no colours, no spinners.
- Claude runs one `quaestor` call at a time. Two calls at once can collide: copies
  taken in the same millisecond share a name, so one exits 2 `backup_not_written`
  with a reason ending in `already exists`, and two first runs with a pending
  migration can both try to apply it. Either way the store is left correct.
  Decided by Angelo on 2026-11-24, because parallel calls are too unlikely to
  pay for handling them.
- Every write accepts `--dry-run`. A dry run does all the work except the commit
  and returns what would change, including each touched account's balance before
  and after.
- The tool is entirely in English. Spanish exists only in what Claude says to
  Angelo.

## Money

- Every amount is integer cents in its account's currency: COP 45,000.50 is
  `4500050`.
- One rounding function, under test, is the only place a fraction of a cent is
  resolved.
- Integer cents hold for every currency, KRW included. The CLI takes an amount as
  text, as the bank shows it (`"45000.50"`, at most two decimals, no thousands
  separator), and gives it back as a number (`45000.5`). An amount whose cents are
  not a safe integer, beyond 90071992547409.91 either way, is refused.
- A rate is the COP that one unit of a foreign currency is worth, stored as integer
  hundredths of a peso, at most two decimals and above 0: 1 USD = 3,912.45 COP is
  `391245`. There is at most one rate per currency, and COP, the local currency fixed in
  code, has none. A six-decimal rate, as the legacy one, would pass the safe-integer
  limit: 3,000,000 cents (30,000.00 USD) × 4,000,000,000 = 1.2 × 10^16, above 2^53; two
  decimals keep it at 1.2 × 10^12. Decided by Angelo on 2026-11-25.
- A report converts each foreign movement on its own through `convertCents`, cents ×
  rate / 100, half a centavo away from zero, and then adds the converted figures. A
  conversion or a total that is not a safe integer fails as `unexpected` (exit 2) instead
  of printing a rounded figure.

## Environments and data

- The installed `quaestor` defaults to `prod` and keeps its store in
  `~/.quaestor/prod.sqlite`, outside the repo.
- Files under `~/.quaestor` keep the default permissions: the home folder already
  shuts out other users, and the Mac has one person account. Decided by Angelo on
  2026-11-24.
- Running the sources (`pnpm quaestor`) defaults to `test` and keeps its stores in
  the repo's `data/<env>.sqlite`, ignored by git. The sources refuse `prod`, from
  `--env` or `QUAESTOR_ENV`, as `invalid_env` (exit 1): `prod` only ever means the
  installed release's `~/.quaestor/prod.sqlite`. Decided by Angelo on 2026-11-24.
- Tests use temporary stores and folders that they remove, and under vitest both
  entry points refuse named environments. The end-to-end tests of the built
  release run it without `VITEST`, so their helper builds its environment from
  nothing and sets `HOME` to a temporary folder it refuses to leave. Either way,
  a test can never reach a real store.
- Resolution order: `--env`, then `QUAESTOR_DB` (an absolute path), then
  `QUAESTOR_ENV`, then the default of whoever is running. An env name starts with
  a lowercase letter and holds only lowercase letters, digits and dashes, and
  `custom` is reserved: `QUAESTOR_DB` is the only way to a store outside the data
  folder, shown as `env: custom (<path>)`, and the folder it names must already
  exist, or the call is refused as `invalid_env` (exit 1). A folder that exists
  but cannot be written still fails as `unexpected` (exit 2). Decided by Angelo on
  2026-11-24.

## Migrations and backups

- Drizzle's migrator applies pending migrations at startup, all or nothing.
- The migration that brings groups seeds the 14 approved groups with fixed codes, in every
  store.
- A table that other tables reference is rebuilt with `PRAGMA defer_foreign_keys = ON`,
  copied through a temporary table and created again under its own name; drizzle-kit's
  `PRAGMA foreign_keys=OFF` rebuild is a no-op inside the migrator's transaction and fails
  once rows point at the table (checked on 2026-11-25). When drizzle-kit generates an
  `ALTER TABLE ... ADD ... NOT NULL` instead, which SQLite refuses on a table with rows, the
  same rebuild replaces it.
- In `prod`, a backup is taken before any migration runs. A `QUAESTOR_DB` store
  gets none, so `QUAESTOR_DB` always names a copy, never
  `~/.quaestor/prod.sqlite`. Decided by Angelo on 2026-11-24.
- A store written by a newer release refuses an older one.
- `quaestor backup` copies the data file on demand.
- Backups live in a `backups/` folder inside the data folder, as in Aletheia: the
  installed release writes to `~/.quaestor/backups/`, the sources to the repo's
  `data/backups/`, and a `QUAESTOR_DB` store is copied there as `custom-<instant>`,
  not beside its own file. Decided by Angelo on 2026-11-23. Nothing goes to iCloud
  Drive, so a copy off the Mac is Time Machine's job; losing the Mac without one
  loses the store and its backups together.

## Release

- `pnpm release`, run by Angelo from a clean, green `rebuild` until it replaces
  `main`, then from `main`, bundles the sources with Rolldown, packs them and
  installs them globally with `pnpm add -g`.
- A `git`, `tar`, `pnpm pack` or `pnpm add -g` command that exits non-zero stops
  the release with `release: failed: <command and arguments> exited <status>`
  (exit 2), so it is never read as a clean tree, another branch or a missing
  `migrations/`.
- The installed binary is the only thing that touches `prod`. Work in progress in
  the repo never does.

## Legacy data

- The legacy Postgres database is frozen: nothing writes to it again.
- The legacy app stays on `main`, tagged `legacy-final`; the new project grows on
  the orphan branch `rebuild`, which shares no history with it.
- On 2026-11-23 (manifest `exportedAt` 2026-11-24T03:03:33Z) every table was
  exported once to `~/.quaestor/legacy/`, outside the repo because it is real
  financial data, and the folder was made read-only. `tables/<table>.jsonl`
  holds one JSON object per row, every value the text of its `row_to_json`
  rendering or null (numbers keep every digit); `manifest.json` holds each file's
  row count and sha256 and each account's stored balance; the final dump and the
  `export.sh` and `check.sh` that made and checked the export sit next to them.
- Legacy values are as stored: amounts and balances are integer cents in the
  account's currency, `settings.usd_cop` has six decimals, and
  `transaction.transfer_direction` holds `in_` and `out`.
- The container `quaestor-db-1` (volume `quaestor_quaestor_pg_data`) stays
  stopped as a frozen copy, with the dump as its fallback. Reading it:
  `docker start quaestor-db-1`,
  `docker exec -i quaestor-db-1 sh -c 'psql -U "${POSTGRES_USER:-quaestor}" -d "${POSTGRES_DB:-quaestor}"'`,
  `docker stop quaestor-db-1`. Nothing writes to it.
- The `import` command loaded the export into `prod` once, on 2026-11-24, and was
  retired on 2026-11-25 (see `docs/features/spending-and-income.md`). The export stays
  untouched in `~/.quaestor/legacy/`.
- Each feature, when it is built, imports the legacy rows it needs into its own
  new tables. Nothing is imported before its table exists, and nothing is
  imported twice.
- After an import, every account's balance equals its legacy stored balance to
  the cent. On 2026-11-23, several legacy accounts did not equal the sum of
  their movements (one stored COP 30,000,000.00 while its movements added up to COP
  9,000,000.00), because opening balances and manual resets were never
  movements. The import carries that difference as the account's opening
  balance, dated the day before its first posted movement (the day of the export
  when it has none); it is never dropped and never silently "fixed".

## Skills

- Skills never touch the database; every read and write goes through `quaestor`.
- `record-movements` and `spending-and-income` live in `.claude/skills/` and call the
  installed `quaestor`, never `pnpm quaestor`, so they work only with Claude open in this
  repo.

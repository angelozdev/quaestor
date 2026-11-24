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
- The core performs no I/O: no filesystem, SQL, network or direct clock. Time and
  persistence enter as injected ports. Lint forbids `node:*` under `src/core/`.
- Only `src/shell/db` imports `node:sqlite` and `drizzle-orm`. Only the utilities
  module imports `just-*`. Both are lint rules.
- `quaestor` is the only writer of data. Claude never opens the SQLite file.

## The CLI contract

Written for a reader that is a model, not a person.

- stdout carries the result and nothing else: TOON by default, one-line JSON with
  `--json`.
- stderr carries diagnostics and an `env: <name>` line on every command.
- A failure leaves stdout empty, exits non-zero and writes a structured error with
  a stable `code` (for example `currency_mismatch`) and the data needed to act on
  it. The exit-code numbering is fixed by the skeleton and documented here.
- Nothing is interactive. Every input is a flag, or JSON on stdin when it is long
  or nested. No prompts, no colours, no spinners.
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
- How the dollar rate is stored is decided by the currency feature. The legacy
  rate has six decimals (4,000.000000), and a six-decimal integer rate times a USD
  balance in cents passes JavaScript's safe-integer limit: 3,000,000 cents ×
  4,000,000,000 = 1.2 × 10^16, above 2^53 ≈ 9.0 × 10^15.

## Environments and data

- The installed `quaestor` defaults to `prod` and keeps its store in
  `~/.quaestor/prod.sqlite`, outside the repo.
- Running the sources (`pnpm quaestor`) defaults to `test` and keeps its stores in
  the repo's `data/<env>.sqlite`, ignored by git. The sources never reach `prod`
  unless told to with `--env prod`.
- Tests use `:memory:` and can never reach a real store.
- Resolution order: `--env`, then `QUAESTOR_DB` (an absolute path), then
  `QUAESTOR_ENV`, then the default of whoever is running.

## Migrations and backups

- Drizzle's migrator applies pending migrations at startup, all or nothing.
- In `prod`, a backup is taken before any migration runs.
- A store written by a newer release refuses an older one.
- `quaestor backup` copies the data file on demand.
- Backups live in a `backups/` folder next to the store, as in Aletheia: the
  installed release writes to `~/.quaestor/backups/`, the sources to the repo's
  `data/backups/`. Decided by Angelo on 2026-11-23. Nothing goes to iCloud Drive,
  so a copy off the Mac is Time Machine's job; losing the Mac without one loses
  the store and its backups together.

## Release

- `pnpm release`, run by Angelo from a clean, green `main`, bundles the sources
  with Rolldown, packs them and installs them globally with `pnpm add -g`.
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
- Each feature, when it is built, imports the legacy rows it needs into its own
  new tables. Nothing is imported before its table exists, and nothing is
  imported twice.
- After an import, every account's balance equals its legacy stored balance to
  the cent. On 2026-11-23, several legacy accounts did not equal the sum of
  their movements (Reserve stores COP 30,000,000.00 while its movements add
  up to COP 9,000,000.00), because opening balances and manual resets were never
  movements. The import carries that difference explicitly; it is never dropped
  and never silently "fixed". How it is represented is decided by the feature
  that imports accounts.

## Skills

- Skills never touch the database; every read and write goes through `quaestor`.
- `record-movements` is rewritten over the CLI by the recording feature. Until
  then, nothing records movements.

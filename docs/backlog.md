# Backlog

Only what is still to do, in order. A finished item is deleted; git keeps the
history. Each feature is rethought from scratch in its own conversation before it
is built; nothing here inherits a rule from the legacy app.

## 1. The fresh start

Exception: shared setup, no user-visible behaviour.

- `main` stays as the legacy app, untouched, and is tagged `legacy-final`.
- A final `pg_dump` of the legacy database, kept with the existing backups and
  copied into `~/.quaestor/legacy/`.
- Every legacy table exported to `~/.quaestor/legacy/`, with a manifest of row
  counts and each account's stored balance, checked against the live database.
  On 2026-11-23: every movement, account, category, category group,
  3 tags, every tag link, 19 repeating rules, 95 repeating dates, 10 funds, 6 metas,
  1 meta amendment, 0 meta contributions, 1 settings row.
- A `CLAUDE.md` for `rebuild` that sends every session to `docs/` first, plus
  `LICENSE`.
- The legacy leftovers still in the working folder (`backend/`, `frontend/`,
  `acceptance/`, `features/`, `.dev-data/`, `.engineer/`, `node_modules/`, caches,
  an empty `quaestor.db`, the legacy lefthook hook in `.git/hooks/`) are handed to Angelo as commands to run, after the
  export, not deleted by the agent. Then the second block of `.gitignore`, which
  only hides them, is removed.
- The Postgres container and its volume stay as a frozen copy. The dump is the
  fallback if they are ever lost.

## 2. The skeleton

Exception: shared setup, no finance behaviour. Exercised with
`quaestor --version` from any folder and `quaestor backup`.

- Tooling from `stack.md`, the `quaestor` entry point, `--help` and `--version`.
- Environment resolution, migrations at startup, `quaestor backup`.
- The CLI contract from `architecture.md`: TOON and `--json`, structured errors,
  exit codes.
- The utilities module wrapping `just-*`, and the boundary lint rules.
- `pnpm release` and the global install.

## 3. Recording movements

The first feature, rethought in its own conversation. It brings the accounts,
categories, tags and movements it needs from the legacy export and rewrites the
`record-movements` skill over the CLI. Done when Claude records a real movement
from a bank screenshot: a dry run first, then the write after Angelo says yes.

## 4. `rebuild` becomes `main`

Once recording works, Angelo replaces `main` with `rebuild`, which means a
force-push on GitHub, and stops the legacy container for good.

## 5. Next features

Rethought one at a time once recording works, in an order chosen then. What Angelo
said he will ask Claude:

- how much he spent last month, and on what;
- how much he has available this month;
- whether he can afford something, such as a trip next year.

Legacy rows that no feature claims yet (funds, metas, planned payments, repeating
rules, the dollar rate) wait in the export and are imported only if a feature
brings them back.

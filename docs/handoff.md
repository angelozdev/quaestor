# Handoff: start building

Written 2026-11-23 at the end of the design conversation. The next session reads
this file, does what it says, and deletes it once the plan exists.

## Where things stand

- Branch `rebuild` is an orphan branch: no shared history with `main`, and
  nothing in it but `.gitignore` and `docs/`.
- `docs/stack.md`, `docs/architecture.md`, `docs/workflow.md` and
  `docs/backlog.md` were approved by Angelo on 2026-11-23. They are the source of
  truth; read all four before planning.
- `main` holds the legacy app, untouched, with Angelo's last edits to the
  `record-movements` skill committed. It is not tagged `legacy-final` yet; that
  is backlog item 1.
- The working folder was emptied of legacy leftovers, including the legacy
  `.env.local.*` files.
- Nothing records movements until backlog item 3 lands. Angelo knows and accepts
  the gap; he catches up later from bank screenshots.

## The legacy database

- Real data, frozen. Never write to it.
- Container `quaestor-db-1`, volume `quaestor_pg_data`, currently stopped. The
  compose files are gone, so start it with `docker start quaestor-db-1` and stop
  it with `docker stop quaestor-db-1`.
- Read with
  `docker exec -i quaestor-db-1 sh -c 'psql -U "${POSTGRES_USER:-quaestor}" -d "${POSTGRES_DB:-quaestor}"'`.
- Amounts and balances are integer cents (`bigint`) in the account's currency.
  `settings.usd_cop` is `numeric(18,6)`.
- Trap: `transaction.transfer_direction` holds `in_` and `out`, not `in`.
- The final legacy dump was taken on 2026-11-23, after the last write
  (2026-11-08 21:08 UTC): `QuaestorBackups/quaestor-legacy-final-2026-11-23.dump`
  in iCloud Drive. Every earlier dump predates that write.
- The start path above was checked on 2026-11-23: the container starts without
  compose and holds every movement.

## Next step

1. Invoke `superpowers:writing-plans` for backlog items 1 (the fresh start) and
   2 (the skeleton). Write the plan to `docs/plans/<name>.md`, cut into vertical
   slices as `docs/workflow.md` says; both items are named exceptions (shared
   setup).
2. Use Aletheia as the working reference for the skeleton and adapt it rather
   than inventing anew: `~/me/aletheia/specs/000-skeleton/spec.md`, its
   `src/shell/` (cli, db, release), and its ADRs 0002, 0003, 0005, 0008 and 0009.
   Rename everything to Quaestor: `QUAESTOR_ENV`, `QUAESTOR_DB`, `~/.quaestor/`.
3. Item 1 also writes the `CLAUDE.md` for `rebuild`: it sends every session to
   `docs/` first and carries no rule that `docs/workflow.md` already states.
4. Execution after the plan is Angelo's call (subagent-driven, inline, or
   `/az-orchestrate`).

## Out of scope for this plan

- Anything about the product: accounts, movements, categories, reports. Each
  feature is rethought in its own conversation, starting with recording
  movements (backlog item 3).
- How the dollar rate is stored (left to the currency feature, see
  `docs/architecture.md`).

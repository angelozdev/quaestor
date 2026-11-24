# Backlog

Only what is still to do, in order. A finished item is deleted; git keeps the
history. Each feature is rethought from scratch in its own conversation before it
is built; nothing here inherits a rule from the legacy app.

## 1. Recording movements

The first feature, rethought in its own conversation. It brings the accounts,
categories, tags and movements it needs from the legacy export and rewrites the
`record-movements` skill over the CLI. Done when Claude records a real movement
from a bank screenshot: a dry run first, then the write after Angelo says yes.

## 2. Skeleton tests through the command

The skeleton's tests that call internal functions (backup names, store
backups, the connection, migrations, env resolution) are rewritten through the
command where one reaches them, as `docs/workflow.md` now asks, and the rest
go to Angelo one by one.

## 3. `rebuild` becomes `main`

GitHub's `main` already holds `rebuild` since 2026-11-24: a force-push of its
history, scrubbed of every real figure and name, with the legacy branch
`monthly-report` and the tag `legacy-final` removed from GitHub (both kept
locally). What remains, once recording works: the local branches swap names
(`rebuild` becomes `main`, the legacy `main` is kept under another name),
`TRUNK_BRANCH` in `src/shell/release/release/release.constants.ts` becomes
`main`, the legacy container stops for good, and Angelo asks GitHub Support to
purge the old commits still reachable by SHA.

## 4. Next features

Rethought one at a time once recording works, in an order chosen then. What Angelo
said he will ask Claude:

- how much he spent last month, and on what;
- how much he has available this month;
- whether he can afford something, such as a trip next year.

Credit accounts get behaviour of their own, such as a cut date and a payment date.
A loan account typed `credit` may need them too; that feature decides.

Legacy rows that no feature claims yet (funds, metas, planned payments, repeating
rules, the dollar rate) wait in the export and are imported only if a feature
brings them back.

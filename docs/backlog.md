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

Once recording works, Angelo replaces `main` with `rebuild`, which means a
force-push on GitHub, and stops the legacy container for good.
`TRUNK_BRANCH` in `src/shell/release/release/release.constants.ts` becomes `main`.

## 4. Next features

Rethought one at a time once recording works, in an order chosen then. What Angelo
said he will ask Claude:

- how much he spent last month, and on what;
- how much he has available this month;
- whether he can afford something, such as a trip next year.

Credit accounts get behaviour of their own, such as a cut date and a payment date.
Loan is a loan typed `credit`, so that feature decides whether it gets them too.

Legacy rows that no feature claims yet (funds, metas, planned payments, repeating
rules, the dollar rate) wait in the export and are imported only if a feature
brings them back.

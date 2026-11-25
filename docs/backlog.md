# Backlog

Only what is still to do, in order. A finished item is deleted; git keeps the
history. Each feature is rethought from scratch in its own conversation before it
is built; nothing here inherits a rule from the legacy app.

## 1. `rebuild` becomes `main`

GitHub's `main` already holds `rebuild` since 2026-11-24: a force-push of its
history, scrubbed of every real figure and name, with the legacy branch
`monthly-report` and the tag `legacy-final` removed from GitHub (both kept
locally). What remains, once recording works: the local branches swap names
(`rebuild` becomes `main`, the legacy `main` is kept under another name),
`TRUNK_BRANCH` in `src/shell/release/release/release.constants.ts` becomes
`main`, the legacy container stops for good, and Angelo asks GitHub Support to
purge the old commits still reachable by SHA.

## 2. Next features

Rethought one at a time once recording works, in an order chosen then. What Angelo
said he will ask Claude:

- how much he spent last month, and on what;
- how much he has available this month;
- whether he can afford something, such as a trip next year.

Credit accounts get behaviour of their own, such as a cut date and a payment date.
A loan account typed `credit` may need them too; that feature decides.

Investments may get behaviour of their own: how to record what Angelo buys, such as
VTI, VXUS or crypto, and not only an account's balance. To be reviewed.

Legacy rows that no feature claims yet (funds, metas, planned payments, repeating
rules, the dollar rate) wait in the export and are imported only if a feature
brings them back.

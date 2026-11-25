# Backlog

Only what is still to do, in order. A finished item is deleted; git keeps the
history. Each feature is rethought from scratch in its own conversation before it
is built; nothing here inherits a rule from the legacy app.

## 1. Retire the legacy app

`rebuild` became `main` on 2026-11-25. What remains is Angelo's: the legacy
container stops for good, and GitHub Support is asked to purge the old commits
still reachable by SHA.

## 2. Archive and unarchive an account

The next feature, decided by Angelo on 2026-11-25. No command archives an account or
opens an archived one, and an archived account takes no movement, so a correction there
is refused. What it unblocks:

- the misfiled rows of the spending-and-income moves that sit in accounts archived since
  the legacy app: open the account, correct the rows, archive it again;
- a loan account paid back to 0, one per person, which today stays in `account list`.

## 3. Next features

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

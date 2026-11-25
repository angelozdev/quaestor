# Archiving an account

Status: draft, waiting for Angelo's approval.

## Why

An archived account takes no new movement, and no command archives an account or opens an
archived one. Two things wait on that:

- misfiled rows that sit in accounts archived since the legacy app: a correction there is
  refused today, because its new record lands in an archived account;
- a loan account paid back to 0, one per borrower, which stays in `account list` for good.

## Done when

- The misfiled rows in the accounts archived since the legacy app are corrected: each
  account opened, its rows corrected, and the account archived again, every write shown as a
  dry run and approved by Angelo.
- The loan accounts back at 0 are archived and leave `account list`.

## Not in this feature

Renaming an account or changing its emoji, deleting an account, unarchiving a category, and
an `account edit` command (see Approaches).

## What must never happen

- Money hidden in an archived account: an archived account is always at 0.

## Rules

- `quaestor account archive <code>` archives an account, with `--dry-run`. It shows the
  account as it would be after, balance included.
- Only an account at 0 can be archived. An account holding anything else is refused as
  `balance_not_zero` (exit 1), with the `account`, its `currency` and its `balance`, so
  what is left gets recorded first as what it really is: the borrower paid it back, or it
  is written off. Decided by Angelo on 2026-11-25.
- `quaestor account unarchive <code>` opens an archived account again, with `--dry-run`.
- Archiving an archived account, or unarchiving an active one, changes nothing and shows the
  account as it is (Claude's call, as `category archive` does).
- A code that names no account is `not_found` (exit 1) with `kind: account`.
- `quaestor account list` shows the active accounts only; `quaestor account list --all`
  shows every account, archived ones included, so Claude can find the code to unarchive.
  Decided by Angelo on 2026-11-25; the flag's name is Claude's call.
- An archived account takes no change while it is archived: no new movement, no transfer
  half, as today, and now no delete either, so its balance cannot move off 0 (Claude's
  call). A delete of a transfer whose other half sits in an archived account is refused too,
  because deleting one half deletes both. Each is a `refused` item with code `archived`.
- A correction in an archived account is always: unarchive, correct, archive again. Moving a
  row to another category keeps its amount, so the account is back at 0 and archives again.
- An archived account keeps its name: no new account can take it, so a second loan to the
  same person opens their old account again instead of creating another (Claude's call;
  archiving a category frees its name, which has no unarchive).
- Nothing else hides an archived account: `movement list --account <code>` still lists its
  movements, and `report` still counts them, so a trip paid from an account archived later
  keeps counting in its months.

## Examples

Invented figures. These outputs come from the real TOON encoder and are pasted again from
the real stdout and stderr once the commands exist.

A loan to Alex, account `k7f2`, paid back to 0, archived with a dry run:

```
dryRun: true
account:
  id: k7f2
  emoji: 🤝
  name: Alex
  type: cash
  currency: COP
  archived: true
  openingAmount: 0
  openingDate: 2026-07-02
  balance: 0
```

A USD account `k7f2` still holding 120.50 USD:

```
error:
  code: balance_not_zero
  account: k7f2
  currency: USD
  balance: 120.5
  message: account k7f2 holds 120.5 USD; only an account at 0 can be archived
```

Deleting a movement of the archived account `k7f2`, or the half of a transfer whose other
half sits in it, such as a 500,000 COP payment from Bank to Alex:

```
error:
  code: refused
  errors[1]{code,item,message}:
    archived,"delete[0]",account k7f2 is archived
  message: 1 item refused
```

## Changed

- `quaestor account list` hides archived accounts; `docs/features/recording-movements.md`
  says "archived ones included" today and is updated.
- `quaestor movement write` refuses a delete in an archived account.
- `docs/architecture.md` gains `balance_not_zero`, `not_found` for an account, and
  `archived` on a `delete[n]` item.
- The `record-movements` skill lists accounts with `--all` when it needs an archived one.
- The store does not change: every account already has its archived mark, so the release
  migrates nothing.

## Tests

- As `workflow.md` sets them: CLI tests through the entry point, each named after its rule
  or example, setup through commands.
- The `balance_not_zero` refusal is tested in USD.
- A property test, oracle the rule itself: for any movements and transfers, archiving
  succeeds exactly when the balance is 0, and once archived, no write changes the account's
  balance.

## Getting the real data ready

After Angelo merges and runs `pnpm release`, with the installed release, each write a dry run
Angelo approves:

1. In each account archived since the legacy app that holds misfiled rows: unarchive it,
   correct the rows, archive it again.
2. Archive the loan accounts back at 0.

## Approaches

Decided by Angelo on 2026-11-25:

- **The list**: hide archived accounts with a flag to see them, chosen; keep listing every
  account with its mark, dropped because a loan at 0 would never leave the list.
- **An account that is not at 0**: refused, chosen; allowed with the balance in the dry run,
  dropped because money could sit unseen in an archived account.
- **The commands**: `account archive` and `account unarchive`, chosen, as `category archive`
  does it; one `account edit --archived true|false`, dropped because it would change one
  thing and the other edits it could hold were never asked for.
- **Corrections in an archived account**: unarchive first, chosen in the backlog; letting a
  correction write into an archived account, not taken, because an archived account takes
  no change.

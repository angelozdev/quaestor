# Archiving an account: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `account archive` and `account unarchive`, an `account list` that hides archived
accounts unless `--all`, and an archived account that no write can move off 0.

**Architecture:** The store already has `accounts.archived`; no migration. The archive and
unarchive commands copy `category archive` (`src/shell/cli/commands/category-archive/`,
`archiveCategory` in `src/shell/db/categories/categories.ts`). The delete refusal lives in
the core's `checkWrite` (`src/core/ledger/ledger.ts`), fed by the shell's catalog.

**Tech Stack:** Node 26 with type stripping, commander, zod, Drizzle on `node:sqlite`, TOON,
vitest, fast-check.

**Spec:** `docs/features/account-archive.md`

## Global Constraints

- `docs/workflow.md` rules every task: test-first; CLI tests through `ledgerCli()`, setup
  through commands, named after the rule or example they cover; no spy, no SQL in a test.
- Never weaken, skip or delete a test. Changing an expectation because the behaviour
  changed on purpose (the `account` group's `missing_command` list, Task 1's plain
  `account list` once Task 3 hides archived accounts, the core test catalog's `movements`
  shape) is allowed and named in its task; anything else goes to Angelo.
- No code comments. Code, docs and tests in English.
- `pnpm check` is green at the end of every task: test, lint, format:check, typecheck, knip,
  jscpd (fails on any clone).
- Commit after each green task on branch `account-archive`, Conventional Commits. Never on
  `main`, never merge, never push, never `pnpm release`.
- Invented data only (Alex, Bank, `k7f2`): the repo is public.
- `listAccounts` keeps returning every account: `movement write` builds its catalog from it,
  so an archived account must stay in it to be refused as `archived`, not `not_found`.

## Client output

What Claude reads, from the real TOON encoder; stderr starts with `env: test` (or
`env: prod`) on every call that opens a store. Exit 0 unless stated.

`account archive k7f2 --dry-run` (`dryRun: false` without the flag):

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

`account unarchive k7f2` prints the same shape with `archived: false`.

`account archive k7f2` on a USD account holding 120.50, exit 1, stdout empty:

```
error:
  code: balance_not_zero
  account: k7f2
  currency: USD
  balance: 120.5
  message: account k7f2 holds 120.5 USD; only an account at 0 can be archived
```

`account list`, then `account list --all`:

```
accounts[1]{id,emoji,name,type,currency,archived,openingAmount,openingDate,balance}:
  n8d3,🏦,Bank,debit,COP,false,1000000,2026-01-13,1500000
```

```
accounts[2]{id,emoji,name,type,currency,archived,openingAmount,openingDate,balance}:
  k7f2,🤝,Alex,cash,COP,true,0,2026-07-02,0
  n8d3,🏦,Bank,debit,COP,false,1000000,2026-01-13,1500000
```

`movement write` deleting a movement of archived `k7f2`, or a transfer half whose partner is
in it, exit 1:

```
error:
  code: refused
  errors[1]{code,item,message}:
    archived,"delete[0]",account k7f2 is archived
  message: 1 item refused
```

`account archive zzzz` (and `unarchive`), exit 1: `not_found` with `kind: account`,
`value: zzzz`, `message: account zzzz does not exist`.

## Review Focus

- An account at 0 that has movements (+5, −5) archives: the rule is the balance, not "no
  movements". Test in Task 2.
- A dry run of an archive that would be refused is refused the same way, exit 1. Test in
  Task 2.
- A write that deletes one movement in an active account and one in an archived account is
  refused whole: nothing deleted, both balances unchanged. Test in Task 5.
- A delete from the active side of a transfer whose other half is archived is refused: one
  half deleted means both. Test in Task 5.
- An archived account still answers `movement list --account` and still counts in `report`.
  Test in Task 3.

---

### Task 1: `account archive` for an account at 0

**Files:**
- Modify: `src/shell/db/accounts/accounts.ts`, `src/shell/db/index.ts`
- Create: `src/shell/cli/commands/account-archive/account-archive.ts`,
  `account-archive.schema.ts`, `account-archive.test.ts`
- Modify: `src/shell/cli/main/main.ts` (register after `accountAddCommand`)
- Modify: `src/shell/cli/commands/account-list/account-list.test.ts` (expected
  `missing_command` list becomes `['list', 'add', 'archive']`: the group gained a command)

**Interfaces:**
- Produces: `archiveAccount(store: Store, id: string, now: Date): AccountRow`, exported from
  `#shell/db`; private `liveAccount(store, id): AccountRow` (from `listAccounts`, else
  `NotFoundError('account', id)`) and `setArchived(store, account: AccountRow, archived:
  boolean, now: Date): AccountRow` (updates `archived` and `updatedAt`, returns the row with
  the new mark and its unchanged balance).
- Produces: `accountArchiveCommand: CliCommand`, `name: 'archive'`, `group: 'account'`,
  description `archive an account at 0: it takes no change until unarchived`, argument
  `code` (`the account code, from account list`), options `[DRY_RUN_OPTION]`, output
  `{ dryRun, account }` inside `inTransaction(store, dryRun, ...)`.

- [ ] **Step 1: Write the failing tests** in `account-archive.test.ts`, setup with
  `addAccount(cli, 'Alex', 'USD', '0')` from `tests/support/books/books.ts`:
  - `account archive marks an account archived and account list shows it`: exit 0, stdout
    `encode({ dryRun: false, account: { ...row, archived: true } })`, stderr `env: test\n`;
    `account list` shows it with `archived: true` (hiding comes in Task 3).
  - `--dry-run on account archive shows it archived and changes nothing`: `expectWrite(run,
    true, { account: archivedRow })`, then `account list` still shows `archived: false`.
  - `archiving an archived account changes nothing`: second archive exits 0 with the same row.
  - `account archive with an unknown code exits 1 as not_found`: `notFound('account', 'zzzz')`.
  - `an archived account keeps its name`: `account add Alex ...` after the archive exits 1 as
    `alreadyExists('account', 'Alex')`.
- [ ] **Step 2: Run** `pnpm vitest run src/shell/cli/commands/account-archive` and see them
  fail with `unknown_command`.
- [ ] **Step 3: Implement** `archiveAccount` (returns the account unchanged when already
  archived) and the command, as `category archive` does.
- [ ] **Step 4: Run** `pnpm check`: green, the updated `missing_command` test included.
- [ ] **Step 5: Commit** `feat(accounts): archive an account`

### Task 2: only an account at 0 archives

**Files:**
- Modify: `src/core/ledger/ledger.errors.ts`, `src/core/ledger/index.ts`,
  `src/shell/db/accounts/accounts.ts`, `account-archive.test.ts`, `docs/architecture.md`

**Interfaces:**
- Produces: `class BalanceNotZeroError extends RefusedError`, `constructor(account: string,
  currency: string, balance: number)`, code `balance_not_zero`, data `{ account, currency,
  balance }`, message `account ${account} holds ${balance} ${currency}; only an account at 0
  can be archived`. `archiveAccount` throws it when an active account's `balance !== 0`.

- [ ] **Step 1: Write the failing tests:**
  - `an account that is not at 0 is refused as balance_not_zero (USD)`:
    `addAccount(cli, 'Wallet', 'USD', '120.50')`, archive exits 1, stdout `''`, stderr
    `env: test\n` plus the `balance_not_zero` block of Client output with `account` set to the
    real code; `account list` still shows `archived: false`.
  - `a dry run of an archive that is refused is refused the same way`: same with `--dry-run`.
  - `an account back at 0 after movements archives`: one movement `+5` and one `-5` in a USD
    account opened at 0 (use `spend` with `amount`), then archive exits 0.
- [ ] **Step 2: Run** them and see the first two fail with exit 0.
- [ ] **Step 3: Implement** the error and the check in `archiveAccount`.
- [ ] **Step 4:** Add to the codes in `docs/architecture.md`, after `group_not_empty`:
  `` `balance_not_zero`, 1, when an account to archive is not at 0, with the `account`, its
  `currency` and its `balance`; ``
- [ ] **Step 5: Run** `pnpm check`: green.
- [ ] **Step 6: Commit** `feat(accounts): only an account at 0 can be archived`

### Task 3: `account list` hides archived accounts, `--all` shows them

**Files:**
- Modify: `src/shell/cli/commands/account-list/account-list.ts`,
  `account-list.test.ts`; Create: `account-list.schema.ts`
- Modify: `docs/features/recording-movements.md` (the `account list` line: "the active
  accounts with their balance today; `--all` adds the archived ones"),
  `.claude/skills/record-movements/SKILL.md` (line on `account list`: it lists active
  accounts; `account list --all` finds an archived one; a correction in an archived account is
  unarchive, correct, archive again, each a dry run Angelo approves)

**Interfaces:**
- Produces: option `{ flags: '--all', description: 'include archived accounts' }`; schema
  `fields({ all: z.boolean().default(false) })`; the command filters
  `listAccounts(store)` by `all || !account.archived`. `listAccounts` itself is unchanged.

- [ ] **Step 1: Write the failing tests** in `account-list.test.ts`:
  - `account list leaves out archived accounts and --all includes them`: Bank active, Alex
    archived; stdout is exactly the two Client output tables (with the real codes).
  - `an archived account still lists its movements and still counts in report`: a movement in
    a USD account, the account settled to 0 and archived, then `movement list --account
    <code>` lists both rows and `report` over that day with `rate set USD 4000` counts them.
- [ ] **Step 2: Run** them; the first fails (archived account shown).
- [ ] **Step 3: Implement** the flag and the filter; update Task 1's test that expected the
  archived account in plain `account list` to read it from `account list --all` (the
  behaviour changed on purpose in this task).
- [ ] **Step 4:** Update the two docs above.
- [ ] **Step 5: Run** `pnpm check`: green.
- [ ] **Step 6: Commit** `feat(accounts): account list hides archived accounts`

### Task 4: `account unarchive`

**Files:**
- Modify: `src/shell/db/accounts/accounts.ts`, `src/shell/db/index.ts`,
  `src/shell/cli/commands/account-archive/account-archive.ts`, `account-archive.test.ts`,
  `src/shell/cli/main/main.ts`, `account-list.test.ts` (`missing_command` list becomes
  `['list', 'add', 'archive', 'unarchive']`)

**Interfaces:**
- Produces: `unarchiveAccount(store: Store, id: string, now: Date): AccountRow` (unchanged
  when already active), exported from `#shell/db`.
- Produces: `accountUnarchiveCommand: CliCommand`, `name: 'unarchive'`, description `open an
  archived account again`, same argument, option and output shape as archive. Both commands
  come from one private function in `account-archive.ts`, so jscpd sees no clone.

- [ ] **Step 1: Write the failing tests:**
  - `account unarchive opens an archived account and account list shows it again`.
  - `--dry-run on account unarchive shows it active and changes nothing`.
  - `unarchiving an active account changes nothing`.
  - `account unarchive with an unknown code exits 1 as not_found`.
  - `a correction in an archived account is unarchive, correct, archive again`: a USD account
    with `+5` and `-5` in one category, archived; unarchive; one `movement write` deletes the
    `+5` and records it in another category; archive exits 0 with balance 0.
- [ ] **Step 2: Run** them and see them fail with `unknown_command`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pnpm check`: green.
- [ ] **Step 5: Commit** `feat(accounts): unarchive an account`

### Task 5: an archived account takes no delete

**Files:**
- Modify: `src/core/ledger/ledger.types.ts`, `src/core/ledger/ledger.ts`,
  `src/core/ledger/ledger.test.ts` (its `catalogOf` builds `movements: new Map()`: the
  catalog's shape changed on purpose), `src/shell/db/movements/movements.ts`,
  `src/shell/cli/commands/movement-write/movement-write.test.ts`
- Modify: `docs/features/recording-movements.md` ("An archived account receives no new
  movement" becomes "...no new movement and no delete; see `account-archive.md`")

**Interfaces:**
- Produces: `Catalog.movements: Map<string, string[]>`, each live code to be deleted mapped to
  the accounts its delete touches: its own and, for a transfer half, its live partner's.
- Produces: in `checkWrite`, a code missing from the map stays `not_found`; otherwise each
  touched account that is archived adds `archived(`delete[${index}]`, 'account', id)`.
- Produces: in `movements.ts`, `liveCodes` becomes `deleteTargets(store, codes): Map<string,
  string[]>`, selecting `movements.id`, `movements.accountId` and the partner's account
  through the existing `partner` alias and `PARTNER_IS_LIVE`.

- [ ] **Step 1: Write the failing CLI tests** in `movement-write.test.ts`:
  - `a movement in an archived account cannot be deleted`: refused with the Client output
    block; `movement list` and the balance unchanged.
  - `a transfer whose other half sits in an archived account cannot be deleted`: Wallet to
    Savings 10 USD and back, Savings at 0 archived, delete the first transfer's Wallet half:
    refused naming Savings.
  - `a write deleting in an active and an archived account is refused whole`: nothing deleted.
  - Property, `an archived account stays at 0: it archives exactly when its balance is 0, and
    no write moves it after`: `fc.asyncProperty(booked(OPENING_DATE), fc.boolean(), ...)`,
    `numRuns: 50`; write the items through `bookedMovements`; when the boolean is true and
    Savings is not at 0, write one movement of the opposite sum to it; archive Savings. The
    oracle is the sum of the Savings cents: at 0, archive exits 0, then a write deleting every
    live Savings movement and adding one more exits 1 and `account list --all` shows Savings
    at 0; otherwise archive exits 1 `balance_not_zero` with that sum / 100 and Savings stays
    active.
- [ ] **Step 2: Run** them; the delete tests fail with exit 0.
- [ ] **Step 3: Implement** the catalog change and the check; update `catalogOf` in the core
  test.
- [ ] **Step 4:** Update `recording-movements.md`.
- [ ] **Step 5: Run** `pnpm check`: green.
- [ ] **Step 6: Commit** `feat(movements): an archived account takes no delete`

### Task 6: check against a copy of the real data, close the docs (exception: no new behaviour)

- [ ] **Step 1:** `quaestor backup` with the installed release (stderr says `env: prod`),
  copy that backup into the scratchpad, and run the sources against it with
  `QUAESTOR_DB=<absolute copy path> pnpm quaestor`: `account list --all`, then for each
  account archived since the legacy app, `account unarchive`, one misfiled row deleted and
  recorded again in its same category (Angelo picks the real categories later, in `prod`),
  and `account archive`; then `account archive --dry-run` on the loan accounts at 0. Every balance matches in cents what the copy showed
  before; nothing real is written into the repo.
- [ ] **Step 2:** Re-paste the examples in `docs/features/account-archive.md` from the real
  stdout and stderr of `pnpm quaestor` on a test store; remove item 2 from
  `docs/backlog.md` and renumber; set the feature's Status to `built, not released`.
- [ ] **Step 3: Run** `pnpm check`: green.
- [ ] **Step 4: Commit** `docs: archiving an account is built`. The plan is deleted after
  Angelo merges and releases.

# Recording Movements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude imports the legacy export and keeps every account's balance equal to the
bank's by recording, transferring and deleting movements through `quaestor`, from bank
screenshots, with a dry run first.

**Architecture:** Rules a write must obey live in `#core/ledger` as pure functions over a
catalog the shell loads. Tables, sums and running balances live in `src/shell/db`, and every
write runs in one SQLite transaction that `--dry-run` rolls back. The legacy mapping is pure,
in `#core/legacy`, and reading the export is `#shell/legacy`.

**Tech Stack:** Node 26, TypeScript 7 (type stripping), commander 15, zod 4, drizzle-orm and
drizzle-kit 1.0.0-rc.5 over `node:sqlite`, `@toon-format/toon` 4.4.0, vitest 5. `Temporal`
and `Intl.supportedValuesOf('currency')` come from Node itself.

**Spec:** `docs/features/recording-movements.md`. Project rules: `docs/architecture.md`,
`docs/stack.md`, `docs/workflow.md`.

## Decisions for Angelo

These are hard to change once real data sits on them.

- **Commands.** `quaestor account list`, `quaestor account add <name>`,
  `quaestor category list`, `quaestor category add <name>`, `quaestor tag list`,
  `quaestor tag add <name>`, `quaestor movement list`, `quaestor movement write` (JSON on
  stdin: records, transfers and deletes in one go), and `quaestor import <folder>`. Every write
  takes `--dry-run`. Flags carry one thing; a batch goes as JSON on stdin, as AWS does with
  `route53 change-resource-record-sets --change-batch`. Confirmed by Angelo on 2026-11-24.
- **Codes, not sequences.** Accounts, categories and movements are identified by a random
  four-character code from `0123456789abcdefghjkmnpqrstvwxyz`, as Aletheia's cards are:
  `n8d3`, `k7f2`. A code already taken is drawn again, so two never share one, and 1,048,576
  fit in each list. The import gives every legacy row a new code, so the legacy numbers are
  not kept. Decided by Angelo on 2026-11-24.
- **Claude names things by code.** Claude never refers to an account or a category by its
  name: two categories are called Gifts. Tags are referred to by name.
- **Emoji apart.** An account and a category carry their emoji in a field of their own, apart
  from the name: `🏦` and `Bank`. Decided by Angelo on 2026-11-24.
- **Storage.** There are four lists: accounts, categories, tags and movements, plus which tags
  each movement carries. A transfer is two movements that share a link. A balance is never
  stored: it is the opening balance plus the sum of the account's movements. Movements on the
  same day keep the order they were stored in, through a hidden `seq INTEGER PRIMARY KEY`
  that Claude never sees: they are ordered by `(date, seq)`. Every list carries `created_at`,
  `updated_at` and `deleted_at`, and deleting marks `deleted_at` instead of removing the row.
  Decided by Angelo on 2026-11-24.
- **Amounts are written as the bank shows them.** Claude gives each amount as text with a dot
  before at most two decimals and no thousands separator: COP $15.000 is `"-15000"`, USD
  $30,39 is `"-30.39"`, KRW ₩15.000 is `"-15000"`. `quaestor` gives it back as a number,
  `-15000` or `-30.39`. A COP amount copied as `"-15.000"` has three decimals and is refused.
  Every currency is stored as integer cents, KRW included, so `quaestor` keeps no table of
  decimals per currency; Node's says COP has none. Decided by Angelo on 2026-11-24. Every movement given to `quaestor` states
  its currency, and `quaestor` refuses one that differs from its account's.
- **Reading movements.** Each row carries its account's balance after it, even when the list
  mixes accounts; tags come out as one space-joined text so the rows stay one TOON table, and
  go in as a list. `movement list` lists at most `--limit` movements, 50 by default, the most recent ones, newest first, and `total` says how many matched. Confirmed by Angelo on 2026-11-24.
- **Refusals.** A write that breaks a rule is refused whole, and every item at fault is listed
  at once, one line each, so Claude fixes them all in one round. Decided by Angelo on
  2026-11-24.
- **Order.** Prod's first write is the import. Nothing writes to `~/.quaestor/prod.sqlite`
  before the import (Task 8) has run there, even if a release ships an earlier slice.

## What Claude reads

Every store command writes `env: <name>` on stderr first. The examples below were rendered
with `@toon-format/toon` `encode`, using invented values; `--json` gives the same object on
one line. Amounts come out as numbers in the currency's units: `-15000` is −15.000 COP and
`95.5` is 95,50 USD.

`quaestor account list`, exit 0:

```
accounts[3]{id,emoji,name,type,currency,archived,openingAmount,openingDate,balance}:
  w2k9,💵,Wallet,debit,USD,false,120,2026-01-05,95.5
  n8d3,🏦,Bank,debit,COP,false,0,null,1500000
  c4tz,💳,Card,credit,COP,false,0,2026-11-24,-45000
```

`quaestor account add Savings --emoji 🏦 --type savings --currency COP --opening 500000 --opening-date 2026-11-24 --dry-run`,
exit 0:

```
dryRun: true
account:
  id: f6m1
  emoji: 🏦
  name: Savings
  type: savings
  currency: COP
  archived: false
  openingAmount: 500000
  openingDate: 2026-11-24
  balance: 500000
```

`quaestor category list` and `quaestor tag list`, exit 0:

```
categories[4]{id,emoji,name,archived}:
  q5d0,null,Food,true
  r3sb,🍽️,Restaurants,false
  x9ta,🚕,Rideshare/Taxi,false
  a7hn,🛡️,Gifts,true
```

```
tags[2]: "trip:lima-2026","who:alex"
```

`quaestor tag add trip:japon-2027 --dry-run`, exit 0:

```
dryRun: true
tag: "trip:japon-2027"
```

`quaestor movement write --dry-run`, a correction (delete h4vw, record it again) plus a
cross-currency transfer, exit 0:

```
dryRun: true
deleted[1]{id,date,account,payee,amount,currency,category,tags,note,transfer}:
  h4vw,2026-11-20,n8d3,Uber,-25000,COP,x9ta,"",null,null
recorded[3]{id,date,account,payee,amount,currency,category,tags,note,transfer}:
  k7f2,2026-11-20,n8d3,Uber,-15000,COP,x9ta,"",null,null
  m3pe,2026-11-21,w2k9,To Bank,-100,USD,null,"",null,3qxa
  3qxa,2026-11-21,n8d3,From Wallet,400000,COP,null,"",null,m3pe
balances[2]{account,currency,before,after}:
  n8d3,COP,1110000,1520000
  w2k9,USD,195.5,95.5
```

The stdin it reads. Every amount is text, as the bank shows it, with a dot before at most two
decimals and no thousands separator:

```json
{
  "delete": [
    "h4vw"
  ],
  "movements": [
    {
      "account": "n8d3",
      "date": "2026-11-20",
      "payee": "Uber",
      "amount": "-15000",
      "currency": "COP",
      "category": "x9ta"
    }
  ],
  "transfers": [
    {
      "from": {
        "account": "w2k9",
        "date": "2026-11-21",
        "payee": "To Bank",
        "amount": "-100",
        "currency": "USD"
      },
      "to": {
        "account": "n8d3",
        "date": "2026-11-21",
        "payee": "From Wallet",
        "amount": "400000",
        "currency": "COP"
      }
    }
  ]
}
```

`quaestor movement list --account n8d3 --from 2026-11-20`, exit 0. `balance` is the row's
account's balance after that movement, counting every earlier movement, including those before
`--from`. `total` counts every movement the filters match; at most `--limit` (50 by default)
are listed, newest first:

```
total: 2
movements[2]{id,date,account,payee,amount,currency,category,tags,note,transfer,balance}:
  3qxa,2026-11-21,n8d3,From Wallet,400000,COP,null,"trip:lima-2026",cambio a 4.000,m3pe,1500000
  k7f2,2026-11-20,n8d3,Uber,-15000,COP,x9ta,"",null,null,1100000
```

`quaestor import ~/.quaestor/legacy --dry-run`, exit 0:

```
dryRun: true
imported:
  accounts: 3
  categories: 4
  tags: 2
  movements: 9
  tagLinks: 2
openings[1]{account,name,amount,currency,date}:
  w2k9,Wallet,120,USD,2026-01-05
```

A refusal leaves stdout empty and exits 1. The error goes on stderr after the `env:` line. A
write that breaks rules lists every item at fault at once:

```
error:
  code: refused
  errors[3]{code,item,message}:
    not_found,"movements[2]",category zz99 does not exist
    archived,"movements[5]",account c4tz is archived
    currency_mismatch,"transfers[0].from","account w2k9 holds USD, not COP"
  message: 3 items refused
```

An amount copied from a COP screen as `"-15.000"`:

```
error:
  code: invalid_input
  issues[2]: "movements[0].amount: must be an amount like \"-15000\" or \"-30.39\": no thousands separator, at most 2 decimals","movements[1].date: must be a date like 2026-11-24"
  message: "movements[0].amount: must be an amount like \"-15000\" or \"-30.39\": no thousands separator, at most 2 decimals; movements[1].date: must be a date like 2026-11-24"
```

## Global Constraints

- Dependencies: only `drizzle-kit` 1.0.0-rc.5 enters, already chosen in `docs/stack.md`.
  Nothing else is added.
- Layout as in `architecture.md`: `<name>.ts`, `.types.ts`, `.errors.ts`, `.constants.ts`,
  `.schema.ts` and `.test.ts` per module, an `index.ts` barrel per concept, kebab-case file
  names, and no comments (the `local/no-comments` lint, which also rules out ponytail
  `shortcut:` notes).
- `src/core` imports no `node:*`, `drizzle-orm` or `#shell/*`. Only `src/shell/db` imports
  `node:sqlite` and `drizzle-orm`. `tests/support/store` may use `node:sqlite`.
- An amount is signed: positive money in, negative money out. Stored, it is a non-zero integer
  in cents for every currency. Claude writes it as text matching
  `AMOUNT_PATTERN = /^-?\d+(\.\d{1,2})?$/`, turned into cents by `centsOf(text)` without
  floating point, and reads it as a number, `amountOf(cents) = cents / 100`. Both live in
  `#core/ledger`, and every amount Claude reads (`amount`, `balance`, `openingAmount`,
  `before`, `after`) goes through `amountOf`. A
  currency is a member of `Intl.supportedValuesOf('currency')`. A date is `YYYY-MM-DD` and a
  real calendar day (`z.iso.date()`).
- A code is `ID_LENGTH = 4` characters from `ID_ALPHABET = '0123456789abcdefghjkmnpqrstvwxyz'`,
  drawn with the injected `randomIndex` and drawn again while the insert hits a taken one.
  Movements are ordered by `(date, seq)`, never by code.
- `accounts`, `categories`, `tags` and `movements` carry `created_at` and `updated_at` (not
  null) and `deleted_at` (null until deleted): UTC ISO instants with milliseconds from
  `context.clock`, such as `2026-11-24T21:04:05.123Z`. Every read filters `deleted_at IS NULL`,
  and every unique index is partial on `deleted_at IS NULL`.
- Every write takes `--dry-run`. A dry run is the same transaction rolled back, and every
  write's stdout starts with `dryRun: <true|false>`.
- Each failure is a class extending `RefusedError` (exit 1) or `FailedError` (exit 2), and its
  stderr object holds `code` first, then data, then `message`. `ErrorData` widens to
  `Record<string, string | number | string[] | Record<string, string>[]>`.
- Tests are of behaviour only. Every test runs `quaestor` through `runCli` and asserts what it
  prints and its exit code. No test calls a core or store function, reads a table or writes
  SQL, and setup goes through commands too: an archived account or category comes from
  importing the fixture, since no command archives. The clock and `randomIndex` are injected
  as the skeleton injects the clock. Every rule and example in the spec has a test whose name
  states the rule; every money figure is also tested in USD; fixtures are invented; no test
  reads `~/.quaestor`. Decided by Angelo on 2026-11-24.
- Migrations: one per task that changes tables, generated with
  `pnpm db:generate --name <name>`, its SQL read before committing, never edited once
  committed.
- `architecture.md` "Codes so far" gains each new code with its exit code in the task that
  introduces it.
- Commit after each green step on `recording-movements`, with Conventional Commits.
- `pnpm check` is green at the end of every task.

## Review Focus

1. A running balance under `--from` still counts every earlier movement of that account. Tested in Task 5.
2. The payee filter ignores case and accents, so `--payee exito` finds `Éxito` and `--payee UBER`
   finds `Uber`. SQLite's own case folding is ASCII-only. Tested in Task 5.
3. A delete list can name the same code twice, or both halves of one transfer. Each movement
   is deleted once and listed once. Tested in Task 7.
4. Empty stdin on `movement write` is `invalid_json`, not a crash or an empty write. Tested in Task 4.
5. Amount format: `"-15.000"` copied from a COP screen, where the dot separates thousands, is
   refused for its three decimals (Task 4). `"-15.00"` would still pass as 15 pesos and only the
   balance after shows it, so the skill makes Claude compare `balances[].after` with the bank
   before asking for the yes, and states the format (Task 9).

## File map

- `src/core/ledger/`: `ledger.ts` (`isCurrency`, `drawCode`, `checkWrite`, `matchesPayee`),
  `ledger.types.ts`, `ledger.constants.ts`, `ledger.errors.ts`, `index.ts`.
- `src/core/legacy/`: `legacy.ts` (`ledgerFrom`), `legacy.types.ts`, `index.ts`.
- `src/shell/db/database/database.ts`: gains `inTransaction`, the foreign-keys pragma and
  `isUniqueViolation`.
- `src/shell/db/accounts/`, `categories/`, `tags/`, `movements/` and `legacy-import/`: each
  holds `<name>.schema.ts` (its tables), and `<name>.ts` (its
  queries).
- `src/shell/legacy/export/`: `export.ts` (`readLegacyExport`), `export.schema.ts`,
  `export.errors.ts`, plus `src/shell/legacy/index.ts`.
- `src/shell/cli/invocation/stdin/` and `input/`: JSON on stdin, and zod issues turned into
  `invalid_input`.
- `src/shell/cli/commands/<group>-<name>/`: one folder per command, plus `import/`.
- `tests/support/ledger/`: `ledgerCli`, which runs commands against a temp store with the
  shipped migrations. `tests/support/legacy-export/` writes an invented export.
- `drizzle.config.ts`, the `db:generate` script, `migrations/<timestamp>_<name>/`.
- `.claude/skills/record-movements/SKILL.md`, `tests/skills/record-movements.test.ts`.

---

### Task 1: `account list` on a fresh store

The thinnest end-to-end slice. It also lays the shared setup: drizzle-kit, the first table,
command groups and the test helper.

**Files:**

- Create: `drizzle.config.ts` (dialect `sqlite`, schema `./src/shell/db/**/*.schema.ts`, out
  `./migrations`); `src/core/ledger/{ledger.constants.ts,ledger.types.ts,index.ts}`;
  `src/shell/db/accounts/{accounts.schema.ts,accounts.ts}`;
  `src/shell/cli/commands/account-list/{account-list.ts,account-list.test.ts}`;
  `tests/support/ledger/{ledger.ts,ledger.types.ts}`; `migrations/<ts>_accounts/`.
- Modify: `package.json` (`drizzle-kit` 1.0.0-rc.5, `"db:generate": "drizzle-kit generate"`);
  `src/shell/db/database/database.ts` (`PRAGMA foreign_keys = ON` right after opening);
  `src/shell/db/index.ts`; `src/shell/cli/main/{main.ts,main.types.ts,main.constants.ts}`;
  `src/shell/cli/main/main.test.ts`; `src/core/errors/errors.types.ts`.

**Interfaces:**

- Produces: `ACCOUNT_TYPES = ['savings', 'debit', 'credit', 'cash'] as const`;
  `type AccountType`; `type Account = { id: string; emoji: string | null; name: string; type: AccountType; currency:
  string; archived: boolean; openingAmount: number; openingDate: string | null }`;
  `type AccountRow = Account & { balance: number }`;
  `listAccounts(store: Store): AccountRow[]`, by name.
- Produces in `main.types.ts`: `CliCommand` gains `group?: CommandGroup`,
  `argument?: { name: string; description: string }` and
  `options?: { flags: string; description: string; defaultValue?: string }[]`, and
  `run(context, options: GlobalOptions, args: string[], flags: Flags): Promise<unknown>`.
  `type Flags = Record<string, string | boolean | undefined>`. In `main.constants.ts`:
  `COMMAND_GROUPS = { account: 'accounts and their balances', category: 'categories a movement
  can take', tag: 'tags a movement can carry', movement: 'movements and transfers' }`.
- Produces: `ledgerCli(): { dataDir: string; run(argv: string[], stdin?: string):
  Promise<CliRun> }`, which runs `runCli` with `dataDir` set to a `tempDir`, `defaultEnv`
  `'test'` and `migrationsDir: SHIPPED_MIGRATIONS`.

Table `accounts`: `id` text primary key, a code (four characters from `ID_ALPHABET`, checked in SQL with `length(id) = 4 AND id NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`); `emoji` text; `name` text not null and not
blank, unique among rows not deleted; `type` text not null in `ACCOUNT_TYPES`; `currency` text not null, three uppercase
letters; `archived` integer boolean not null default false; `opening_amount` integer not null
default 0; `opening_date` text, null or a valid date; check `opening_amount = 0 OR opening_date IS NOT NULL`; `created_at`, `updated_at` text not
null; `deleted_at` text.

- [ ] **Step 1: Write the failing tests**

```ts
it('account list on a fresh store prints no accounts', async () => {
  const { code, stdout, stderr } = await ledgerCli().run(['account', 'list'])
  expect(code).toBe(0)
  expect(stdout).toBe(`${encode({ accounts: [] })}\n`)
  expect(stderr).toBe('env: test\n')
})
it('a bare group exits 1 as missing_command with its own commands', async () => {
  const { code, stderr } = await ledgerCli().run(['account'])
  expect(code).toBe(1)
  expect(stderr).toBe(`${encode({ error: { code: 'missing_command', commands: ['list'],
    message: 'missing command: use one of list' } })}\n`)
})
it('account help is not a command and exits 1 as excess_arguments', ...)
```

In `main.test.ts`, two expectations change because the contract grows: `--help` lists
`backup`, `account` and every later group, and the bare-call `missing_command` lists them all
(`commands: ['backup', 'account']` in this task). Both are stated here so the change is not
mistaken for weakening a test.

- [ ] **Step 2: Run them and see them fail**

Run: `pnpm test src/shell/cli/commands/account-list`. Expected: FAIL, unknown command
`account`.

- [ ] **Step 3: Implement**

Write the schema. Generate the migration with `pnpm db:generate --name accounts` and read the
SQL. Write `listAccounts`, with balance = `opening_amount` for now. Then do the group
registration: a group command gets `.helpCommand(false)` and an action that throws
`MissingCommandError` with its subcommand names. Finally add `accountListCommand`, which
returns `{ accounts: listAccounts(store) }`.

- [ ] **Step 4: Run `pnpm check`**

Expected: green, with knip seeing `drizzle.config.ts`.

- [ ] **Step 5: Commit**

`feat(cli): account list on a fresh store`

---

### Task 2: `account add` with its dry run

**Files:**

- Create: `src/shell/cli/commands/account-add/{account-add.ts,account-add.schema.ts,account-add.test.ts}`;
  `src/shell/cli/invocation/input/{input.ts,input.schema.ts,input.constants.ts,input.errors.ts}`;
  `src/core/ledger/{ledger.ts,ledger.errors.ts}`.
- Modify: `src/shell/db/database/database.ts`, `src/shell/db/accounts/accounts.ts`,
  `src/shell/cli/main/{main.ts,main.types.ts}`, `context.types.ts`, `bin.ts`, `released.ts`,
  `tests/support/run-cli/run-cli.ts`, `docs/architecture.md`.

**Interfaces:**

- Produces: `inTransaction<T>(store: Store, dryRun: boolean, work: () => T): T`, which commits,
  rolls back on a dry run, and rolls back and rethrows on a throw.
  `isUniqueViolation(error: unknown): boolean`.
- Produces: `ID_ALPHABET`, `ID_LENGTH`, `type RandomIndex = (bound: number) => number` and
  `drawCode(randomIndex: RandomIndex): string` in `#core/ledger`. `CliContext` gains
  `randomIndex`: `crypto.randomInt` in `bin.ts` and `released.ts`, and a deterministic
  sequence by default in `runCli`, overridable per test.
- Produces: `type AccountDraft = { emoji: string; name: string; type: AccountType; currency:
  string; openingAmount: number; openingDate: string }`;
  `type WriteDeps = { randomIndex: RandomIndex; now: Date }`;
  `insertAccount(store, draft, deps: WriteDeps): AccountRow`, which sets `created_at` and
  `updated_at` to `now`.
  It throws `AlreadyExistsError('account', name)`, code `already_exists`, data
  `{ kind, name }`, message `account <name> already exists`.
- Produces: `isCurrency(code: string): boolean`; `AMOUNT_PATTERN`, `centsOf(text: string):
  number` and `amountOf(cents: number): number`.
- Produces: `parsed<T>(schema: z.ZodType<T>, value: unknown): T`, which throws
  `InvalidInputError(issues: string[])`: code `invalid_input`, data `{ issues }`, message the
  issues joined by `; `, each issue `<path>: <message>`. Shared pieces in `input.schema.ts`:
  - `requiredText`: `is required`.
  - `dateText`: `must be a date like 2026-11-24`.
    - `amountText`: text matching `AMOUNT_PATTERN`, turned into cents, `must be an amount like
    "-15000" or "-30.39": no thousands separator, at most 2 decimals`. A JSON number gets the
    same message.
  - `currencyCode`: `must be an ISO 4217 code such as COP`.
  - `oneOf(values)`: `must be one of savings, debit, credit or cash`.
  - `emojiText`: exactly one emoji, `/^\p{RGI_Emoji}$/v`, `must be one emoji such as 🏦`.
  - An unknown key: `is not a field`.
- Produces: `DRY_RUN_OPTION = { flags: '--dry-run', description: 'do everything but commit,
  and show what would change' }`.

Flags: `account add <name> --emoji <emoji> --type <type> --currency <code> --opening <amount>
--opening-date <date> [--dry-run]`. `--opening` defaults to `0`, `--opening-date` is
required. Output: `{ dryRun, account: AccountRow }`.

- [ ] **Step 1: Write the failing tests**
  - `an account is created with its opening balance as its balance (USD)`:
    `Wallet --emoji 💵 --type debit --currency USD --opening 120.50 --opening-date 2026-01-05`
    makes `account list` show balance `120.5`.
  - `an account keeps its emoji apart from its name`: `emoji: 💵`, `name: Wallet`.
  - `an emoji field that is not exactly one emoji is refused`: `🏦🏦` and `A`.
    - `an account gets a four-character code`: `id` matches `/^[0-9a-hjkmnp-tv-z]{4}$/`.
  - `two accounts never share a code, even when the draw repeats`: with a `randomIndex` whose
    second account's first draw repeats the first code, both accounts are created with
    different codes.
  - `a credit card in debt opens with a negative balance`: `--opening -45000` gives balance
    `-45000`.
  - `--dry-run shows the account and leaves the store unchanged`: stdout `dryRun: true`, and
    `account list` is still empty.
  - `a currency that is not ISO 4217 is refused`: `--currency UDS` exits 1 `invalid_input` with
    issue `currency: must be an ISO 4217 code such as COP`.
  - `a type outside savings, debit, credit and cash is refused`.
  - `an account name already taken is refused`: exits 1 `already_exists`, kind `account`.
    - `an opening amount with a thousands separator or more than two decimals is refused`:
    `--opening 15.000` and `--opening 1,500`.
  - `the opening date is required`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement** `accountAddCommand`: parse the flags with zod, then
  `inTransaction(store, dryRun, () => insertAccount(...))`. `insertAccount` maps
  `isUniqueViolation` to `AlreadyExistsError`. The `main.ts` registration passes `args` and
  the command's own `opts()`.
- [ ] **Step 4: `pnpm check` green.** Add `already_exists`, 1 and `invalid_input`, 1 to
  "Codes so far" in `architecture.md`. In its Money section, add: integer cents hold for every
  currency, KRW included, and the CLI takes an amount as text and gives it back as a number.
- [ ] **Step 5: Commit**: `feat(cli): account add with a dry run`.

---

### Task 3: categories and tags

**Files:**

- Create: `src/shell/db/categories/*`, `src/shell/db/tags/*`;
  `src/shell/cli/commands/{category-add,category-list,tag-add,tag-list}/*`;
  `migrations/<ts>_categories_and_tags/`.
- Modify: `src/core/ledger/ledger.constants.ts` (`TAG_PATTERN = /^[a-z0-9:-]+$/`),
  `src/core/ledger/ledger.types.ts`, `src/shell/db/index.ts`, `main.ts`, `main.test.ts`.

**Interfaces:**

- Produces: `type Category = { id: string; emoji: string | null; name: string; archived:
  boolean }`; `insertCategory(store, { emoji, name }, deps: WriteDeps): Category`;
  `listCategories(store): Category[]` by name;
  `insertTag(store, name, now: Date): string`; `listTags(store): string[]` sorted.

Tables: `categories` has `id` text primary key, a code (four characters from `ID_ALPHABET`, checked in SQL with `length(id) = 4 AND id NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`), `emoji` text, `name` text not
null and not blank, `archived` integer boolean not null default false, and a unique index on `name`
`WHERE archived = 0 AND deleted_at IS NULL`. `tags` has `name` text primary key matching
`TAG_PATTERN`. Both carry `created_at`, `updated_at` and `deleted_at`.

- [ ] **Step 1: Write the failing tests**
  - `category add creates a category and category list shows it with its code`:
    `category add Games --emoji 🎮`.
  - `a category keeps its emoji apart from its name`.
  - `an unknown category name can be added once; a second active one is refused`: exits 1
    `already_exists`, kind `category`.
  - `tag add creates a tag; tag list shows it`: `trip:japon-2027`.
  - `a tag outside lowercase letters, digits, colons and dashes is refused`: `Trip Japón`
    exits 1 `invalid_input`, message `name: must be lowercase letters, digits, colons and
    dashes`.
  - `a tag already there is refused`.
  - `--dry-run on category add and tag add writes nothing`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Use the same command shape as `account add`. Keep the four
  commands thin enough that `jscpd` stays green, and extract a helper for any repeated block.
- [ ] **Step 4: `pnpm check` green.**
- [ ] **Step 5: Commit**: `feat(cli): categories and tags`.

---

### Task 4: recording movements

**Files:**

- Create: `src/shell/db/movements/{movements.schema.ts,movements.ts,movements.types.ts}`;
  `src/shell/cli/invocation/stdin/{stdin.ts,stdin.errors.ts,stdin.constants.ts}`;
  `src/shell/cli/commands/movement-write/{movement-write.ts,movement-write.schema.ts,movement-write.test.ts}`;
  `migrations/<ts>_movements/`.
- Modify: `main.types.ts` (`CliContext.stdin: () => Promise<string>`),
  `context.types.ts` (`InvocationContext` also omits `stdin`), `bin.ts` and `released.ts`
  (`stdin: processStdin`), `tests/support/run-cli/run-cli.ts` (default stdin `''`),
  `src/shell/db/accounts/accounts.ts` (balance = opening + sum of movements),
  `src/core/ledger/{ledger.ts,ledger.types.ts,ledger.errors.ts,index.ts}`,
  `main.test.ts`, `docs/architecture.md`.

**Interfaces:**

- Consumes: `inTransaction`, `parsed`, `listAccounts`.
- Produces in `#core/ledger`:
  - `type MovementDraft = { account: string; date: string; payee: string; amount: number;
    currency: string; category: string; tags: string[]; note: string | null }`.
  - `type HalfDraft = Omit<MovementDraft, 'category'>`.
  - `type TransferDraft = { from: HalfDraft; to: HalfDraft }`.
  - `type WriteRequest = { delete: string[]; movements: MovementDraft[]; transfers:
    TransferDraft[] }`.
  - `type Catalog = { accounts: Map<string, Account>; categories: Map<string, Category>;
    tags: Set<string>; movements: Set<string> }`, where `movements` holds the codes asked to
    be deleted that exist.
    - `type WriteProblem = { code: string; item: string; message: string }`.
  - `checkWrite(request: WriteRequest, catalog: Catalog): WriteProblem[]`, pure. It returns
    every problem in input order, `item` being `movements[i]` (later `transfers[i].from`,
    `transfers[i].to` and `delete[i]`):
    - `not_found`: `<kind> <id> does not exist`.
    - `currency_mismatch`: `account <account> holds <expected>, not <currency>`.
    - `before_opening`: `account <account> opens on <openingDate>, after <date>`.
  - `RefusedWriteError(problems: WriteProblem[])` in `ledger.errors.ts`: a `RefusedError`,
    code `refused`, data `{ errors: problems }`, message `1 item refused` or
    `<n> items refused`.
- Produces: `readJson(context: CliContext): Promise<unknown>`, which throws `InvalidJsonError`:
  `invalid_json`, message `invalid JSON on stdin: <reason on one line>`.
- Produces: `type MovementRow = { id: string; date: string; account: string; payee: string;
  amount: number; currency: string; category: string | null; tags: string; note: string |
  null; transfer: string | null }`, where `tags` is space-joined and `transfer` is the other
  half's code. `type BalanceChange = { account: string; currency: string; before: number;
  after: number }`. `type WriteResult = { deleted: MovementRow[]; recorded: MovementRow[];
  balances: BalanceChange[] }`.
- Produces: `writeMovements(store: Store, request: WriteRequest, deps: WriteDeps):
  WriteResult`. It loads the
  catalog and calls `checkWrite`, throwing `RefusedWriteError` when it returns any problem, then
  reads the touched accounts' balances, writes in order
  (deletes, movements, transfers), reads the balances again, and returns the result with
  `balances` sorted by account.

Tables: `movements` has these columns:
- `seq` integer primary key, the hidden order;
- `id` text not null unique, a code (four characters from `ID_ALPHABET`, checked in SQL with
  `length(id) = 4 AND id NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`);
- `account_id` text not null, referencing accounts;
- `date` text not null, with `date(date) IS date`;
- `payee` text not null and not blank;
- `amount` integer not null `<> 0`;
- `category_id` text, referencing categories;
- `transfer` text;
- `note` text;
- `created_at`, `updated_at` text not null; `deleted_at` text;
- check `(category_id IS NULL) = (transfer IS NOT NULL)`;
- index on `(account_id, date, seq)`.

`movement_tags` has `movement_id` (referencing movements) and `tag` (referencing tags), with
primary key `(movement_id, tag)`. The `transfer` column arrives now and is first written in Task 6.

stdin for `movement write [--dry-run]` is a strict object. `delete`, `movements` and
`transfers` all default to `[]`, and at least one must be non-empty, or the root issue is
`nothing to write: give delete, movements or transfers`. A movement is a strict object with
these fields:
- `account` and `category`: codes (strings);
- `date`;
- `payee`: required text;
- `amount`: `amountText`, not 0 (`must not be 0`);
- `currency`: text;
- `tags`: optional, `TAG_PATTERN`, no repeats (`is repeated`);
- `note`: optional string.

The output is `{ dryRun, ...WriteResult }`. Task 7 adds `delete` and Task 6 adds `transfers`:
until then their schemas take only `[]`.

- [ ] **Step 1: Write the failing tests**
  - `a movement is recorded in its account and its balance moves by its amount (USD)`.
  - `money in is positive and money out negative`.
  - `--dry-run shows each movement and the balance before and after, and writes nothing`.
  - `a payee and a category are required`.
  - `a zero amount is refused`: `"0"` and `"0.00"`.
  - `an amount is read back as written (USD)`: `"-30.39"` gives `amount: -30.39` and moves
    the balance by -30.39.
  - `a COP amount copied with its thousands dot is refused`: `"-15.000"` (Review Focus 5).
  - `an amount given as a JSON number is refused`: `-15000`.
  - `an impossible date such as 2026-02-30 is refused`.
  - `every item at fault is listed at once, and nothing is written`: an unknown category in
    `movements[0]` and another currency in `movements[2]` give `refused` with two `errors`, in
    that order. In the tests below, a rule's code is read from `errors[]`.
  - `a movement in another currency than its account's is refused`: `currency_mismatch`.
  - `an unknown account, category or tag is refused`: `not_found`.
  - `a movement dated before its account's opening date is refused`: `before_opening`.
  - `a movement dated on its account's opening date is accepted`.
  - `any category takes money in or money out`: +2000 COP into a spending category.
  - `a refusal anywhere in the write writes nothing`: the second of two movements is refused
    and the first is not stored.
  - `movements on the same day keep the order they were recorded in`.
  - `empty stdin is invalid_json` (Review Focus 4).
  - `a field the schema does not know is refused`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement** in this order: the schema and migration, stdin, `writeMovements`,
  `movementWriteCommand`, and the balance sum in `listAccounts`.
- [ ] **Step 4: `pnpm check` green.** Add `invalid_json` and `refused`, both 1, to "Codes so far",
  with `not_found`, `currency_mismatch` and `before_opening` as the codes inside `refused`.
- [ ] **Step 5: Commit**: `feat(cli): record movements`.

---

### Task 5: `movement list`

**Files:**

- Create: `src/shell/cli/commands/movement-list/{movement-list.ts,movement-list.schema.ts,movement-list.test.ts}`.
- Modify: `src/shell/db/movements/movements.ts`, `src/core/ledger/ledger.ts`.

**Interfaces:**

- Produces in `#core/ledger`: `matchesPayee(payee: string, text: string): boolean`. It
  compares the two strings after NFD normalisation, removing `\p{Diacritic}` and lowercasing.
- Produces: `type MovementFilter = { account?: string; from?: string; to?: string; payee?:
  string }`; `listMovements(store, filter): (MovementRow & { balance: number })[]`, newest first, by
  `(date, seq)` descending, without deleted rows. `balance` is the row's account's opening amount plus the running sum
  partitioned by account in `(date, seq)` order. It is computed over every movement in SQL
  before `from` and `to` filter the rows, and the payee filter runs afterwards in the shell
  with `matchesPayee`.

Flags: `--account <code>`, `--from <date>`, `--to <date>` (inclusive), `--payee <text>` and
`--limit <n>`, a whole number above 0 that defaults to `50` (`must be a whole number above 0`).
`listMovements` returns every match; the command keeps the first `limit` of them. Output:
`{ total, movements }`, `total` being the number of matches.

- [ ] **Step 1: Write the failing tests**
  - `movement list shows an account's movements with the balance after each (USD)`.
  - `the balance after a movement counts the movements before --from` (Review Focus 1).
  - `--from and --to keep the days in between, both included`.
  - `--payee finds Éxito from exito and Uber from UBER` (Review Focus 2).
  - `--payee across all accounts shows how a payee was categorised before`.
    - `a --from after --to gives no movements`.
    - `movements are listed newest first, and same-day ones by the reverse of their recorded
    order`.
  - `without --limit the 50 most recent matches are listed and total counts them all`: 52
    movements give `total: 52` and rows 52 down to 3.
  - `--limit 2 lists the 2 most recent matches`.
  - `a --limit that is not a whole number above 0 is refused`: `0` and `abc`, `invalid_input`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: `pnpm check` green.**
- [ ] **Step 5: Commit**: `feat(cli): list movements with their running balance`.

---

### Task 6: transfers

**Files:**

- Modify: `movement-write.schema.ts`, `src/shell/db/movements/movements.ts`,
  `src/core/ledger/{ledger.ts,ledger.errors.ts}`, the tests, and
  `docs/architecture.md`.

**Interfaces:**

- `checkWrite` also checks each half like a movement, without the category, `from` before
  `to`. It adds the problem `same_account_transfer`, message `a transfer needs two different accounts, not <account> twice`.
- A transfer in stdin is a strict object `{ from: Half, to: Half }`.
  - `from.amount` must be negative: `must be negative: the money leaves this account`.
  - `to.amount` must be positive: `must be positive: the money arrives in this account`.
  - Halves have no `category`.
- Both halves get the same `transfer` key, `crypto.randomUUID()`. Each half is listed with
  `transfer` = the other half's code.

- [ ] **Step 1: Write the failing tests**
  - `a transfer writes both halves, each in its own account`.
  - `a transfer across currencies carries both amounts and converts nothing`: `"-100"` USD and
    `"400000"` COP.
  - `each half keeps its own date, payee and note`: from on 2026-11-10, to on 2026-11-11.
  - `a transfer has no category`: `category` on a half is `is not a field`.
  - `a transfer between an account and itself is refused`: `same_account_transfer`.
  - `a refused half writes neither half`.
  - `tags can go on a transfer half`.
  - `an archived account cannot be either half`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: `pnpm check` green.** Add `same_account_transfer` to the codes inside `refused`.
- [ ] **Step 5: Commit**: `feat(cli): transfers between accounts`.

---

### Task 7: deletes and corrections

**Files:**

- Modify: `movement-write.schema.ts`, `src/shell/db/movements/movements.ts`,
  `src/core/ledger/ledger.ts`, and the tests.

**Interfaces:**

- `checkWrite` checks the deletes first: an id missing from `catalog.movements` is the problem
  `not_found`, `movement <id> does not exist`, item `delete[i]`.
- `delete` is an array of codes. They are deduplicated, and each is expanded to both
  halves of its transfer. A delete sets `deleted_at` and `updated_at` to `now` on
  both halves; rows and their tags stay stored. `deleted` lists each movement once, by
  `(date, seq)`.

- [ ] **Step 1: Write the failing tests**
  - `a deleted movement leaves every list and its balance returns (USD)`.
  - `a movement already deleted is not_found`.
  - `deleting one half of a transfer deletes both`.
  - `naming a movement twice, or both halves, deletes each once` (Review Focus 3).
  - `a correction is a delete and a new record in one write`: the balances show both changes,
    and the new movement gets a fresh code.
  - `an unknown movement code is refused and nothing is deleted`: `not_found` in
    `errors[]`.
  - `--dry-run of a delete writes nothing`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: `pnpm check` green.**
- [ ] **Step 5: Commit**: `feat(cli): delete and correct movements`.

---

### Task 8: importing the legacy export

**Files:**

- Create: `src/core/legacy/*`, `src/shell/legacy/export/*`, `src/shell/legacy/index.ts`,
  `src/shell/db/legacy-import/{legacy-import.ts,legacy-import.errors.ts}`,
  `src/shell/cli/commands/import/{import.ts,import.test.ts}`,
  `tests/support/legacy-export/{legacy-export.ts,legacy-export.constants.ts,legacy-export.types.ts}`.
- Modify: `src/shell/db/index.ts`, `main.ts`, `main.test.ts`, `docs/architecture.md`,
  `src/core/ledger/ledger.ts`.

**Interfaces:**

- `checkWrite` adds the problem `archived`, `<kind> <id> is archived`, for an archived account
  or category. It arrives here because only the import brings archived ones.

- Produces in `#core/legacy`:
  - `type LegacyExport = { exportedAt: string; balances: Map<number, number>; accounts:
    LegacyAccount[]; categories: LegacyCategory[]; tags: LegacyTag[]; transactions:
    LegacyTransaction[]; tagLinks: LegacyTagLink[] }`, with values already parsed to numbers,
    booleans and null.
  - `type StoredMovement = { id: string; account: string; date: string; payee: string; amount:
    number; category: string | null; transfer: string | null; note: string | null }`, with
    `transfer` as the legacy group text.
  - `type Ledger = { accounts: Account[]; categories: Category[]; tags: string[]; movements:
    StoredMovement[]; tagLinks: { movement: number; tag: string }[] }`.
  - `ledgerFrom(legacy: LegacyExport, randomIndex: RandomIndex): Ledger` keeps only `posted`
    rows, in legacy id order. An `expense` becomes
    `-amount` and an `income` `+amount`; a transfer's `out` half becomes `-amount` and its
    `in_` half `+amount`. An account whose balance minus the sum of its movements is not 0
    gets that difference as `openingAmount`, dated the day before its first posted movement
    (`Temporal.PlainDate`), or on the day of `exportedAt` when it has none. Every account, category and movement gets a fresh code, distinct within its list, and each
    movement's account, category, tags and transfer partner follow the codes. A name splits
    with `/^(\p{RGI_Emoji}) (.+)$/v` into `emoji` and `name`; a name it does not match keeps
    `emoji: null`. Types, archived marks, payees and notes are copied as stored, an
    empty-string note included.
- Produces in `#shell/legacy`: `readLegacyExport(folder: string): Promise<LegacyExport>`.
  - It checks each manifest table's `rows` and `sha256`, then parses each `.jsonl` line with
    zod, and only then returns.
  - Any failure throws `ExportMismatchError(file, reason)`: a `FailedError` (exit 2), code
    `export_mismatch`, message `<file>: <reason>`.
  - The reasons are `sha256 differs from manifest.json`,
    `has <n> rows, manifest.json says <m>` and `line <l>: <issue>`.
- Produces in `#shell/db`: `importLedger(store, ledger: Ledger, expected: Map<string, number>): ImportCounts`, with
  `expected` keyed by the new account codes.
  - It refuses a store with any account: `AlreadyImportedError`, `already_imported` (exit 1),
    message `the legacy export is imported only into an empty store`.
  - It inserts in legacy id order, so `seq` keeps the legacy order within a day, and writes
    directly rather than through `checkWrite`, since archived accounts hold history.
  - Movements keep their legacy `created_at`, which the legacy code wrote as UTC
    (`datetime.now(UTC)`), stored as an ISO instant with milliseconds. Accounts, categories
    and tags get the import's `now`, and `updated_at` equals `created_at`.
  - Afterwards it checks every balance against `expected`: `BalanceMismatchError`,
    `balance_mismatch` (exit 2), data `{ account, expected, actual }`.
  - `type ImportCounts = { accounts; categories; tags; movements; tagLinks }`.
- Command: `quaestor import <folder> [--dry-run]`. Output: `{ dryRun, imported: ImportCounts,
  openings: { account, name, amount, currency, date }[] }`, `name` being the account's
  name, so the openings can be checked against the spec without a second read.

The fixture is invented and has the shapes the real export has:
- an archived account holding posted movements;
- two categories sharing a name, one of them archived, and a category name with no emoji;
- a negative expense in a transfer category;
- a cross-currency transfer pair;
- a `skipped` row and a `planned` row;
- an empty-string note;
- one account whose balance differs from its movements, and one that matches.

Values are strings and nulls, as in `row_to_json`, and `manifest.json` carries the `sha256`
and `rows` of each file and each account's `balance`.

- [ ] **Step 1: Write the failing tests**
  - `import brings the export over and every balance equals the export to the cent (USD and
    COP)`.
  - `an account whose balance differs from its movements gets an opening balance the day before
    its first movement`.
  - `posted movements in an archived account are imported`.
  - `a negative expense becomes money in`.
  - `skipped and planned rows stay in the export`.
  - `every legacy account, category and movement gets a code, and each movement keeps its
    account, category, tags and transfer partner`.
  - `a legacy name splits into its emoji and its name, and a name without one keeps none`.
  - `movements of the same day keep their legacy order`.
  - `import --dry-run writes nothing`.
  - `import refuses a store that already holds data` (exit 1).
  - `a file whose sha256 differs from manifest.json stops the import` (exit 2, store
    unchanged).
  - `a row count that differs from manifest.json stops the import` (exit 2).
    - `an archived account receives no new movement`: after importing the fixture,
    `movement write` into its archived account gives `archived` in `errors[]`.
  - `an archived category receives no new movement`.
  - `an account without an opening date accepts a movement on any date`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: `pnpm check` green.** Add `already_imported`, 1 and `export_mismatch`,
  `balance_mismatch`, 2 to "Codes so far", and `archived` to the codes inside `refused`. In "Legacy data", the difference between a stored
  balance and its movements becomes the account's opening balance.
- [ ] **Step 5: Commit**: `feat(cli): import the legacy export`.
- [ ] **Step 6: Run it on a copy of the real data.** Claude runs this, read-only on the export:

```bash
SCRATCH=<scratchpad>
QUAESTOR_DB=$SCRATCH/copy.sqlite pnpm -s quaestor import ~/.quaestor/legacy --dry-run
QUAESTOR_DB=$SCRATCH/copy.sqlite pnpm -s quaestor import ~/.quaestor/legacy
QUAESTOR_DB=$SCRATCH/copy.sqlite pnpm -s quaestor account list --json > $SCRATCH/accounts.json
```

Then compare each account's `balance`, times 100 and rounded, with the cents in
`~/.quaestor/legacy/manifest.json`, with a script, not by eye, matching each account by `<emoji> <name>` against the manifest's name. Expected: every account equal, and the openings Angelo approved, which Claude keeps outside the repo. Report the
result to Angelo.

---

### Task 9: the `record-movements` skill

**Files:**

- Create: `.claude/skills/record-movements/SKILL.md`, `tests/skills/record-movements.test.ts`.
- Modify: `docs/architecture.md`. Under Skills, `record-movements` lives in `.claude/skills/`
  and calls the installed `quaestor`; that replaces "Until then, nothing records movements".

**Interfaces:**

- Consumes: every command above, through the installed `quaestor`.

`SKILL.md` holds:
- A frontmatter description that triggers on screenshots and on "anotar", "registrar
  movimientos" or "poner al día la cuenta".
- The session from the spec, step by step, with the command for each step.
- The amount format: as the bank shows it, a dot before the decimals and no thousands
  separator: COP $45.000,50 → `"45000.50"`, USD $10,85 → `"10.85"`, KRW ₩15.000 → `"15000"`.
- Before asking for the yes, a comparison of each `balances[].after` with the bank's balance
  (Review Focus 5).
- The rules:
  - one question per message;
  - only a bank statement creates a movement;
  - a pending row is asked about;
  - a difference is investigated and never adjusted;
  - a correction is a delete and a record in one write;
  - `quaestor`, never `pnpm quaestor`.

- [ ] **Step 1: Write the failing tests**
  - `every quaestor command the record-movements skill names exists`: extract each
    `quaestor <group> <command>`, `quaestor import` and `quaestor backup` from `SKILL.md`, and
    expect `runCli([...words, '--help'])` to exit 0.
  - `the skill never calls pnpm quaestor`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `SKILL.md`.**
- [ ] **Step 4: `pnpm check` green.**
- [ ] **Step 5: Commit**: `feat(skill): record-movements over the CLI`.

---

### Task 10: done in prod

- [ ] **Step 1:** `pnpm check` green on `recording-movements`. Hand Angelo the merge into
  `rebuild` and `pnpm release`; he runs both.
- [ ] **Step 2:** After the release, Claude runs `quaestor backup`, then
  `quaestor import ~/.quaestor/legacy --dry-run`, then `quaestor import ~/.quaestor/legacy`.
  Then `quaestor account list --json`, comparing it with `manifest.json` in cents as in
  Task 8.
- [ ] **Step 3:** The first real session. Angelo sends a bank screenshot, Claude follows the
  skill with a dry run first, and writes after his yes. That meets the spec's Done.
- [ ] **Step 4:** Cleanup, in one commit on a branch:
  - delete this plan;
  - remove item 1 from `docs/backlog.md`;
  - make `docs/features/recording-movements.md` describe what was built: commands and codes,
    with its decisions kept.

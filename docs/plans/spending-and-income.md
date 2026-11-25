# Spending and income Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude answers Angelo's questions on what he spent and earned, with exact figures in
COP at one configured rate, by group and category.

**Architecture:** Groups and rates are new store tables; every category points to a group in
the store itself. `quaestor report` reads the counted movements from the store and a pure
function in `src/core/report/` adds them up. A new skill holds Claude's judgment.

**Tech Stack:** Node 26, TypeScript, `node:sqlite` + Drizzle 1.0.0-rc.5, commander, zod,
`@toon-format/toon`, vitest, fast-check. No new dependency.

**Spec:** `docs/features/spending-and-income.md`, approved on 2026-11-25. It builds on
`docs/features/recording-movements.md`, `docs/architecture.md` and `docs/workflow.md`. Read
all four first.

## Global Constraints

- Every amount is integer cents in its account's currency; the CLI prints `cents / 100` as a
  number (`amountOf`).
- A rate is integer hundredths of a peso per unit (`3912.45` → `391245`), at most two
  decimals, above 0; COP has none. The local currency is `COP`, a constant.
- A foreign movement converts on its own: `cents × rate / 100`, half a centavo away from zero,
  through one function. A figure beyond 2^53 cents throws instead of rounding.
- Spending lines are `-(sum)`; income and outside lines are `sum`. `left` = income − spending,
  in every column.
- Codes are four characters from `0123456789abcdefghjkmnpqrstvwxyz`. Lists print the code
  as `id`.
- Every write takes `--dry-run` and prints `dryRun` first. stderr is `env: test\n` on success
  under tests.
- Exit 1 refused, exit 2 failed. Each new error class extends `RefusedError` or `FailedError`
  in its module's `.errors.ts`, and each new code goes into `docs/architecture.md` in the
  same task.
- Tests run the real command through `ledgerCli()`. Setup goes through commands; the only
  exception is the upgrade seed in Task 4 (`docs/workflow.md`). Each test is named after the
  rule it covers. Money tests run in a currency other than COP where the figure has one.
- Property tests: `fc.assert(fc.asyncProperty(...))` in an `it`, fresh store per run,
  `numRuns: 50`, arbitraries built with `.map` and never with `Math.random`.
- No code comments. Conventional Commits in English. Commit after each green step on
  `spending-and-income`; never merge or push. Run `pnpm check` before each commit that ends
  a task.
- No real figure or name in the repo: every example is invented. The category names in the
  Task 4 mapping are approved product data.

## Review Focus

- An income category holding money out (a salary reversal) prints a negative income and
  breaks nothing. Pinned in Task 5.
- A period with no movement prints its four `totals` lines at 0, `rates: []` and empty
  `groups` and `categories`. Pinned in Task 5.
- A movement on `--from` and one on `--to` count; the day before and the day after do not.
  Pinned in Task 5.
- A corrected movement (deleted by `movement write`) never counts. Pinned in Task 5.
- A conversion beyond 2^53 cents throws instead of printing a rounded figure. Pinned in
  Task 7.

---

## File map

- `src/core/ledger/`: add `GROUP_KINDS`, `LOCAL_CURRENCY`, `RATE_PATTERN`; the types `Group`,
  `GroupDraft` and `GroupKind`, and `group` on `Category` and `CategoryDraft`; the errors
  `NotFoundError` and `GroupNotEmptyError`; the function `convertCents`.
- `src/core/report/` (new concept): `report.ts` (`reportOf`), `report.types.ts`,
  `report.errors.ts` (`MissingRateError`), `report.constants.ts`, `index.ts`.
- `src/shell/db/groups/` (new): `groups.schema.ts`, `groups.ts`.
- `src/shell/db/rates/` (new): `rates.schema.ts`, `rates.ts`.
- `src/shell/db/categories/`: a `group` column, `archiveCategory` and `setCategoryGroup`.
- `src/shell/db/movements/movements.ts`: `countedMovements`.
- `src/shell/cli/commands/`: `group-list`, `group-add`, `group-edit`, `group-delete`,
  `category-archive`, `category-edit`, `rate-set` and `report` (new); `import` removed.
- `src/shell/cli/main/`: register the commands; `COMMAND_GROUPS` gains `group` and `rate`;
  `CliCommand.argument` becomes `arguments` (Task 6).
- `migrations/`: `<ts>_groups`, `<ts>_category_groups`, `<ts>_rates`, all from
  `pnpm db:generate --name <name>`, edited as each task says.
- `tests/support/`: `books.ts` takes a group; `upgrades/` (new) holds the seed files; the
  `legacy-export` helpers and `legacyRows` go away.
- `.claude/skills/spending-and-income/SKILL.md` (new); `tests/skills/` covers both skills.

---

### Task 1: Claude lists the 14 groups

**Files:**
- Create: `src/shell/db/groups/groups.schema.ts`, `src/shell/db/groups/groups.ts`,
  `src/shell/cli/commands/group-list/group-list.ts`,
  `src/shell/cli/commands/group-list/group-list.test.ts`, `migrations/<ts>_groups/`
- Modify: `src/core/ledger/ledger.constants.ts`, `ledger.types.ts`, `index.ts`;
  `src/shell/db/index.ts`; `src/shell/cli/main/main.ts`, `main.constants.ts`,
  `main.test.ts`; `docs/architecture.md`

**Interfaces:**
- Produces:
  - `GROUP_KINDS = ['income', 'spending', 'outside'] as const`, whose order is the display
    order;
  - `type GroupKind`;
  - `type Group = { id: string; kind: GroupKind; emoji: string; name: string }`;
  - `listGroups(store: Store): Group[]`, live groups by kind in `GROUP_KINDS` order, then
    by name;
  - the table `groups`: `id`, `kind`, `emoji` (not null), `name`, `created_at`,
    `updated_at` and `deleted_at`, with checks like `categories` (code, name not blank,
    `kind IN (...)`) and a unique `name` where `deleted_at IS NULL`.

- [ ] **Step 1: Write the failing tests** in `group-list.test.ts`:
  - `'a new store has the 14 approved groups, by kind then name'`: `group list` exits 0 with
    stderr `env: test\n` and stdout exactly:

    ```
    groups[14]{id,kind,emoji,name}:
      m0z7,income,💰,Income
      y6v7,spending,🚗,Auto & Transport
      jpnq,spending,💡,Bills & Utilities
      d7gd,spending,🧠,Education
      ex09,spending,🎢,Entertainment
      3asb,spending,🧾,Financial
      1aae,spending,🍽️,Food & Dining
      zyt4,spending,🎁,Gifts
      cx75,spending,⚕️,Health & Wellness
      xwvq,spending,🏠,Housing
      q3rh,spending,🛍️,Shopping
      pjbv,spending,💻,Software & AI
      xgn8,spending,✈️,Travel
      7hdg,outside,🔄,Transfers & Investments
    ```

  - `'a bare group exits 1 as missing_command with its own commands'`:
    `missingCommand(['list'])`.
  - In `main.test.ts`, add `'group'` to the expected `commands` (in registration order).
- [ ] **Step 2: Run** `pnpm test src/shell/cli/commands/group-list`. Expected: FAIL with
  `unknown_command`.
- [ ] **Step 3: Implement.**
  - Add the schema and run `pnpm db:generate --name groups`.
  - Append to the generated `migration.sql`, after a `--> statement-breakpoint`, one
    `INSERT INTO groups` of the 14 rows above, with `created_at` and `updated_at` set to
    `strftime('%Y-%m-%dT%H:%M:%fZ', 'now')`. The codes are fixed: Task 4 maps names to them.
  - Add `listGroups`, the `group list` command (`group: 'group'`) and
    `COMMAND_GROUPS.group = 'groups of categories and their kind'`.
- [ ] **Step 4: Run** `pnpm test`. Expected: PASS. `released.test.ts` counts shipped
  migrations through `shippedMigrationNames()`, so it needs no edit.
- [ ] **Step 5: Docs.** In `architecture.md` > Migrations, add: "The migration that brings
  groups seeds the 14 approved groups with fixed codes, in every store."
- [ ] **Step 6: Commit** `feat(groups): every store starts with the 14 approved groups`.

### Task 2: Claude archives a category

**Files:**
- Create: `src/shell/cli/commands/category-archive/category-archive.ts`,
  `category-archive.schema.ts`, `category-archive.test.ts`
- Modify: `src/core/ledger/ledger.errors.ts`, `index.ts`;
  `src/shell/db/categories/categories.ts`; `src/shell/db/index.ts`;
  `src/shell/cli/main/main.ts`; `tests/support/refusals/refusals.ts`;
  `docs/architecture.md`

**Interfaces:**
- Produces:
  - `class NotFoundError extends RefusedError`, built as
    `new NotFoundError(kind: string, value: string)`, with code `not_found`, data
    `{ kind, value }` and message `` `${kind} ${value} does not exist` ``;
  - `archiveCategory(store: Store, id: string, now: Date): Category`, which throws
    `NotFoundError('category', id)` for a code that is missing or deleted and returns an
    archived category unchanged;
  - `notFound(kind: string, value: string): string` in `refusals.ts`, the stderr with its
    `env: test\n` line, as `alreadyExists` does it.

- [ ] **Step 1: Write the failing tests** (they set up categories through today's
  `category add`):
  - `'category archive marks a category archived and category list shows it'`: the stdout
    is exactly the following, where `<games>` is the code `category add` printed (Task 4
    adds `group` after `id`):

    ```
    dryRun: false
    category:
      id: <games>
      emoji: 🎮
      name: Games
      archived: true
    ```
  - `'an archived category takes no new movement'`: after the archive, `movement write`
    naming it is refused with `archived` (as `movement-write.test.ts` asserts).
  - `'archiving frees the name: a new active category may take it'`: archive Games, then
    `category add Games` exits 0, and `category list` shows both, by name and then by code.
  - `'--dry-run on category archive shows it archived and changes nothing'`.
  - `'category archive with an unknown code exits 1 as not_found'`: stdout `''`, stderr
    `notFound('category', 'zzzz')`, that is:

    ```
    env: test
    error:
      code: not_found
      kind: category
      value: zzzz
      message: category zzzz does not exist
    ```

  - `'archiving a category that still holds movements is allowed'`: exit 0.
- [ ] **Step 2: Run** the new file. Expected: FAIL with `unknown_command`.
- [ ] **Step 3: Implement** the error, `archiveCategory` and the command
  (`category archive <code>` with `--dry-run`).
- [ ] **Step 4: Run** `pnpm test`. Expected: PASS.
- [ ] **Step 5: Docs.** Add `not_found` (exit 1, with `kind` and `value`) to the codes in
  `architecture.md`.
- [ ] **Step 6: Commit** `feat(categories): archive a category`.

### Task 3: `import` is retired (exception: a removal)

No new behaviour beyond `quaestor import` now being `unknown_command`. It comes before
Task 4, which would break it.

**Files:**
- Delete: `src/shell/cli/commands/import/`, `src/shell/db/legacy-import/`,
  `src/shell/legacy/`, `src/core/legacy/`, `tests/support/legacy-export/`, and
  `legacyRows` with its constants in `tests/support/arbitraries/` (whatever knip then
  reports unused).
- Modify: `src/shell/cli/main/main.ts`, `main.test.ts`; `src/shell/db/index.ts`;
  `category-list.test.ts`; `tests/skills/record-movements.test.ts` (drop `import` from
  `COMMAND`); `.claude/skills/record-movements/SKILL.md` (drop the `quaestor import` sentence
  in "Not part of a session"); `docs/architecture.md`;
  `docs/features/recording-movements.md`

What happens to each test that uses `import`, labelled on 2026-11-25. Every test in
`import.test.ts` covers what `import` does, so it goes with the command, except these five
rules of `movement write`. They outlive `import`, but only `import` could set them up,
because no command archives an account or leaves it without an opening date. `prod` holds
such accounts. Also, `released.test.ts` does not use `import`.

| Test | Becomes |
| --- | --- |
| an archived account receives no new movement | core test of `checkWrite` through `#core/ledger` |
| an archived account cannot be either half | core test of `checkWrite` |
| an archived category receives no new movement (archived account, archived category and an unknown tag, in that order) | core test of `checkWrite`, same order |
| an account without an opening date accepts a movement on any date | core test of `checkWrite` |
| an archived account is refused as archived only, even before its opening date | core test of `checkWrite` |
| categories with the same name are listed by code (`category-list.test.ts`) | CLI test set up with `category add`, `category archive` and `category add` |

- [ ] **Step 1: Move the surviving rules.**
  - Write `src/core/ledger/ledger.test.ts` with the five tests above, under the same names.
    Each builds a `Catalog` by hand and asserts the `WriteProblem[]` that `checkWrite`
    returns. The assertions are those of the old tests: the same codes, items and messages.
  - Re-set up `'categories with the same name are listed by code'` through commands: add
    Gifts, `category archive` it, then add Gifts again with `descendingCodes()`. Its
    assertions stay as they are.
  - Run both. Expected: PASS.
- [ ] **Step 2: Write the failing test** in `main.test.ts`:
  `'import is no longer a command'`: `['import', '/tmp']` exits 1 with stdout `''` and
  stderr:

  ```
  error:
    code: unknown_command
    message: unknown command 'import'
  ```

  Also drop `'import'` from the expected `commands`.
- [ ] **Step 3: Delete** the files listed above, and remove the `importCommand`
  registration and the db exports.
- [ ] **Step 4: Run** `pnpm check`. Expected: green, with knip reporting nothing unused.
- [ ] **Step 5: Docs.**
  - `architecture.md`: drop `already_imported`, `export_mismatch` and `balance_mismatch`
    from the codes and the stderr list. In Legacy data, say the `import` command loaded the
    export once on 2026-11-24 and was retired on 2026-11-25, and that the export stays in
    `~/.quaestor/legacy/`.
  - `recording-movements.md`: in Commands, replace the `import` line with "retired on
    2026-11-25 (see `spending-and-income.md`)".
- [ ] **Step 6: Commit** `refactor(cli)!: retire import`.

### Task 4: Every category has a group

**Files:**
- Create: `migrations/<ts>_category_groups/`, `tests/support/upgrades/upgrades.ts`,
  `tests/support/upgrades/category-groups.sql`,
  `tests/support/upgrades/unknown-category.sql`,
  `src/shell/db/migrations/category-groups.test.ts`
- Modify:
  - `src/shell/db/categories/categories.schema.ts` and `categories.ts`;
  - `src/core/ledger/ledger.types.ts`;
  - `category-add.schema.ts`, `category-add.ts`, `category-add.test.ts`;
  - `category-list.test.ts`, `movement-list.test.ts`, `movement-write.test.ts`;
  - `tests/support/books/books.ts`;
  - `.claude/skills/record-movements/SKILL.md` (the `category add` example gets
    `--group 1aae`, after `group list`);
  - `docs/architecture.md`, `docs/features/recording-movements.md`

**Interfaces:**
- Consumes: the fixed group codes (Task 1), `NotFoundError` (Task 2).
- Produces:
  - `Category = { id; group: string; emoji; name; archived }`;
  - `CategoryDraft = { emoji; name; group }`;
  - `insertCategory`, which throws `NotFoundError('group', id)` for a missing or deleted
    group;
  - `groupId(cli: LedgerCli, name: string): Promise<string>`, which reads `group list`;
  - `addCategory(cli, name = 'Food', group = 'Food & Dining')`;
  - `upgradeCli(seedFile: string, underTest: string): { before(argv: string[]): Promise<CliRun>; after(argv: string[]): Promise<CliRun> }`.
    Both calls use one temporary data folder. `before` runs with a migrations folder that
    holds the shipped migrations before `underTest`, plus the seed as a migration named to
    sort after them and before `underTest`. `after` runs with that same folder plus
    `underTest`. A test
    calls `before` first, so the seed is committed before the upgrade runs. Neither call
    warms up the store.

The migration. Run `pnpm db:generate --name category_groups` after adding
`group: text('group_id').notNull().references(() => groups.id)`. Then replace drizzle-kit's
`PRAGMA foreign_keys=OFF` rebuild, which is a no-op inside the migrator's single transaction
and fails with `FOREIGN KEY constraint failed` once movements point at categories (spiked
on 2026-11-25). The replacement, one statement per breakpoint:

```sql
PRAGMA defer_foreign_keys = ON;
CREATE TEMP TABLE `old_categories` AS SELECT * FROM `categories`;
DROP TABLE `categories`;
CREATE TABLE `categories` (...exactly as drizzle-kit generated `__new_categories`...);
INSERT INTO `categories` (`id`, `emoji`, `name`, `archived`, `created_at`, `updated_at`, `deleted_at`, `group_id`)
  SELECT `id`, `emoji`, `name`, `archived`, `created_at`, `updated_at`, `deleted_at`, CASE `name` ... END FROM `old_categories`;
DROP TABLE `old_categories`;
CREATE UNIQUE INDEX `categories_name_unique` ...;
```

The `CASE` maps exactly these names, and nothing else, so an unknown one is NULL and fails
`NOT NULL`:

| Group | Names |
| --- | --- |
| `xwvq` Housing | Rent, Home Maintenance, Laundry |
| `jpnq` Bills & Utilities | Utilities, Services, Internet, Phone |
| `1aae` Food & Dining | Restaurants, Groceries, Food Delivery, Coffee Shops, Food |
| `y6v7` Auto & Transport | Gas, Parking, Tolls, Car Wash, Car Maintenance, Auto Insurance, Rideshare/Taxi, Car Payment |
| `q3rh` Shopping | Clothing, Gadgets, Home Goods, Pets |
| `cx75` Health & Wellness | Healthcare, Fitness, Beauty & Wellness |
| `ex09` Entertainment | Entertainment, Streaming, Fun |
| `xgn8` Travel | Flights, Car Rental |
| `pjbv` Software & AI | AI Tools, Software |
| `d7gd` Education | Courses / Learning |
| `zyt4` Gifts | Gifts |
| `3asb` Financial | Taxes, Accountant, Bank Fees, Refund, Reimbursable |
| `m0z7` Income | Salary, Bonuses, Interest, Cashback |
| `7hdg` Transfers & Investments | Payment / Transfer, Investment, Investment Gains |

- [ ] **Step 1: Write the seed files.** They are invented rows in plain SQL, matching the
  schema just before `category_groups`.
  - `category-groups.sql`: one COP account, one category per name in the table (48 rows)
    plus an archived `Auto Insurance`, and two movements on two of those categories.
  - `unknown-category.sql`: the same, plus a category named `Mystery`.
- [ ] **Step 2: Write the failing tests** in `category-groups.test.ts`. Each starts with
  `const cli = upgradeCli(seed, '<ts>_category_groups')` and runs
  `await cli.before(['movement', 'list'])` first, which commits the seed under the old
  schema. `movement list` reads no category column.
  - `'the upgrade puts every existing category in its approved group, archived ones by their
    name'`: `cli.after(['category', 'list'])` exits 0, and each seeded code has the group
    the table gives it.
  - `'the upgrade keeps every movement on its category'`: `cli.after(['movement', 'list'])`
    prints the same stdout as `before` did.
  - `'a category the list does not name stops the upgrade and leaves the store as it was'`,
    with `unknown-category.sql`:
    - `cli.after(['category', 'list'])` exits 2 with stdout `''`;
    - its stderr is `env: test\n` followed by the `migration_failed` error, naming the
      migration and the reason `NOT NULL constraint failed: categories.group_id`;
    - `cli.before(['movement', 'list'])` then prints the same stdout as before the
      attempt;
    - a second `after` call fails the same way.
- [ ] **Step 3: Write the failing tests** in `category-add.test.ts` (the existing ones gain
  `--group`, and `GAMES` gains `group`):
  - `'a category is created with its group, and category list shows it'`: the stdout of
    `category add Gifts --emoji 🎁 --group zyt4` is exactly:

    ```
    dryRun: false
    category:
      id: n8d3
      group: zyt4
      emoji: 🎁
      name: Gifts
      archived: false
    ```

    (here `n8d3` is the drawn code), and `category list` prints
    `categories[1]{id,group,emoji,name,archived}:` / `  n8d3,zyt4,🎁,Gifts,false`.
  - `'the group is required'`: stderr `invalidInput('group: is required')`.
  - `'a group that does not exist is refused as not_found'`: stderr
    `notFound('group', 'zzzz')`.
- [ ] **Step 4: Run** both files. Expected: FAIL.
- [ ] **Step 5: Implement.**
  - Write the migration as above.
  - Add `group` to `categoryAddSchema` (`requiredText`), the `--group <code>` option (`'its
    group, from group list'`) and to `insertCategory`/`listCategories`. Check that the group
    is live before inserting.
  - Change `addCategory` in `books.ts` to look up its group with `groupId`. Every existing
    `category add` call gains `--group`.
- [ ] **Step 6: Run** `pnpm check`. Expected: green.
- [ ] **Step 7: Docs.**
  - `architecture.md` > Migrations: "A table that other tables reference is rebuilt with
    `PRAGMA defer_foreign_keys = ON`, copied through a temporary table and created again
    under its own name; drizzle-kit's `PRAGMA foreign_keys=OFF` rebuild is a no-op inside
    the migrator's transaction and fails once rows point at the table (checked on
    2026-11-25)."
  - `recording-movements.md` > Commands: `category add <name> --emoji <emoji> --group
    <code>`.
- [ ] **Step 8: Commit** `feat(categories): every category belongs to a group`.

### Task 5: Claude asks for a period's spending and income in COP

**Files:**
- Create: `src/core/report/` (`report.ts`, `report.types.ts`, `report.errors.ts`,
  `report.constants.ts`, `index.ts`), `src/shell/cli/commands/report/report.ts`,
  `report.schema.ts`, `report.test.ts`, `tests/support/reports/reports.ts`
- Modify: `src/shell/db/movements/movements.ts`, `movements.types.ts`;
  `src/shell/db/index.ts`; `src/shell/cli/main/main.ts`, `main.test.ts`;
  `docs/architecture.md`

**Interfaces:**
- Consumes: `listGroups`, `listCategories` (with `group`).
- Produces:
  - `type CountedMovement = { date: string; cents: number; currency: string; category: string }`;
  - `countedMovements(store: Store, filter: { from: string; to: string }): CountedMovement[]`,
    the live movements with a category, `from <= date <= to`;
  - `type ReportRequest = { from: string; to: string; byMonth: boolean }`;
  - `reportOf(request: ReportRequest, movements: CountedMovement[], catalog: { groups: Group[]; categories: Category[] }, rates: Map<string, number>): Report`,
    which throws `MissingRateError(currencies: string[])` (code `missing_rate`, data
    `{ currencies }` sorted, message `` `no rate for ${currencies.join(', ')}; set one with quaestor rate set` ``)
    for every non-COP currency missing from `rates`;
  - `Report` is the object printed below, its amounts already passed through `amountOf`.
  - In this task the command passes `new Map()` as `rates`.

- [ ] **Step 1: Write the failing tests** in `report.test.ts`. They set up through
  commands: a COP account, Salary in `m0z7`, Restaurants in `1aae`, Investment in `7hdg`,
  and `movement write`.
  - `'a month gives income, spending, what is left and the outside line, by group and
    category'`: with +5,000,000 Salary and -300,000 then +50,000 Restaurants in October,
    `report --from 2026-10-01 --to 2026-10-31` exits 0 with stderr `env: test\n` and stdout
    exactly:

    ```
    from: 2026-10-01
    to: 2026-10-31
    currency: COP
    rates: []
    totals[4]{line,total}:
      income,5000000
      spending,250000
      left,4750000
      outside,0
    groups[2]{id,kind,emoji,name,total}:
      m0z7,income,💰,Income,5000000
      1aae,spending,🍽️,Food & Dining,250000
    categories[2]{id,group,emoji,name,total}:
      <salary>,m0z7,💼,Salary,5000000
      <restaurants>,1aae,🍽️,Restaurants,250000
    ```

    `<salary>` and `<restaurants>` stand for the codes `category add` printed.

  - `'a refund in a later month lowers that month: +200,000 in October, -200,000 in November'`
    (Clothing in `q3rh`).
  - `'a transfer is never spending or income'`: a COP→COP transfer leaves stdout identical.
  - `'an opening balance is never spending or income'`: an account opened with 1,000,000
    adds nothing.
  - `'a change in an investment's value is outside the totals, with its sign'`: -4,000,000 in
    Investment gives `outside,-4000000` and spending unchanged.
  - The Review Focus tests:
    - `'an income category with money out prints a negative income'`;
    - `'a period with no movement prints four totals at 0 and nothing else'`;
    - `'both days of the period count, and the days around them do not'`;
    - `'a deleted movement never counts'`.
  - `'groups come by kind then name, and categories by group then name'`.
  - `'--to before --from is invalid_input'`: stderr `invalidInput('to: must not be before
    from')`, with no `env:` line.
  - `'--from and --to are required'`.
  - `'a period with a foreign currency and no rate is refused as missing_rate'`: with a USD
    and a KRW movement, exit 1, stdout `''`, stderr:

    ```
    env: test
    error:
      code: missing_rate
      currencies[2]: KRW,USD
      message: "no rate for KRW, USD; set one with quaestor rate set"
    ```

  - The property test, `'categories add up to their group and groups to their line, for any
    movements'`. It covers fresh categories in each kind, then 1 to 20 COP movements that
    `.map` over category index, cents (−10^9..10^9, not 0) and day (1..28 October). The
    oracle:
    - each category total is its signed sum;
    - each group is the sum of its categories;
    - each line is the sum of its groups;
    - left is income − spending;
    - adding 1 to 3 transfers changes no byte of stdout.
- [ ] **Step 2: Run.** Expected: FAIL with `unknown_command`.
- [ ] **Step 3: Implement.**
  - `countedMovements` is a select like `listMovements`, without the window sums.
  - `reportOf` groups the movements by category, signs each line by its group's kind and
    orders as specified.
  - The command is `report` (no command group). Its options are `--from <day>` and
    `--to <day>`, both required, validated by `report.schema.ts` with `dateText` and a
    refine on `to >= from`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Docs.** Add `missing_rate` (exit 1, with `currencies`) to `architecture.md`.
- [ ] **Step 6: Commit** `feat(report): spending and income of a period in COP`.

### Task 6: Claude sets the dollar rate

**Files:**
- Create: `src/shell/db/rates/rates.schema.ts`, `rates.ts`, `migrations/<ts>_rates/`,
  `src/shell/cli/commands/rate-set/rate-set.ts`, `rate-set.schema.ts`,
  `rate-set.test.ts`
- Modify: `src/core/ledger/ledger.constants.ts`; `src/shell/cli/invocation/input/`
  (`input.schema.ts`, `input.constants.ts`); `src/shell/cli/main/main.types.ts`,
  `main.ts`, `main.constants.ts`, `main.test.ts`; every command that uses `argument`
  (`account-add`, `category-add`, `category-archive`, `tag-add`)

**Interfaces:**
- Produces:
  - `LOCAL_CURRENCY = 'COP'`;
  - `RATE_PATTERN = /^\d+(\.\d{1,2})?$/`;
  - `rateText`, a zod string that becomes hundredths through `centsOf` and must be above 0
    and a safe integer, with the message `` 'must be a rate like "3912.45": above 0, no thousands separator, at most 2 decimals' ``;
  - `foreignCurrency`, which is `currencyCode` refined so that COP gives
    `'must not be COP, the local currency'`;
  - the table `rates`: `currency` (primary key, three capitals), `rate` (integer, above 0),
    `created_at` and `updated_at`;
  - `setRate(store: Store, currency: string, rate: number, now: Date): { currency: string; before: number | null; after: number }`,
    whose amounts go through `amountOf`;
  - `listRates(store: Store): Map<string, number>`, in hundredths;
  - `CliCommand.arguments?: { name: string; description: string }[]`, replacing
    `argument`.

- [ ] **Step 1: Write the failing tests:**
  - `'rate set stores a rate and shows it before and after'`: `rate set USD 3912.45` gives:

    ```
    dryRun: false
    rate:
      currency: USD
      before: null
      after: 3912.45
    ```

    Then `rate set USD 4000` gives `before: 3912.45` and `after: 4000`.
  - `'a rate works for any foreign currency (KRW)'`: `rate set KRW 2.85` gives `after: 2.85`.
  - `'--dry-run on rate set shows the change and stores nothing'`: a second dry run still
    says `before: null`.
  - `'a rate of 0, a negative one, three decimals or a thousands separator is refused'`
    (`it.for(['0', '-1', '3912.455', '3.912,45'])`): stderr `invalidInput('rate: must be a
    rate like "3912.45": above 0, no thousands separator, at most 2 decimals')`.
  - `'COP has no rate'`: `invalidInput('currency: must not be COP, the local currency')`.
  - `'a currency that is not ISO 4217 is refused'`: `invalidInput('currency: must be an ISO
    4217 code such as COP')`.
  - In `main.test.ts`: add `'rate'` to `commands`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Change `argument` to `arguments` and register each in order. The existing commands
    move to a one-item list.
  - Write the schema, then run `pnpm db:generate --name rates`.
  - Add `setRate` as an upsert, and the command `rate set <currency> <rate>` with
    `--dry-run`. Set `COMMAND_GROUPS.rate = 'rates from a foreign currency to COP'`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Docs.** In `architecture.md` > Money, replace "How the dollar rate is stored
  is decided by the currency feature…" with the decision: hundredths of a peso, at most two
  decimals, conversion per movement through `convertCents`.
- [ ] **Step 6: Commit** `feat(rates): set the rate of a foreign currency`.

### Task 7: The report converts foreign currencies at the rate

**Files:**
- Modify: `src/core/ledger/ledger.ts`, `index.ts`, `ledger.test.ts` (new, through
  `#core/ledger`); `src/core/report/report.ts`; `src/shell/cli/commands/report/report.ts`,
  `report.test.ts`

**Interfaces:**
- Produces: `convertCents(cents: number, rate: number): number`. It is exact, done in
  `BigInt`, rounds half a centavo away from zero, and throws `RangeError` when the result is
  not a safe integer.

- [ ] **Step 1: Write the failing tests:**
  - Core, through `#core/ledger`:
    - `convertCents(1085, 391245)` is `4245008`;
    - `convertCents(-1085, 391245)` is `-4245008`;
    - `convertCents(1, 400050)` is `4001`;
    - `convertCents(-1, 400050)` is `-4001`;
    - `convertCents(9007199254740991, 391245)` throws.
  - `'every total is in COP at the rate, with the part in each currency next to it (USD,
    KRW)'`: with a -10.85 USD and a -15,000 KRW Restaurants, `rate set USD 3912.45` and
    `rate set KRW 2.85`, the stdout is exactly:

    ```
    from: 2026-09-01
    to: 2026-09-30
    currency: COP
    rates[2]{currency,rate}:
      KRW,2.85
      USD,3912.45
    totals[4]{line,total,KRW,USD}:
      income,0,0,0
      spending,85200.08,15000,10.85
      left,-85200.08,-15000,-10.85
      outside,0,0,0
    groups[1]{id,kind,emoji,name,total,KRW,USD}:
      1aae,spending,🍽️,Food & Dining,85200.08,15000,10.85
    categories[1]{id,group,emoji,name,total,KRW,USD}:
      <restaurants>,1aae,🍽️,Restaurants,85200.08,15000,10.85
    ```

  - `'the spec example: 3,000 USD salary at 4,000 is 12,000,000 COP'`: this reproduces the
    approved example in `spending-and-income.md` (income, spending, left and outside, with
    their USD parts).
  - `'a purchase and its refund convert to exact opposites'`.
  - `'a currency with a rate needs none for the others in COP'`: `rates` lists only the
    counted currencies.
  - `'missing_rate names only the currencies without a rate'`: USD set, KRW not, gives
    `currencies[1]: KRW`.
  - The property test, `'with a whole rate, every figure is its COP part plus each foreign
    part times the rate'`. It covers COP and USD movements and a rate of `n × 100` hundredths
    (n in 1..5000), and checks every `total` against `COP part + USD × n`, line by line.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The command passes `listRates(store)`. `reportOf` converts each
  movement through `convertCents`, adds one column per foreign currency counted (sorted by
  code, in its own units with the line's sign) and lists those currencies in `rates`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Commit** `feat(report): convert foreign currencies at the configured rate`.

### Task 8: The report splits a period by month

**Files:**
- Modify: `src/core/report/report.ts`, `report.constants.ts`;
  `src/shell/cli/commands/report/report.ts`, `report.schema.ts`, `report.test.ts`

- [ ] **Step 1: Write the failing tests:**
  - `'--by-month gives every month its four totals, a month with no movement at 0'`: with a
    3,000 USD Salary in September, a -250,000 COP Restaurants in October and
    `rate set USD 4000`, `report --from 2026-09-01 --to 2026-10-31 --by-month` prints
    exactly:

    ```
    from: 2026-09-01
    to: 2026-10-31
    currency: COP
    rates[1]{currency,rate}:
      USD,4000
    totals[8]{month,line,total,USD}:
      2026-09,income,12000000,3000
      2026-09,spending,0,0
      2026-09,left,12000000,3000
      2026-09,outside,0,0
      2026-10,income,0,0
      2026-10,spending,250000,0
      2026-10,left,-250000,0
      2026-10,outside,0,0
    groups[2]{month,id,kind,emoji,name,total,USD}:
      2026-09,m0z7,income,💰,Income,12000000,3000
      2026-10,1aae,spending,🍽️,Food & Dining,250000,0
    categories[2]{month,id,group,emoji,name,total,USD}:
      2026-09,<salary>,m0z7,💼,Salary,12000000,3000
      2026-10,<restaurants>,1aae,🍽️,Restaurants,250000,0
    ```
  - `'months are cut to the period'`: from `2026-09-15` to `2026-10-10`, only `2026-09` and
    `2026-10`, and a movement on 2026-09-14 does not count.
  - `'groups and categories carry their month, only where they have movements'`.
  - The property test, `'the months add up to the period, for any movements'`. For each
    line, group and category, the sum over months of `--by-month` equals the figure without
    it.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Use `--by-month` (boolean). The month is `date.slice(0, 7)`, and
  months run from `from.slice(0, 7)` to `to.slice(0, 7)`. Each of the three tables gains
  `month` as its first field.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Commit** `feat(report): split a period by month`.

### Task 9: The report filters by tag and payee

**Files:**
- Modify: `src/shell/db/movements/movements.ts`; `src/shell/cli/commands/report/report.ts`,
  `report.schema.ts`, `report.test.ts`

**Interfaces:**
- Produces: `countedMovements(store, filter: { from; to; tag?: string; withoutTag?: string; payee?: string })`.
  The tags go through `EXISTS` on `movement_tags`. The payee goes through `matchesPayee`, in
  JS, as `listMovements` does.

- [ ] **Step 1: Write the failing tests** (in USD, with a rate set):
  - `'--tag keeps only the movements with that tag: how much the trip cost'`.
  - `'--without-tag leaves them out: September without the trip'`.
  - `'--payee keeps the payees containing the text, ignoring case and accents'` (`--payee
    uber` matches `UBER *TRIP`).
  - `'a tag that does not exist is refused as not_found'`: stderr
    `notFound('tag', 'trip:lima-2062')`, that is:

    ```
    env: test
    error:
      code: not_found
      kind: tag
      value: "trip:lima-2062"
      message: "tag trip:lima-2062 does not exist"
    ```

  - `'a movement the filters leave out needs no rate'`: a USD movement without the tag,
    with `--tag`, and no USD rate, exits 0.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The flags are `--tag <tag>` and `--without-tag <tag>` (both
  `tagText`) and `--payee <text>` (`requiredText`). Each tag must be in `listTags`, or the
  call throws `NotFoundError('tag', value)`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Commit** `feat(report): filter by tag and payee`.

### Task 10: Claude creates a group

**Files:** create `src/shell/cli/commands/group-add/` (`group-add.ts`,
`group-add.schema.ts`, `group-add.test.ts`); modify `src/shell/db/groups/groups.ts` and
`src/shell/cli/main/main.ts`.

**Interfaces:**
- Produces:
  - `type GroupDraft = { kind: GroupKind; emoji: string; name: string }`;
  - `insertGroup(store: Store, draft: GroupDraft, deps: WriteDeps): Group`, which throws
    `AlreadyExistsError('group', name)`.

- [ ] **Step 1: Write the failing tests:**
  - `'group add creates a group and group list shows it among the 14'`: the stdout of
    `group add Kids --emoji 👶 --kind spending` is:

    ```
    dryRun: false
    group:
      id: k4tr
      kind: spending
      emoji: 👶
      name: Kids
    ```

  - `'a new category can go into the new group'`.
  - `'--dry-run on group add writes nothing'`.
  - `'a name already taken is already_exists'`: `alreadyExists('group', 'Gifts')`.
  - `'the kind must be income, spending or outside'`: `invalidInput('kind: must be one of
    income, spending or outside')`.
  - `'the emoji is one emoji and required'`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The command is `group add <name>` with `--emoji`, `--kind`
  (`oneOf(GROUP_KINDS)`) and `--dry-run`, and the code comes from `withFreshCode`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Commit** `feat(groups): create a group`.

### Task 11: Claude renames a group or changes its emoji

**Files:** create `src/shell/cli/commands/group-edit/`; modify `groups.ts` and `main.ts`.

**Interfaces:**
- Produces: `updateGroup(store: Store, id: string, change: { name?: string; emoji?: string }, now: Date): Group`.
  It throws `NotFoundError('group', id)` and `AlreadyExistsError('group', name)`.

- [ ] **Step 1: Write the failing tests:**
  - `'group edit renames a group and changes its emoji'`: on Kids, `group edit k4tr --name
    Children --emoji 🧸` gives:

    ```
    dryRun: false
    group:
      id: k4tr
      kind: spending
      emoji: 🧸
      name: Children
    ```

  - `'the report shows the new name'`.
  - `'group edit with neither flag is invalid_input'`: `invalidInput('nothing to change:
    give --name, --emoji or both')`.
  - `'a name already taken is already_exists'`.
  - `'an unknown group is not_found'`.
  - `'--dry-run changes nothing'`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Commit** `feat(groups): rename a group or change its emoji`.

### Task 12: Claude moves a category to another group

**Files:** create `src/shell/cli/commands/category-edit/`; modify `categories.ts` and
`main.ts`.

**Interfaces:**
- Produces: `setCategoryGroup(store: Store, id: string, group: string, now: Date): Category`.
  It throws `NotFoundError('category', id)` and `NotFoundError('group', group)`.

- [ ] **Step 1: Write the failing tests:**
  - `'category edit moves a category to another group'`: `category edit <gifts> --group
    ex09` prints exactly:

    ```
    dryRun: false
    category:
      id: <gifts>
      group: ex09
      emoji: 🎁
      name: Gifts
      archived: false
    ```
  - `'its movements count in the new group, past periods included'`: a report of last month
    shows Gifts under `ex09`.
  - `'an unknown category or group is not_found'`.
  - `'the group is required'`.
  - `'--dry-run changes nothing'`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `category edit <code> --group <code>` with `--dry-run`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Commit** `feat(categories): move a category to another group`.

### Task 13: Claude deletes an empty group

**Files:** create `src/shell/cli/commands/group-delete/`; modify `ledger.errors.ts`,
`groups.ts`, `main.ts` and `docs/architecture.md`.

**Interfaces:**
- Produces:
  - `class GroupNotEmptyError extends RefusedError`, built as
    `new GroupNotEmptyError(group: string, categories: string[])`, with code
    `group_not_empty`, data `{ group, categories }` and message
    `` `group ${group} still holds ${n} ${n === 1 ? 'category' : 'categories'}` ``;
  - `deleteGroup(store: Store, id: string, now: Date): Group`. It soft-deletes, and its
    categories include archived ones.

- [ ] **Step 1: Write the failing tests:**
  - `'group delete deletes an empty group and group list no longer shows it'`: on Children
    (Task 11), `group delete k4tr` prints exactly the following, and `group list` is back
    to the 14:

    ```
    dryRun: false
    group:
      id: k4tr
      kind: spending
      emoji: 🧸
      name: Children
    ```
  - `'a group with a category is refused as group_not_empty'`: on `zyt4` holding Gifts,
    exit 1, stdout `''`, stderr:

    ```
    env: test
    error:
      code: group_not_empty
      group: zyt4
      categories[1]: <gifts>
      message: group zyt4 still holds 1 category
    ```

  - `'an archived category still holds its group'`.
  - `'moving the category out first lets the group go'` (`category edit`, then
    `group delete`).
  - `'a deleted group's name can be taken again'`.
  - `'a deleted group takes no new category'`: `category add --group <deleted>` is
    `not_found`.
  - `'an unknown group is not_found'`.
  - `'--dry-run deletes nothing'`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `group delete <code>` with `--dry-run`.
- [ ] **Step 4: Run** `pnpm check`. Expected: green.
- [ ] **Step 5: Docs.** Add `group_not_empty` (exit 1, with `group` and `categories`) to
  `architecture.md`.
- [ ] **Step 6: Commit** `feat(groups): delete an empty group`.

### Task 14: The `spending-and-income` skill

**Files:**
- Create: `.claude/skills/spending-and-income/SKILL.md`
- Modify: `tests/skills/record-movements.test.ts` → `tests/skills/skills.test.ts`, which
  runs both skills with `it.for`; its `COMMAND` becomes
  `/\bquaestor (?:(?:account|category|tag|movement|group|rate) [a-z]+|report|backup)\b/g`

- [ ] **Step 1: Write the failing test:** `'every quaestor command the spending-and-income
  skill names exists'` and `'the skill never calls pnpm quaestor'`, for both skills.
- [ ] **Step 2: Run.** Expected: FAIL, because the file is missing.
- [ ] **Step 3: Write the skill.** It is in English, with Spanish triggers such as "cuánto
  gasté", "cuánto gané", "compara este mes" or "cuánto me costó el viaje". It covers:
  - call the installed `quaestor` and check the `env: prod` line;
  - every figure comes from `report`, and Claude never adds two figures itself;
  - "this year" runs from 1 January to today;
  - a month in progress goes against the same days of the month before (two calls);
  - `--by-month` for a trend, `--tag` and `--without-tag` for a trip, `--payee` for one
    merchant;
  - read `total` as COP, and say the rate in every answer;
  - explain an odd month (a refund after its purchase) and the outside line;
  - on `missing_rate`, ask Angelo the rate, one question per message, run `rate set
    --dry-run`, and set it after his yes;
  - creating, editing or deleting a group, and moving or archiving a category, follow
    `record-movements`'s dry-run rule.
- [ ] **Step 4: Docs.** In `architecture.md` > Skills, add that `spending-and-income` lives
  in `.claude/skills/` and calls the installed `quaestor`.
- [ ] **Step 5: Run** `pnpm check`. Expected: green.
- [ ] **Step 6: Commit** `feat(skills): answer spending and income questions`.

---

## Getting the real data ready (non-code steps, in order)

1. **Before Task 4 is committed, with the installed release:** create Car Payment and move
   the misfiled rows (car loan payments, every Refund row, the Services rows that belong
   elsewhere). Each write is a dry run Angelo approves, under `record-movements`'s rules.
   It has to come first: from Task 4 on, the branch's `record-movements` skill passes
   `--group`, which the installed release rejects.
2. **The trial on a copy of `prod`, right after Task 4 and again just before the
   release:**
   - run `quaestor backup` and copy that backup into the scratchpad;
   - from the repo, run `QUAESTOR_DB=<copy> pnpm quaestor category list` and check every
     category's group against the Task 4 table;
   - the second time, also run `report` for a past month on the copy, at the rate Angelo
     gives, and check it in cents against `movement list`.
3. **From the last trial to the release, no category is created in `prod`.** A name the
   upgrade does not know makes every `prod` call exit 2 once the release is installed.
4. **Angelo** merges and runs `pnpm release`. The first `prod` call prints
   `backup: … (before migrating)` and three `migrated:` lines.
5. **With the new release:** `category archive` Refund and Reimbursable, and `rate set USD
   <rate>`, each a dry run and then a yes.
6. Claude answers Angelo's questions against `prod` with the skill and checks the figures in
   cents.
7. **Close:**
   - drop "how much he spent last month, and on what" from `backlog.md`;
   - set the status line of `docs/features/spending-and-income.md` to built;
   - delete this plan.

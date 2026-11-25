# Skeleton tests through the command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every skeleton test that calls an internal function, reads a table or writes SQL
is rewritten through the command, or deleted where Angelo said so, as backlog item 1 and
`docs/workflow.md` ask.

**Kind:** a pure refactor, named as the exception in `docs/workflow.md` ("a slice that
delivers no behaviour"). No command changes: Claude reads exactly the same stdout, stderr
and exit codes as today, so this plan shows no new client output.

**Architecture:** tests only. Each rule an internal test pins moves to a CLI test that runs
`main` through `runCli` (or the source bin through `spawnSync`) and asserts stdout, stderr,
the exit code and the files on disk. No file under `src/` changes except `*.test.ts`.

**Spec:** `docs/backlog.md` item 1 and the Tests section of `docs/workflow.md`.

## Scope

Files that call an internal function, read a table or write SQL today:

- `src/core/backups/backups.test.ts` (backup names), deleted in Task 2.
- `src/shell/db/backups/backups.test.ts` (store backups), deleted in Task 2.
- `src/shell/db/database/database.test.ts` (the connection), deleted in Task 3.
- `src/shell/db/migrations/migrations.test.ts` (migrations), deleted in Task 3.
- `src/shell/cli/invocation/env/env.test.ts` (env resolution), rewritten in Task 1.
- `src/shell/cli/invocation/context/context.test.ts` (the entry points' contexts), deleted
  in Task 4. The backlog does not name it, but it calls `sourceContext` and
  `releasedContext`.
- `src/shell/cli/commands/backup/backup.test.ts`, which already runs the command but sets
  up and checks with `openTestStore`, `closeStore`, `runSql` and `selectAll`. Fixed in
  Task 3.

`src/shell/release/release/release.test.ts`, `tests/lint/` and
`tests/support/temp-dir/temp-dir.test.ts` stay: they test code with no command of its own.

## Angelo's rulings (2026-11-25)

- The four `closes the handle when …` tests are deleted. Nothing a command prints, exits or
  leaves on disk shows whether the handle was closed. The code that closes it stays.
- `copiesToRemove reads the env as literal text` (`pr.d`) is deleted. No command accepts an
  env name with a dot.
- The installed entry's context tests are deleted: `--version` prints `<version> (<commit>)`,
  defaults to `prod` under `<home>/.quaestor`, finds migrations in
  `<entryDir>/../migrations`, its first run creates `~/.quaestor`, and it has no data
  folder under vitest. `pnpm release` still smoke-runs the packed `--help` and `--version`.
- By the same reasoning, the source entry's "data folder is `<repoRoot>/data`" half is
  deleted. It is visible only outside vitest, where it would write into the repo's real
  `data/`. The source bin already shows its default env, `test`, under vitest.

## Global constraints

- No code comments. Code, tests and commit messages are in English.
- Each test name says which rule it pins.
- Expected TOON is built with `encode` or pasted from a real run, never typed by hand.
- No test unsets `VITEST`. A spawned bin gets `QUAESTOR_DB` and `QUAESTOR_ENV` only when
  the test sets them.
- A test never weakens an assertion. Every assertion this plan changes is listed in its
  task.
- Every new CLI test replaces an internal one and passes on its first run. Before
  committing, break the rule it names with a one-line edit to the source, watch the test
  fail on that rule, and revert the edit.
- `pnpm check` is green at the end of every task. knip and jscpd count: a support helper
  left with no user is deleted in the same task.
- Commit after each task on branch `skeleton-tests`, never on `rebuild`, never push.

## Review focus

1. A replacement passes for the wrong reason, for example seeded copies that the rule
   would keep anyway. The red check in Global constraints catches it, so it must be done
   for every new test.
2. A spawned process reaches a real store. Bin tests strip `QUAESTOR_DB` and
   `QUAESTOR_ENV` unless the test sets them, and never unset `VITEST`.
3. A locked folder outlives a failing test. Every `chmod 0o500` registers the folder in
   `lockedFolder`, which `afterEach` restores.
4. A check run with `migrate` writes into the `dataDir` under test and breaks that test's
   folder listings. `migrate` always uses its own throwaway `dataDir`.
5. The writer-lock test depends on timing. The child holds the lock for 400 ms against a
   5000 ms busy timeout. Keep that ratio.

---

### Task 1: env resolution through `quaestor backup`

**Files:**
- Rewrite: `src/shell/cli/invocation/env/env.test.ts`

The file stops importing `resolveEnv` and the env types. Each case runs
`runCli(['backup', ...argv], { dataDir, ...overrides })` with `dataDir = tempDir('quaestor-cli-')`
and the default `noMigrations()`. On success, stderr is exactly the env line.

Ledger, from old test to its fate:

- Precedence, `--env` over both: already covered by `backup.test.ts` "with --env,
  QUAESTOR_DB and QUAESTOR_ENV all set, backup uses --env". Dropped.
- Precedence, QUAESTOR_DB over QUAESTOR_ENV: new test. `vars: { QUAESTOR_DB: <tmp>/x.sqlite, QUAESTOR_ENV: 'staging' }`
  exits 0 with stderr `env: custom (<tmp>/x.sqlite)\n`, and no `staging.sqlite` in `dataDir`.
- Precedence, QUAESTOR_ENV over the default: new test. `vars: { QUAESTOR_ENV: 'staging' }`
  exits 0 with stderr `env: staging\n`, and `dataDir/staging.sqlite` exists.
- Precedence, the default: covered by `backup.test.ts` "stderr is exactly env: test …".
  Dropped.
- `--env x maps to <dataDir>/x.sqlite`: covered by the `--env staging` test in
  `backup.test.ts`. Dropped.
- Naming rule: `Prod` from `--env` is covered by `backup.test.ts`. New `it.each` for
  `QUAESTOR_ENV: 'a b'` and `--env 1prod`: exit 1, empty stdout, stderr
  `encode({ error: { code: 'invalid_env', source, value, message: 'invalid <source> "<value>": start with a lowercase letter, then use lowercase letters, digits and dashes' } })`,
  and `dataDir` empty.
- `custom` is reserved: new `it.each` for `--env custom` and `QUAESTOR_ENV: 'custom'`:
  exit 1, `invalid_env`, message `invalid <source> "custom": custom is reserved for QUAESTOR_DB`,
  and `dataDir` empty.
- Relative QUAESTOR_DB: new test. `QUAESTOR_DB: 'rel/x.sqlite'` gives exit 1, `invalid_env`,
  `source: 'QUAESTOR_DB'`, and the message `invalid QUAESTOR_DB "rel/x.sqlite": must be an absolute path`.
- No data folder, named env: `default` is covered by `backup.test.ts`. New `it.each` with
  `dataDir: null` for `--env prod` and `QUAESTOR_ENV: 'x'`: exit 1, stderr
  `encode({ error: { code: 'named_env_disabled', source, env, message: 'named environments are disabled here (<source>: <env>); set QUAESTOR_DB to a temporary file' } })`.
- No data folder, QUAESTOR_DB still names a custom store: covered by `backup.test.ts`
  "QUAESTOR_DB with no data folder exits 1 as backups_disabled …", whose stderr starts
  `env: custom (<path>)`. Dropped.

- [ ] **Step 1:** Write the new cases. Run `pnpm vitest run src/shell/cli/invocation/env`
  and expect PASS.
- [ ] **Step 2:** Red check for each case, in `src/shell/cli/invocation/env/env.ts`: swap the
  `QUAESTOR_DB` and `QUAESTOR_ENV` branches, drop the format check, drop the `custom`
  check, drop the `isAbsolute` check, and drop the `dataDir === null` check. Each case must
  fail on its own rule. Revert every edit.
- [ ] **Step 3:** Run `pnpm check` and expect green. Commit
  `test(cli): env resolution through the command`.

### Task 2: backup copies through `quaestor backup`

**Files:**
- Modify: `src/shell/cli/commands/backup/backup.test.ts`
- Delete: `src/core/backups/backups.test.ts`, `src/shell/db/backups/backups.test.ts`

Seeded copies are files whose content is their own name, so the test can check they are
untouched. `FIXED_INSTANT` is `2026-11-23T21:04:05.123Z`, so `COPY_NAME` is
`test-2026-11-23T21-04-05-123Z.sqlite`.

Ledger:

- `backupFileName` names `<env>-<instant>.sqlite`: covered by every `COPY_NAME` assertion.
  Dropped.
- Keeps the newest 5: covered by "backup prints the copy it removed". Dropped.
- Another env whose name starts the same: new test "copies of an env whose name starts the
  same are not counted". Seed six `prod-2026-11-0{1..6}T10-00-00-000Z.sqlite`, then
  `backup --env pro` prints `removed: []`, and all six prod copies are intact.
- Another env that extends this one with a dash: new test "copies of an env whose name
  extends this one with a dash are not counted". Seed six `prod-eu-…` copies and four
  `prod-…` copies, then `backup --env prod` prints `removed: []`, and the folder holds
  the seeds plus the new copy.
- Literal env text (`pr.d`): deleted (ruling).
- Five copies or fewer: new test "four copies and a new one remove nothing". Seed four
  `test-…` copies, then `backup` prints `removed: []`, and the folder holds five copies.
- The protected copy, "nothing more", and the older clock (core tests 7–8, db test 5):
  one new test, "a clock older than the copies on disk keeps the copy it just wrote and
  removes only the oldest of the rest". Seed six copies dated
  `test-2026-12-0{1..6}T10-00-00-000Z.sqlite`, then `backup` prints `path` = `COPY_NAME`
  and `removed` = the 2026-12-01 copy only. The folder holds `COPY_NAME` plus
  2026-12-02..06, untouched.
- The newest copy protected: covered by "backup prints the copy it removed". Dropped.
- The copy opens with the same content: new test "the copy holds the same accounts as the
  store". With `migrationsDir: SHIPPED_MIGRATIONS` on every call: run `account add Wallet
  --emoji 💵 --type debit --currency USD --opening 120.50 --opening-date 2026-01-05`, then
  `backup`, then `account list`. Its stdout equals `account list` with
  `vars: { QUAESTOR_DB: <copy> }`, and contains `Wallet`.
- The sixth backup removes that env's oldest copy only: new test "a sixth backup removes
  that env's oldest copy and leaves other envs and other files untouched". Seed five
  `prod-2026-11-0{1..5}…`, two `test-2026-10-0{1,2}…` and `notes.txt`, then `backup --env prod`
  prints `removed` = the 2026-11-01 prod copy. Every other seed is intact.
- Same instant: covered by "a second backup at the same instant exits 2 …". Dropped.
- Partial copies: new test "a partial copy another process left or is still writing is
  neither used nor removed". Seed `${COPY_NAME}.partial` and `${COPY_NAME}.0.partial`, then
  `backup` exits 0. Both are intact, and the folder holds them plus `COPY_NAME`.
- A copy that cannot be moved into place: new test. A folder named `COPY_NAME` inside
  `backups/` makes `backup` exit 2 with `backup_not_written` and `folder` = `<dataDir>/backups`.
  Paste the real stderr. The listing is `[COPY_NAME]`, so no `.partial` is left.
- A backups folder that cannot be created: new test. Put the store at
  `QUAESTOR_DB=<other tmp>/x.sqlite` and `chmod 0o500` the `dataDir`, registered in
  `lockedFolder`. `backup` exits 2, stderr starts `env: custom (<path>)\n` and holds
  `backup_not_written` with `folder` = `<dataDir>/backups`, and `dataDir` is empty.

- [ ] **Step 1:** Write the new tests. Delete both old files. Run
  `pnpm vitest run src/shell/cli/commands/backup` and expect PASS.
- [ ] **Step 2:** Run each red check below, watch its tests fail, and revert the edit.
  - In `copyPattern`, replace `${ENV_SEPARATOR}${INSTANT_PATTERN}` with `.*`. Fails: the
    "starts the same", "extends with a dash" and "sixth backup" tests.
  - Set `COPIES_KEPT` to `4`. Fails: "four copies and a new one".
  - Drop the `protect` filter in `copiesToRemove`. Fails: "a clock older …".
  - Replace the `backup(…)` call in `writeCopy` with `new DatabaseSync(partial).close()`.
    Fails: "the copy holds the same accounts".
  - Name the partial `${path}${PARTIAL_SUFFIX}`, without the pid. Fails: "a partial copy …".
  - Drop the `finally` `rm(partial)`. Fails: "a copy that cannot be moved into place".
  - Move `mkdir` above the `try` in `writeCopy`. Fails: "a backups folder that cannot be
    created".
- [ ] **Step 3:** Run `pnpm check` and expect green. Commit
  `test(cli): backup copies through the command`.

### Task 3: migrations and the connection through the command

**Files:**
- Modify: `src/shell/cli/commands/backup/backup.test.ts`
- Delete: `src/shell/db/migrations/migrations.test.ts`, `src/shell/db/database/database.test.ts`,
  and `tests/support/store/`, which has no user left after this task.

**Produces:** in `backup.test.ts`, `migrate(path: string, migrationsDir: string): Promise<string[]>`.
It runs `backup` with `vars: { QUAESTOR_DB: path }`, its own `dataDir: tempDir('quaestor-migrate-')`
and the given migrations. It throws with the stderr if the exit is not 0, and returns the
names on the `migrated: ` lines of stderr, in order. It is the setup that replaces
`openTestStore`, and the check that replaces `fixtureTables`.

Assertions this task changes. Each one reads what the command sees instead of a table:

- "a second backup at the same instant …": `runSql(… create table notes)` becomes
  `account add` (Task 2's Wallet argv), with `migrationsDir: SHIPPED_MIGRATIONS` on all
  three calls. The asserted call's exit, stderr and listing are unchanged.
- "an unwritable backups folder …": `openTestStore` + `runSql` become `account add` with
  `SHIPPED_MIGRATIONS`, then the lock, then `backup` with `SHIPPED_MIGRATIONS`. The
  assertions are unchanged.
- "backup on a new store applies the migrations first": `fixtureTables(copy)` becomes
  `expect(await migrate(copy, fixtureMigrations())).toEqual([])`.
- "a prod store with pending migrations is backed up before they apply":
  `fixtureTables(beforeMigrating)` becomes `migrate(beforeMigrating, …)` and equals both
  fixture names, and `fixtureTables(own)` becomes `migrate(own, …)` and equals `[]`.
- "… unwritable backups folder … migrates nothing": `fixtureTables(prod.sqlite)` becomes
  `migrate(prod.sqlite, fixtureMigrations())`, which equals both fixture names.
- "a failing migration in prod …": `fixtureTables(prod.sqlite)` becomes
  `migrate(prod.sqlite, fixtureMigrations(FIXTURE_MIGRATIONS))`, which equals both fixture
  names. This also covers migrations test 2 ("a failing migration keeps none of the
  pending ones").
- "a store with migrations this code does not know …": the `openTestStore` setup becomes
  `migrate(prod.sqlite, fixtureMigrations())`. The assertions are unchanged.

Ledger for the deleted files:

- migrations 1, "a new store is created with every migration applied": covered by "backup
  on a new store applies the migrations first" (stderr plus `migrate(copy)`).
- migrations 2: covered above.
- migrations 3, "the shipped migrations folder opens a store": moves to Task 4.
- database 1–4, `closes the handle …`: deleted (ruling).
- database 5, the writer lock: new test "a store another process holds briefly is waited
  for, not refused as locked". `migrate(<dataDir>/test.sqlite, noMigrations())`, then
  `holdExclusiveLock` (moved from `database.test.ts` as is), then `backup` exits 0 and
  prints `COPY_NAME`. The child process writes `BEGIN EXCLUSIVE`. That is another process
  holding the file, not the test reading or writing the store, and it is the only SQL
  left in the suite.

- [ ] **Step 1:** Add `migrate`, change the assertions listed above, add the lock test,
  and delete the two files and `tests/support/store/`. Run
  `pnpm vitest run src/shell/cli/commands/backup` and expect PASS.
- [ ] **Step 2:** Red checks:
  - Set `BUSY_TIMEOUT_MS` to `0`. The lock test fails as `unexpected` `database is locked`.
    Revert.
  - For each `migrate(…)` assertion changed above, swap its expected value once (`[]` for
    both names, or both names for `[]`). It must fail. Revert.
- [ ] **Step 3:** `grep -rn "runSql\|selectAll\|openTestStore\|closeStore" src tests` returns
  nothing. Run `pnpm check` and expect green. Commit
  `test(cli): migrations and the connection through the command`.

### Task 4: the source entry through its bin

**Files:**
- Modify: `src/shell/cli/bin/bin.test.ts`
- Delete: `src/shell/cli/invocation/context/context.test.ts`

`runBin(args: string[], { input = '', vars = {} }: { input?: string; vars?: Record<string, string> } = {})`
keeps stripping `QUAESTOR_DB` and `QUAESTOR_ENV`, then applies `vars`. Existing callers
pass their stdin as `{ input }`.

Ledger:

- The source context prints `dev`: new test "the source bin prints dev for --version".
  Status 0, stdout `dev\n`, stderr empty.
- The source context refuses `prod`: new `it.each` for `['--env', 'prod', 'backup']` and
  `['backup']` with `vars: { QUAESTOR_ENV: 'prod' }`. Status 1, stdout empty, stderr
  `encode({ error: { code: 'invalid_env', source, value: 'prod', message: 'invalid <source> "prod": prod is reserved for the installed quaestor' } })`,
  and `<REPO_ROOT>/data/prod.sqlite` does not exist.
- The source context finds migrations in `<repoRoot>/migrations`, plus migrations test 3:
  new test "the source bin migrates a new store with every shipped migration".
  `vars: { QUAESTOR_DB: <tmp>/x.sqlite }` and `['account', 'list']` give status 0, stdout
  `accounts: []\n`, and stderr `env: custom (<path>)\n` followed by `migrated: <name>\n`
  for every folder under `SHIPPED_MIGRATIONS` that holds `MIGRATION_FILE`, sorted.
- The source default is `test` under vitest: covered by "the source bin under vitest
  refuses its default env" and the leak test (`source: 'default', env: 'test'`). The data
  folder half is deleted (ruling).
- Every installed-entry case is deleted (ruling).

- [ ] **Step 1:** Write the new tests and delete `context.test.ts`. Run
  `pnpm vitest run src/shell/cli/bin` and expect PASS.
- [ ] **Step 2:** Red checks, each reverted after it fails: change `DEV_VERSION` in
  `context.constants.ts` (fails the `--version` test), change `MIGRATIONS_FOLDER` there
  (fails the shipped-migrations test), and empty the source's `releaseOnlyEnvs` in
  `context.ts` (fails both `prod` cases as `named_env_disabled`).
- [ ] **Step 3:** Run `pnpm check` and expect green. Commit
  `test(cli): the source entry through its bin`.

### Closing

- [ ] Delete item 1 from `docs/backlog.md` and renumber the rest. Delete this plan.
  Commit `docs: close skeleton tests through the command`. Angelo merges.

# Skeleton tests through the command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the skeleton's tests follow the test rules in `docs/workflow.md`, as Angelo
revised them on 2026-11-25, which is what backlog item 1 asks.

**Kind:** a pure refactor, named as the exception in `docs/workflow.md` ("a slice that
delivers no behaviour"). No command changes: Claude reads exactly the same stdout, stderr
and exit codes as today, so this plan shows no new client output.

**Architecture:** the three layers in `docs/workflow.md`:
- Shell rules move to tests that run `main` through `runCli`, or the source bin through
  `spawnSync`, and assert stdout, stderr, the exit code and the files on disk.
- The pure core test stays and reaches its logic through the `#core/backups` barrel.
- The installed entry gets end-to-end tests that build the release and run it.

The only production change is an output folder for `buildRelease`.

**Spec:** `docs/backlog.md` item 1 and the Tests section of `docs/workflow.md`.

## Scope

- `src/core/backups/backups.test.ts` (backup names): kept, and imports through
  `#core/backups` (Task 2).
- `src/shell/db/backups/backups.test.ts` (store backups): deleted in Task 2.
- `src/shell/db/database/database.test.ts` (the connection): deleted in Task 3.
- `src/shell/db/migrations/migrations.test.ts` (migrations): deleted in Task 3.
- `src/shell/cli/invocation/env/env.test.ts` (env resolution): rewritten in Task 1.
- `src/shell/cli/invocation/context/context.test.ts` (the entry points' contexts):
  deleted in Task 4. Its installed-entry cases move to Task 5. The backlog does not name
  this file, but it calls `sourceContext` and `releasedContext`.
- `src/shell/cli/commands/backup/backup.test.ts`, which already runs the command but sets
  up and checks with `openTestStore`, `closeStore`, `runSql` and `selectAll`: fixed in
  Task 3.

`src/shell/release/release/release.test.ts`, `tests/lint/` and
`tests/support/temp-dir/temp-dir.test.ts` stay: they test code with no command of its own.

## Angelo's rulings (2026-11-25)

- These test rules are already written into `docs/workflow.md`:
  - a test checks the resulting state, never which internal calls were made;
  - pure logic in `src/core/` may be tested through its barrel;
  - a few end-to-end tests run the built release.
- The four `closes the handle when …` tests are deleted. They spy on an internal call,
  and nothing a command prints, exits or leaves on disk shows whether the handle was
  closed. The code that closes it stays.
- The source entry's data folder checks are deleted: that its store is
  `<repoRoot>/data/<env>.sqlite`, and that a refused `--env prod` creates nothing there.
  Under vitest the bin has no data folder, so neither check can show. The source bin
  still shows that its default env is `test` and that it refuses `prod`.

## Global constraints

- No code comments. Code, tests and commit messages are in English.
- Each test name says which rule it pins.
- Expected TOON is built with `encode` or pasted from a real run, never typed by hand.
- No test under vitest unsets `VITEST`, except the installed-entry tests in Task 5, which
  run with a temporary home folder. A spawned bin gets `QUAESTOR_DB` and `QUAESTOR_ENV`
  only when the test sets them.
- A test never weakens an assertion. Every assertion this plan changes is listed in its
  task.
- A new test that replaces an old one passes on its first run. Before committing, break
  the rule it names with a one-line edit to the source, watch the test fail on that rule,
  and revert the edit.
- `pnpm check` is green at the end of every task. knip and jscpd count: a support helper
  left with no user is deleted in the same task. If a deletion leaves a `src/` export with
  no user, stop and report it instead of editing `src/`.
- No file under `src/` changes except `*.test.ts` and Task 5's `buildRelease` output folder.
- Commit after each task on branch `skeleton-tests`, never on `rebuild`, never push.

## Review focus

1. A replacement passes for the wrong reason, for example seeded copies that the rule
   would keep anyway. The red check in Global constraints catches it, so it must be done
   for every new test.
2. A spawned process reaches a real store.
   - Bin tests strip `QUAESTOR_DB` and `QUAESTOR_ENV` unless the test sets them.
   - The installed-entry helper builds its environment from nothing and refuses a home
     outside `tmpdir()`. Without that guard, a mistake would back up the real
     `~/.quaestor/prod.sqlite` and remove its oldest copy.
3. A locked folder outlives a failing test. Every `chmod 0o500` registers the folder in
   `lockedFolder`, which `afterEach` restores.
4. A check run with `migrate` writes into the `dataDir` under test and breaks that test's
   folder listings. `migrate` uses a fresh throwaway `dataDir` on every call.
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
  QUAESTOR_DB and QUAESTOR_ENV all set, backup uses --env".
- Precedence, QUAESTOR_DB over QUAESTOR_ENV: new test. `vars: { QUAESTOR_DB: <tmp>/x.sqlite, QUAESTOR_ENV: 'staging' }`
  exits 0 with stderr `env: custom (<tmp>/x.sqlite)\n`, and no `staging.sqlite` in `dataDir`.
- Precedence, QUAESTOR_ENV over the default: new test. `vars: { QUAESTOR_ENV: 'staging' }`
  exits 0 with stderr `env: staging\n`, and `dataDir/staging.sqlite` exists.
- Precedence, the default: already covered by `backup.test.ts` "stderr is exactly env: test …".
- `--env x maps to <dataDir>/x.sqlite`: already covered by the `--env staging` test in
  `backup.test.ts`.
- Naming rule: `Prod` from `--env` is already covered by `backup.test.ts`. New `it.each`
  for `QUAESTOR_ENV: 'a b'` and `--env 1prod`: exit 1, empty stdout, stderr
  `encode({ error: { code: 'invalid_env', source, value, message: 'invalid <source> "<value>": start with a lowercase letter, then use lowercase letters, digits and dashes' } })`,
  and `dataDir` empty.
- `custom` is reserved: new `it.each` for `--env custom` and `QUAESTOR_ENV: 'custom'`:
  exit 1, `invalid_env`, message `invalid <source> "custom": custom is reserved for QUAESTOR_DB`,
  and `dataDir` empty.
- Relative QUAESTOR_DB: new test. `QUAESTOR_DB: 'rel/x.sqlite'` gives exit 1, `invalid_env`,
  `source: 'QUAESTOR_DB'`, and the message `invalid QUAESTOR_DB "rel/x.sqlite": must be an absolute path`.
- No data folder, named env: `default` is already covered by `backup.test.ts`. New
  `it.each` with `dataDir: null` for `--env prod` and `QUAESTOR_ENV: 'x'`: exit 1, stderr
  `encode({ error: { code: 'named_env_disabled', source, env, message: 'named environments are disabled here (<source>: <env>); set QUAESTOR_DB to a temporary file' } })`.
- No data folder, QUAESTOR_DB still names a custom store: already covered by
  `backup.test.ts` "QUAESTOR_DB with no data folder exits 1 as backups_disabled …", whose
  stderr starts `env: custom (<path>)`.

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
- Modify: `src/shell/cli/commands/backup/backup.test.ts`,
  `src/core/backups/backups.test.ts` (its import only: `from '#core/backups'`)
- Delete: `src/shell/db/backups/backups.test.ts`

The core test keeps every case as it is, `pr.d` included: which copies to remove is pure
logic, tested through its barrel. Only the shell's store backups move to the command.

Seeded copies are files whose content is their own name, so the test can check they are
untouched. `FIXED_INSTANT` is `2026-11-23T21:04:05.123Z`, so `COPY_NAME` is
`test-2026-11-23T21-04-05-123Z.sqlite`.

Ledger for `src/shell/db/backups/backups.test.ts`:

- The copy opens with the same content: new test "the copy holds the same accounts as the
  store". With `migrationsDir: SHIPPED_MIGRATIONS` on every call: run `account add Wallet
  --emoji 💵 --type debit --currency USD --opening 120.50 --opening-date 2026-01-05`, then
  `backup`, then `account list`. Its stdout equals `account list` with
  `vars: { QUAESTOR_DB: <copy> }`, and contains `Wallet`.
- The sixth backup removes that env's oldest copy only: new test "a sixth backup removes
  that env's oldest copy and leaves other envs and other files untouched". Seed five
  `prod-2026-11-0{1..5}T10-00-00-000Z.sqlite`, two `test-2026-10-0{1,2}T10-00-00-000Z.sqlite`
  and `notes.txt`. `backup --env prod` prints `removed` = the 2026-11-01 prod copy, and
  every other seed is intact.
- Same instant: already covered by "a second backup at the same instant exits 2 …".
- Partial copies: new test "a partial copy another process left or is still writing is
  neither used nor removed". Seed `${COPY_NAME}.partial` and `${COPY_NAME}.0.partial`, then
  `backup` exits 0. Both are intact, and the folder holds them plus `COPY_NAME`.
- A clock older than the copies on disk: new test "a clock older than the copies on disk
  keeps the copy it just wrote". Seed five `test-2026-12-0{1..5}T10-00-00-000Z.sqlite`.
  `backup` prints `path` = `COPY_NAME` and `removed: []`, and the five seeds are intact.
- A copy that cannot be moved into place: already covered by "a second backup at the same
  instant exits 2 …". A folder blocking the name fails the same `link` with `EEXIST`, and
  that test already asserts the listing is `[COPY_NAME]`, so no `.partial` is left.
- A backups folder that cannot be created: new test. Put the store at
  `QUAESTOR_DB=<other tmp>/x.sqlite` and `chmod 0o500` the `dataDir`, registered in
  `lockedFolder`. `backup` exits 2, stderr starts `env: custom (<path>)\n` and holds
  `backup_not_written` with `folder` = `<dataDir>/backups`, and `dataDir` is empty.

- [ ] **Step 1:** Write the new tests, change the core test's import, and delete the old
  file. Run `pnpm vitest run src/shell/cli/commands/backup src/core/backups` and expect
  PASS.
- [ ] **Step 2:** Run each red check below, in `src/shell/db/backups/backups.ts`, watch its
  test fail, and revert the edit.
  - Replace the `backup(…)` call in `writeCopy` with `new DatabaseSync(partial).close()`.
    Fails: "the copy holds the same accounts".
  - Pass `4` as `keep` to `copiesToRemove` in `removeOldCopies`. Fails: "a sixth backup …".
  - Name the partial `${path}${PARTIAL_SUFFIX}`, without the pid. Fails: "a partial copy …".
  - Pass no `kept` name to `copiesToRemove`. Fails: "a clock older …".
  - Drop the `finally` `rm(partial)`. Fails: "a second backup at the same instant …".
  - Move `mkdir` above the `try` in `writeCopy`. Fails: "a backups folder that cannot be
    created".
- [ ] **Step 3:** Run `pnpm check` and expect green. Commit
  `test(cli): store backups through the command`.

### Task 3: migrations and the connection through the command

**Files:**
- Modify: `src/shell/cli/commands/backup/backup.test.ts`
- Delete: `src/shell/db/migrations/migrations.test.ts`, `src/shell/db/database/database.test.ts`,
  and `tests/support/store/`, which has no user left after this task.

**Produces:** in `backup.test.ts`, `migrate(path: string, migrationsDir: string): Promise<string[]>`.
It runs `backup` with `vars: { QUAESTOR_DB: path }`, the given migrations, and a fresh
`dataDir: tempDir('quaestor-migrate-')` on every call, because two calls at the fixed
instant would otherwise collide as `already exists`. It throws with the stderr if the
exit is not 0, and returns the names on the `migrated: ` lines of stderr, in order. It is
the setup that replaces `openTestStore`, and the check that replaces `fixtureTables`.

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

- migrations 1, "a new store is created with every migration applied": already covered
  by "backup on a new store applies the migrations first" (stderr plus `migrate(copy)`).
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
- [ ] **Step 3:** `grep -rn --include='*.test.ts' -e runSql -e selectAll -e openTestStore -e closeStore src tests`
  returns nothing. Run `pnpm check` and expect green. Commit
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
  `encode({ error: { code: 'invalid_env', source, value: 'prod', message: 'invalid <source> "prod": prod is reserved for the installed quaestor' } })`.
- The source context finds migrations in `<repoRoot>/migrations`, plus migrations test 3:
  new test "the source bin migrates a new store with every shipped migration".
  `vars: { QUAESTOR_DB: <tmp>/x.sqlite }` and `['account', 'list']` give status 0, stdout
  `accounts: []\n`, and stderr `env: custom (<path>)\n` followed by `migrated: <name>\n`
  for every folder under `SHIPPED_MIGRATIONS` that holds `MIGRATION_FILE`, sorted.
- The source default is `test` under vitest: already covered by "the source bin under
  vitest refuses its default env" and the leak test (`source: 'default', env: 'test'`).
  The data folder checks are deleted (ruling).
- Every installed-entry case moves to Task 5.

- [ ] **Step 1:** Write the new tests and delete `context.test.ts`. Run
  `pnpm vitest run src/shell/cli/bin` and expect PASS.
- [ ] **Step 2:** Red checks, each reverted after it fails: change `DEV_VERSION` in
  `context.constants.ts` (fails the `--version` test), change `MIGRATIONS_FOLDER` there
  (fails the shipped-migrations test), and empty the source's `releaseOnlyEnvs` in
  `context.ts` (fails both `prod` cases as `named_env_disabled`).
- [ ] **Step 3:** Run `pnpm check` and expect green. Commit
  `test(cli): the source entry through its bin`.

### Task 5: the installed quaestor end to end

**Files:**
- Modify: `src/shell/release/build/build.ts`
- Create: `src/shell/cli/released.test.ts`

**Interfaces:**
- `buildRelease(release: Release, outDir: string = release.repoRoot): Promise<void>` writes
  the bundle to `join(outDir, BUNDLE_FILE)`. `release.ts` keeps calling it with one
  argument, so `pnpm release` is unchanged.

Setup, in each test:
- Build into `pkg = tempDir('quaestor-package-')` with
  `{ version: '0.0.0', commit: 'abc1234', repoRoot: REPO_ROOT }`.
- Copy `SHIPPED_MIGRATIONS` to `<pkg>/migrations`. That is the packed layout:
  `dist/quaestor.js` next to `migrations/`.

The helper `installed(args: string[], { home, vars = {} }: { home: string; vars?: Record<string, string> })`:
- throws unless `home` is inside `tmpdir()`;
- runs `spawnSync(process.execPath, [<pkg>/dist/quaestor.js, ...args])` with
  `env: { PATH: process.env.PATH, HOME: home, ...vars }`, built from nothing, so no
  `VITEST` and no `QUAESTOR_*` reach it.

The installed entry runs on the real clock, so copy names are matched with
`/^prod-.+\.sqlite$/`, not pasted.

Ledger, from the deleted `context.test.ts`:

- The installed entry prints `<version> (<commit>)`: new test "the installed quaestor
  prints its version and commit". Status 0, stdout `0.0.0 (abc1234)\n`, stderr empty.
- Defaults to `prod` under `<home>/.quaestor`, finds migrations in
  `<entryDir>/../migrations`, and its first run creates `~/.quaestor`: one new test,
  "the installed quaestor's first run creates ~/.quaestor/prod.sqlite, backs it up before
  migrating, and applies every shipped migration".
  - `backup` gives status 0.
  - stderr starts with `env: prod\n`, then `backup: <home>/.quaestor/backups/prod-….sqlite (before migrating)\n`,
    then one `migrated: <name>\n` per shipped migration.
  - `<home>/.quaestor/prod.sqlite` exists.
  - `<home>/.quaestor/backups/` holds two `prod-` copies, one of them the `path` that
    stdout prints.
- No data folder under vitest: new test "the installed quaestor under vitest refuses its
  default env". `vars: { VITEST: 'true' }` and `backup` give status 1, stderr
  `encode({ error: { code: 'named_env_disabled', source: 'default', env: 'prod', message: 'named environments are disabled here (default: prod); set QUAESTOR_DB to a temporary file' } })`,
  and no `.quaestor` folder in `home`.

- [ ] **Step 1:** Add `outDir` to `buildRelease` and write the three tests. Run
  `pnpm vitest run src/shell/cli/released.test.ts src/shell/release` and expect PASS.
  `release.test.ts` must stay green unchanged.
- [ ] **Step 2:** Red checks in `context.ts` and `context.constants.ts`, each reverted after
  it fails:
  - change `RELEASE_DATA_FOLDER` (fails the first-run test);
  - drop the `'..'` from the installed `migrationsDir` (fails the first-run test);
  - drop `outsideVitest` for the installed context (fails the vitest test);
  - change `releaseVersion`'s format (fails the version test).
- [ ] **Step 3:** Run `pnpm check` and expect green. Commit
  `test(cli): the installed quaestor end to end`.

### Closing

- [ ] Delete item 1 from `docs/backlog.md` and renumber the rest. Delete this plan.
  Commit `docs: close skeleton tests through the command`. Angelo merges.

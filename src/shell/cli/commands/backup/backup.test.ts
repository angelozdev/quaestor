import { decode, encode } from '@toon-format/toon'
import { createHash } from 'node:crypto'
import { chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { closeStore } from '#shell/db'
import { FIXTURE_MIGRATIONS } from '../../../../../tests/support/fixture-migrations/fixture-migrations.constants.ts'
import {
  noMigrations,
  writeMigrations,
} from '../../../../../tests/support/fixture-migrations/fixture-migrations.ts'
import { FIXED_INSTANT } from '../../../../../tests/support/run-cli/run-cli.constants.ts'
import { runCli } from '../../../../../tests/support/run-cli/run-cli.ts'
import type { CliOverrides } from '../../../../../tests/support/run-cli/run-cli.types.ts'
import { openTestStore, runSql, selectAll } from '../../../../../tests/support/store/store.ts'
import { tempDir } from '../../../../../tests/support/temp-dir/temp-dir.ts'

const COPY_NAME = 'test-2026-11-23T21-04-05-123Z.sqlite'

let dataDir: string
let lockedFolder: string | null = null

beforeEach(() => {
  dataDir = tempDir('quaestor-cli-')
})

afterEach(() => {
  if (lockedFolder !== null) chmodSync(lockedFolder, 0o700)
  lockedFolder = null
})

function sha256(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

function backup(argv: string[] = [], overrides: CliOverrides = {}) {
  return runCli(['backup', ...argv], { defaultEnv: 'test', dataDir, ...overrides })
}

function fixtureMigrations(): string {
  return writeMigrations(tempDir('quaestor-migrations-'), FIXTURE_MIGRATIONS)
}

function advancingClock(): () => Date {
  let calls = 0
  return () => new Date(Date.parse(FIXED_INSTANT) + calls++)
}

function fixtureTables(path: string): unknown[] {
  return selectAll(path, "select name from sqlite_master where name like 'fixture_%' order by name")
}

async function expectNotAStoreLeftAlone(env: string) {
  const store = join(dataDir, `${env}.sqlite`)
  writeFileSync(store, 'not a store\n')
  const before = sha256(store)

  const { code, stdout, stderr } = await backup(['--env', env], {
    migrationsDir: fixtureMigrations(),
    clock: advancingClock(),
  })

  expect(code).toBe(2)
  expect(stdout).toBe('')
  expect(stderr).toBe(
    `env: ${env}\n${encode({ error: { code: 'unexpected', message: 'file is not a database' } })}\n`,
  )
  expect(sha256(store)).toBe(before)
  expect(readdirSync(dataDir)).toEqual([`${env}.sqlite`])
}

describe('quaestor backup', () => {
  it("backup copies the default env's store and prints the copy, TOON by default", async () => {
    const { code, stdout } = await backup()

    expect(code).toBe(0)
    expect(existsSync(join(dataDir, 'test.sqlite'))).toBe(true)
    expect(stdout).toBe(`${encode({ path: join(dataDir, 'backups', COPY_NAME), removed: [] })}\n`)
    expect(existsSync(join(dataDir, 'backups', COPY_NAME))).toBe(true)
  })

  it('backup prints the copy it removed', async () => {
    const folder = join(dataDir, 'backups')
    const seeded = [1, 2, 3, 4, 5].map((day) => `test-2026-11-0${day}T10-00-00-000Z.sqlite`)
    mkdirSync(folder)
    for (const name of seeded) writeFileSync(join(folder, name), name)

    const { code, stdout } = await backup()

    expect(code).toBe(0)
    expect(stdout).toBe(
      `${encode({ path: join(folder, COPY_NAME), removed: [join(folder, seeded[0]!)] })}\n`,
    )
    expect(readdirSync(folder).toSorted()).toEqual([...seeded.slice(1), COPY_NAME])
  })

  it('--json prints the same fields as one line of JSON', async () => {
    const { code, stdout } = await backup(['--json'])

    expect(code).toBe(0)
    expect(stdout).toBe(`{"path":"${join(dataDir, 'backups', COPY_NAME)}","removed":[]}\n`)
  })

  it('stderr is exactly env: test and stdout holds only the result', async () => {
    const { stdout, stderr } = await backup()

    expect(stderr).toBe('env: test\n')
    expect(stdout).toBe(`${encode({ path: join(dataDir, 'backups', COPY_NAME), removed: [] })}\n`)
  })

  it('backup --help opens no store and prints no env line', async () => {
    const { code, stdout, stderr } = await backup(['--help'])

    expect(code).toBe(0)
    expect(stdout).toContain('Usage: quaestor backup')
    expect(stderr).toBe('')
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('an unknown command exits 1 as unknown_command', async () => {
    const { code, stdout, stderr } = await runCli(['nope'], { dataDir })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'unknown_command', message: "unknown command 'nope'" } })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('backup --bogus exits 1 and opens no store', async () => {
    const { code, stdout, stderr } = await backup(['--bogus'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'unknown_option', message: "unknown option '--bogus'" } })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('with no data folder backup exits 1 as named_env_disabled and creates nothing', async () => {
    const { code, stdout, stderr } = await backup([], { dataDir: null })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'named_env_disabled',
          source: 'default',
          env: 'test',
          message:
            'named environments are disabled here (default: test); set QUAESTOR_DB to a temporary file',
        },
      })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('an unwritable backups folder exits 2 as backup_not_written, leaves no copy and leaves the store unchanged', async () => {
    const store = join(dataDir, 'test.sqlite')
    closeStore(await openTestStore(store, noMigrations()))
    runSql(
      store,
      "create table notes (id integer primary key, body text); insert into notes (body) values ('first')",
    )
    const before = sha256(store)
    const folder = join(dataDir, 'backups')
    mkdirSync(folder, { mode: 0o500 })
    lockedFolder = folder

    const { code, stdout, stderr } = await backup()

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toMatch(
      new RegExp(
        `^${RegExp.escape(`env: test\nerror:\n  code: backup_not_written\n  folder: ${folder}\n  reason: `)}`,
      ),
    )
    const { error } = decode(stderr) as { error: { reason: string; message: string } }
    expect(error.message).toBe(`cannot write backup to ${folder}: ${error.reason}`)
    expect(readdirSync(folder)).toEqual([])
    expect(sha256(store)).toBe(before)
  })

  it('a data folder whose path holds a space works', async () => {
    const spaced = tempDir('quaestor cli-')

    const { code, stdout, stderr } = await backup([], { dataDir: spaced })

    expect(code).toBe(0)
    expect(stderr).toBe('env: test\n')
    expect(stdout).toBe(`${encode({ path: join(spaced, 'backups', COPY_NAME), removed: [] })}\n`)
    expect(existsSync(join(spaced, 'backups', COPY_NAME))).toBe(true)
  })

  it('with --env, QUAESTOR_DB and QUAESTOR_ENV all set, backup uses --env', async () => {
    const storeDir = tempDir('quaestor-store-')
    const vars = { QUAESTOR_DB: join(storeDir, 'x.sqlite'), QUAESTOR_ENV: 'other' }

    const { code, stdout, stderr } = await backup(['--env', 'staging'], { vars })

    expect(code).toBe(0)
    expect(stderr).toBe('env: staging\n')
    expect(stdout).toBe(
      `${encode({ path: join(dataDir, 'backups', 'staging-2026-11-23T21-04-05-123Z.sqlite'), removed: [] })}\n`,
    )
    expect(existsSync(join(dataDir, 'staging.sqlite'))).toBe(true)
    expect(readdirSync(storeDir)).toEqual([])
  })

  it('an invalid env exits 1 as invalid_env before any store is opened', async () => {
    const { code, stdout, stderr } = await backup(['--env', 'Prod'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'invalid_env',
          source: '--env',
          value: 'Prod',
          message: 'invalid --env "Prod": use lowercase letters, digits and dashes',
        },
      })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('QUAESTOR_DB names a custom store shown as env: custom (<path>)', async () => {
    const storeDir = tempDir('quaestor-store-')
    const dbPath = join(storeDir, 'x.sqlite')

    const { code, stdout, stderr } = await backup([], { vars: { QUAESTOR_DB: dbPath } })

    const copy = join(dataDir, 'backups', 'custom-2026-11-23T21-04-05-123Z.sqlite')
    expect(code).toBe(0)
    expect(stderr).toBe(`env: custom (${dbPath})\n`)
    expect(stdout).toBe(`${encode({ path: copy, removed: [] })}\n`)
    expect(existsSync(dbPath)).toBe(true)
    expect(existsSync(copy)).toBe(true)
    expect(readdirSync(dataDir)).toEqual(['backups'])
  })

  it('QUAESTOR_DB with no data folder exits 1 as backups_disabled and writes no copy', async () => {
    const storeDir = tempDir('quaestor-store-')
    const dbPath = join(storeDir, 'x.sqlite')

    const { code, stdout, stderr } = await backup([], {
      dataDir: null,
      vars: { QUAESTOR_DB: dbPath },
    })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: custom (${dbPath})\n${encode({
        error: { code: 'backups_disabled', message: 'backups are disabled here (under vitest)' },
      })}\n`,
    )
    expect(readdirSync(storeDir)).toEqual(['x.sqlite'])
  })

  it('QUAESTOR_DB in a folder that does not exist exits 2 as unexpected and creates nothing', async () => {
    const storeDir = tempDir('quaestor-store-')
    const dbPath = join(storeDir, 'missing', 'x.sqlite')

    const { code, stdout, stderr } = await backup([], { vars: { QUAESTOR_DB: dbPath } })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: custom (${dbPath})\n${encode({
        error: { code: 'unexpected', message: 'unable to open database file' },
      })}\n`,
    )
    expect(readdirSync(storeDir)).toEqual([])
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('backup on a new store applies the migrations first', async () => {
    const { code, stdout, stderr } = await backup([], { migrationsDir: fixtureMigrations() })

    const copy = join(dataDir, 'backups', COPY_NAME)
    expect(code).toBe(0)
    expect(stderr).toBe(
      'env: test\nmigrated: 20261123000000_first\nmigrated: 20261123000100_second\n',
    )
    expect(stdout).toBe(`${encode({ path: copy, removed: [] })}\n`)
    expect(fixtureTables(copy)).toEqual([{ name: 'fixture_a' }, { name: 'fixture_b' }])
  })

  it('in a non-prod env pending migrations apply without a backup', async () => {
    const { code, stderr } = await backup(['--env', 'test'], { migrationsDir: fixtureMigrations() })

    expect(code).toBe(0)
    expect(stderr).toBe(
      'env: test\nmigrated: 20261123000000_first\nmigrated: 20261123000100_second\n',
    )
    expect(readdirSync(join(dataDir, 'backups'))).toEqual([COPY_NAME])
  })

  it('a prod store with pending migrations is backed up before they apply', async () => {
    const folder = join(dataDir, 'backups')
    const beforeMigrating = join(folder, 'prod-2026-11-23T21-04-05-123Z.sqlite')
    const own = join(folder, 'prod-2026-11-23T21-04-05-124Z.sqlite')

    const { code, stdout, stderr } = await backup(['--env', 'prod'], {
      migrationsDir: fixtureMigrations(),
      clock: advancingClock(),
    })

    expect(code).toBe(0)
    expect(stderr).toBe(
      `env: prod\nbackup: ${beforeMigrating} (before migrating)\n` +
        'migrated: 20261123000000_first\nmigrated: 20261123000100_second\n',
    )
    expect(stdout).toBe(`${encode({ path: own, removed: [] })}\n`)
    expect(fixtureTables(beforeMigrating)).toEqual([])
    expect(fixtureTables(own)).toEqual([{ name: 'fixture_a' }, { name: 'fixture_b' }])
    expect(readdirSync(folder)).toEqual([
      'prod-2026-11-23T21-04-05-123Z.sqlite',
      'prod-2026-11-23T21-04-05-124Z.sqlite',
    ])
  })

  it('a current store takes no backup and reports nothing about schema', async () => {
    const folder = join(dataDir, 'backups')
    const prod = { migrationsDir: fixtureMigrations(), clock: advancingClock() }
    await backup(['--env', 'prod'], prod)
    const before = readdirSync(folder)

    const { code, stderr } = await backup(['--env', 'prod'], prod)

    expect(code).toBe(0)
    expect(stderr).toBe('env: prod\n')
    expect(readdirSync(folder).filter((name) => !before.includes(name))).toHaveLength(1)
  })

  it('a store file that is not SQLite exits 2 as unexpected and is left unchanged', async () => {
    await expectNotAStoreLeftAlone('test')
  })

  it('a prod store file that is not SQLite is left unchanged and gets no copy before migrating', async () => {
    await expectNotAStoreLeftAlone('prod')
  })

  it('bare quaestor prints the help on stdout and exits 0', async () => {
    const { code, stdout, stderr } = await runCli([], { dataDir })

    expect(code).toBe(0)
    expect(stdout).toContain('Usage: quaestor')
    expect(stdout).toContain('backup')
    expect(stderr).toBe('')
    expect(readdirSync(dataDir)).toEqual([])
  })

  it.for([
    [
      'an error no class names',
      () => {
        throw new Error('clock broke')
      },
    ],
    [
      'a thrown value that is not an Error',
      () => {
        throw 'clock broke'
      },
    ],
  ] as const)('%s exits 2 as unexpected with its message', async ([, clock], { expect }) => {
    const { code, stdout, stderr } = await backup([], { clock })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: test\n${encode({ error: { code: 'unexpected', message: 'clock broke' } })}\n`,
    )
  })
})

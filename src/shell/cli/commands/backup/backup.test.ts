import { decode, encode } from '@toon-format/toon'
import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  FAILING_MIGRATIONS,
  FIXTURE_MIGRATIONS,
  SHIPPED_MIGRATIONS,
} from '../../../../../tests/support/fixture-migrations/fixture-migrations.constants.ts'
import {
  noMigrations,
  writeMigrations,
} from '../../../../../tests/support/fixture-migrations/fixture-migrations.ts'
import type { FixtureMigrations } from '../../../../../tests/support/fixture-migrations/fixture-migrations.types.ts'
import { FIXED_INSTANT } from '../../../../../tests/support/run-cli/run-cli.constants.ts'
import { runCli } from '../../../../../tests/support/run-cli/run-cli.ts'
import type { CliOverrides } from '../../../../../tests/support/run-cli/run-cli.types.ts'
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

const MIGRATED = 'migrated: '

const FIXTURE_NAMES = Object.keys(FIXTURE_MIGRATIONS)

const HOLD_EXCLUSIVE_LOCK = `
const { DatabaseSync } = require('node:sqlite')
const db = new DatabaseSync(process.argv[1])
db.exec('BEGIN EXCLUSIVE')
process.stdout.write('locked\\n')
setTimeout(() => {
  db.exec('COMMIT')
  db.close()
}, 400)
`

const WALLET_ARGV = [
  'account',
  'add',
  'Wallet',
  '--emoji',
  '💵',
  '--type',
  'debit',
  '--currency',
  'USD',
  '--opening',
  '120.50',
  '--opening-date',
  '2026-01-05',
]

function seed(folder: string, names: string[]): void {
  mkdirSync(folder, { recursive: true })
  for (const name of names) writeFileSync(join(folder, name), name)
}

function expectIntact(folder: string, names: string[]): void {
  for (const name of names) expect(readFileSync(join(folder, name), 'utf8')).toBe(name)
}

function sha256(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

function backup(argv: string[] = [], overrides: CliOverrides = {}) {
  return runCli(['backup', ...argv], { defaultEnv: 'test', dataDir, ...overrides })
}

function fixtureMigrations(migrations: FixtureMigrations = FIXTURE_MIGRATIONS): string {
  return writeMigrations(tempDir('quaestor-migrations-'), migrations)
}

function advancingClock(): () => Date {
  let calls = 0
  return () => new Date(Date.parse(FIXED_INSTANT) + calls++)
}

async function migrate(path: string, migrationsDir: string): Promise<string[]> {
  const { code, stderr } = await runCli(['backup'], {
    dataDir: tempDir('quaestor-migrate-'),
    vars: { QUAESTOR_DB: path },
    migrationsDir,
  })
  if (code !== 0) throw new Error(`migrate exited ${code}: ${stderr}`)
  return stderr
    .split('\n')
    .filter((line) => line.startsWith(MIGRATED))
    .map((line) => line.slice(MIGRATED.length))
}

function holdExclusiveLock(path: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['-e', HOLD_EXCLUSIVE_LOCK, path])
    child.once('error', reject)
    child.stdout.once('data', () => resolve())
    child.once('close', () => reject(new Error('the writer ended before it held the file')))
  })
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

  it('a second backup at the same instant exits 2 as backup_not_written and keeps the first copy', async () => {
    const folder = join(dataDir, 'backups')
    const shipped = { migrationsDir: SHIPPED_MIGRATIONS }
    await backup([], shipped)
    const copy = join(folder, COPY_NAME)
    const before = sha256(copy)
    expect((await runCli(WALLET_ARGV, { dataDir, ...shipped })).code).toBe(0)

    const { code, stdout, stderr } = await backup([], shipped)

    const reason = `${COPY_NAME} already exists`
    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: test\n${encode({
        error: {
          code: 'backup_not_written',
          folder,
          reason,
          message: `cannot write backup to ${folder}: ${reason}`,
        },
      })}\n`,
    )
    expect(sha256(copy)).toBe(before)
    expect(readdirSync(folder)).toEqual([COPY_NAME])
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
    const shipped = { migrationsDir: SHIPPED_MIGRATIONS }
    expect((await runCli(WALLET_ARGV, { dataDir, ...shipped })).code).toBe(0)
    const before = sha256(store)
    const folder = join(dataDir, 'backups')
    mkdirSync(folder, { mode: 0o500 })
    lockedFolder = folder

    const { code, stdout, stderr } = await backup([], shipped)

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
          message:
            'invalid --env "Prod": start with a lowercase letter, then use lowercase letters, digits and dashes',
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

  it('QUAESTOR_DB in a folder that does not exist exits 1 as invalid_env and creates nothing', async () => {
    const storeDir = tempDir('quaestor-store-')
    const dbPath = join(storeDir, 'missing', 'x.sqlite')

    const { code, stdout, stderr } = await backup([], { vars: { QUAESTOR_DB: dbPath } })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'invalid_env',
          source: 'QUAESTOR_DB',
          value: dbPath,
          message: `invalid QUAESTOR_DB "${dbPath}": its folder does not exist`,
        },
      })}\n`,
    )
    expect(readdirSync(storeDir)).toEqual([])
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('QUAESTOR_DB in a folder that exists but cannot be written exits 2 as unexpected and creates nothing', async () => {
    const storeDir = tempDir('quaestor-store-')
    const folder = join(storeDir, 'locked')
    mkdirSync(folder, { mode: 0o500 })
    lockedFolder = folder
    const dbPath = join(folder, 'x.sqlite')

    const { code, stdout, stderr } = await backup([], { vars: { QUAESTOR_DB: dbPath } })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: custom (${dbPath})\n${encode({
        error: { code: 'unexpected', message: 'unable to open database file' },
      })}\n`,
    )
    expect(readdirSync(folder)).toEqual([])
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
    expect(await migrate(copy, fixtureMigrations())).toEqual([])
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
    expect(await migrate(beforeMigrating, fixtureMigrations())).toEqual(FIXTURE_NAMES)
    expect(await migrate(own, fixtureMigrations())).toEqual([])
    expect(readdirSync(folder)).toEqual([
      'prod-2026-11-23T21-04-05-123Z.sqlite',
      'prod-2026-11-23T21-04-05-124Z.sqlite',
    ])
  })

  it('a prod store with pending migrations and an unwritable backups folder exits 2 as backup_not_written and migrates nothing', async () => {
    const folder = join(dataDir, 'backups')
    mkdirSync(folder, { mode: 0o500 })
    lockedFolder = folder

    const { code, stdout, stderr } = await backup(['--env', 'prod'], {
      migrationsDir: fixtureMigrations(),
    })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toMatch(
      new RegExp(
        `^${RegExp.escape(`env: prod\nerror:\n  code: backup_not_written\n  folder: ${folder}\n  reason: `)}`,
      ),
    )
    expect(stderr).not.toContain('migrated:')
    expect(readdirSync(folder)).toEqual([])
    expect(await migrate(join(dataDir, 'prod.sqlite'), fixtureMigrations())).toEqual(FIXTURE_NAMES)
  })

  it('a failing migration in prod exits 2 as migration_failed and keeps the copy taken before it', async () => {
    const folder = join(dataDir, 'backups')
    const beforeMigrating = join(folder, 'prod-2026-11-23T21-04-05-123Z.sqlite')

    const { code, stdout, stderr } = await backup(['--env', 'prod'], {
      migrationsDir: fixtureMigrations(FAILING_MIGRATIONS),
      clock: advancingClock(),
    })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: prod\nbackup: ${beforeMigrating} (before migrating)\n${encode({
        error: {
          code: 'migration_failed',
          migration: '20261123000100_second',
          reason: 'near "this": syntax error',
          message: 'migration 20261123000100_second failed: near "this": syntax error',
        },
      })}\n`,
    )
    expect(readdirSync(folder)).toEqual(['prod-2026-11-23T21-04-05-123Z.sqlite'])
    expect(await migrate(join(dataDir, 'prod.sqlite'), fixtureMigrations())).toEqual(FIXTURE_NAMES)
  })

  it('a store with migrations this code does not know exits 2 as unknown_migrations and is unchanged', async () => {
    const store = join(dataDir, 'prod.sqlite')
    await migrate(store, fixtureMigrations())
    const before = sha256(store)

    const { code, stdout, stderr } = await backup(['--env', 'prod'], {
      migrationsDir: fixtureMigrations({
        '20261123000000_first': FIXTURE_MIGRATIONS['20261123000000_first'],
        '20261123000200_third': 'CREATE TABLE fixture_c (id integer primary key);',
      }),
      clock: advancingClock(),
    })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: prod\n${encode({
        error: {
          code: 'unknown_migrations',
          names: ['20261123000100_second'],
          message: 'the store has migrations this code does not know: 20261123000100_second',
        },
      })}\n`,
    )
    expect(sha256(store)).toBe(before)
    expect(readdirSync(dataDir)).toEqual(['prod.sqlite'])
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

describe('quaestor backup copies', () => {
  it('the copy holds the same accounts as the store', async () => {
    const shipped = { migrationsDir: SHIPPED_MIGRATIONS }
    expect((await runCli(WALLET_ARGV, { dataDir, ...shipped })).code).toBe(0)

    const { stdout } = await backup([], shipped)

    const { path } = decode(stdout) as { path: string }
    const original = await runCli(['account', 'list'], { dataDir, ...shipped })
    const copy = await runCli(['account', 'list'], {
      dataDir,
      ...shipped,
      vars: { QUAESTOR_DB: path },
    })
    expect(original.stdout).toContain('Wallet')
    expect(copy.stdout).toBe(original.stdout)
  })

  it("a sixth backup removes that env's oldest copy and leaves other envs and other files untouched", async () => {
    const folder = join(dataDir, 'backups')
    const prod = [1, 2, 3, 4, 5].map((day) => `prod-2026-11-0${day}T10-00-00-000Z.sqlite`)
    const others = [
      'test-2026-10-01T10-00-00-000Z.sqlite',
      'test-2026-10-02T10-00-00-000Z.sqlite',
      'notes.txt',
    ]
    const own = 'prod-2026-11-23T21-04-05-123Z.sqlite'
    seed(folder, [...prod, ...others])

    const { code, stdout } = await backup(['--env', 'prod'])

    expect(code).toBe(0)
    expect(stdout).toBe(
      `${encode({ path: join(folder, own), removed: [join(folder, prod[0]!)] })}\n`,
    )
    expect(readdirSync(folder).toSorted()).toEqual([...prod.slice(1), ...others, own].toSorted())
    expectIntact(folder, [...prod.slice(1), ...others])
  })

  it('a partial copy another process left or is still writing is neither used nor removed', async () => {
    const folder = join(dataDir, 'backups')
    const foreign = [`${COPY_NAME}.partial`, `${COPY_NAME}.0.partial`]
    seed(folder, foreign)

    const { code } = await backup()

    expect(code).toBe(0)
    expect(readdirSync(folder).toSorted()).toEqual([COPY_NAME, ...foreign].toSorted())
    expectIntact(folder, foreign)
    expect(await migrate(join(folder, COPY_NAME), noMigrations())).toEqual([])
  })

  it('a clock older than the copies on disk keeps the copy it just wrote', async () => {
    const folder = join(dataDir, 'backups')
    const newer = [1, 2, 3, 4, 5].map((day) => `test-2026-12-0${day}T10-00-00-000Z.sqlite`)
    seed(folder, newer)

    const { code, stdout } = await backup()

    expect(code).toBe(0)
    expect(stdout).toBe(`${encode({ path: join(folder, COPY_NAME), removed: [] })}\n`)
    expect(readdirSync(folder)).toEqual([COPY_NAME, ...newer])
    expectIntact(folder, newer)
  })

  it('a backups folder that cannot be created exits 2 as backup_not_written naming that folder', async () => {
    const dbPath = join(tempDir('quaestor-store-'), 'x.sqlite')
    const folder = join(dataDir, 'backups')
    chmodSync(dataDir, 0o500)
    lockedFolder = dataDir

    const { code, stdout, stderr } = await backup([], { vars: { QUAESTOR_DB: dbPath } })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toMatch(
      new RegExp(
        `^${RegExp.escape(`env: custom (${dbPath})\nerror:\n  code: backup_not_written\n  folder: ${folder}\n  reason: `)}`,
      ),
    )
    const { error } = decode(stderr.slice(stderr.indexOf('\n') + 1)) as {
      error: { reason: string; message: string }
    }
    expect(error.message).toBe(`cannot write backup to ${folder}: ${error.reason}`)
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('a store another process holds briefly is waited for, not refused as locked', async () => {
    const store = join(dataDir, 'test.sqlite')
    await migrate(store, noMigrations())
    await holdExclusiveLock(store)

    const { code, stdout } = await backup()

    expect(code).toBe(0)
    expect(stdout).toBe(`${encode({ path: join(dataDir, 'backups', COPY_NAME), removed: [] })}\n`)
  })
})

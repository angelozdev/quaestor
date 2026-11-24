import { chmodSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { openTestStore, runSql, selectAll } from '../../../../tests/support/store/store.ts'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { closeStore } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { backupStore } from './backups.ts'
import { BackupNotWrittenError } from './backups.errors.ts'

const NOW = new Date('2026-11-23T21:04:05.123Z')

let lockedFolder: string | null = null

afterEach(() => {
  if (lockedFolder !== null) chmodSync(lockedFolder, 0o700)
  lockedFolder = null
})

function tempStore(): Promise<Store> {
  return openTestStore(join(tempDir('quaestor-store-'), 'store.sqlite'))
}

async function notWritten(promise: Promise<unknown>): Promise<BackupNotWrittenError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof BackupNotWrittenError) return error
    throw error
  }
  throw new Error('expected the backup to be rejected as not written')
}

describe('backupStore', () => {
  it('the copy opens as a store with the same content', async () => {
    const storePath = join(tempDir('quaestor-store-'), 'store.sqlite')
    const store = await openTestStore(storePath)
    runSql(storePath, 'create table notes (id integer primary key, body text)')
    runSql(storePath, "insert into notes (body) values ('first'), ('second')")
    const root = tempDir('quaestor-data-')

    const { path, removed } = await backupStore({ store, env: 'test', root, now: NOW })

    const folder = join(root, 'backups')
    expect(path).toBe(join(folder, 'test-2026-11-23T21-04-05-123Z.sqlite'))
    expect(removed).toEqual([])
    const copy = await openTestStore(path)
    expect(selectAll(path, 'select * from notes order by id')).toEqual(
      selectAll(storePath, 'select * from notes order by id'),
    )
    expect(readdirSync(folder)).toEqual(['test-2026-11-23T21-04-05-123Z.sqlite'])
    closeStore(copy)
    closeStore(store)
  })

  it("a sixth backup removes that env's oldest copy only", async () => {
    const store = await tempStore()
    const root = tempDir('quaestor-data-')
    const folder = join(root, 'backups')
    const seeded = [
      'prod-2026-11-01T10-00-00-000Z.sqlite',
      'prod-2026-11-02T10-00-00-000Z.sqlite',
      'prod-2026-11-03T10-00-00-000Z.sqlite',
      'prod-2026-11-04T10-00-00-000Z.sqlite',
      'prod-2026-11-05T10-00-00-000Z.sqlite',
      'test-2026-10-01T10-00-00-000Z.sqlite',
      'test-2026-10-02T10-00-00-000Z.sqlite',
      'notes.txt',
    ]
    mkdirSync(folder)
    for (const name of seeded) writeFileSync(join(folder, name), name)

    const { removed } = await backupStore({ store, env: 'prod', root, now: NOW })

    expect(removed).toEqual([join(folder, 'prod-2026-11-01T10-00-00-000Z.sqlite')])
    expect(readdirSync(folder).toSorted()).toEqual(
      [...seeded.slice(1), 'prod-2026-11-23T21-04-05-123Z.sqlite'].toSorted(),
    )
    for (const name of seeded.slice(1)) {
      expect(readFileSync(join(folder, name), 'utf8')).toBe(name)
    }
    closeStore(store)
  })

  it('a second backup at the same instant fails as backup_not_written and leaves the first copy intact', async () => {
    const storePath = join(tempDir('quaestor-store-'), 'store.sqlite')
    const store = await openTestStore(storePath)
    runSql(storePath, 'create table notes (id integer primary key, body text)')
    runSql(storePath, "insert into notes (body) values ('first')")
    const root = tempDir('quaestor-data-')
    const folder = join(root, 'backups')
    const name = 'test-2026-11-23T21-04-05-123Z.sqlite'
    const { path } = await backupStore({ store, env: 'test', root, now: NOW })
    runSql(storePath, "insert into notes (body) values ('second')")

    const error = await notWritten(backupStore({ store, env: 'test', root, now: NOW }))

    expect(error.code).toBe('backup_not_written')
    expect(error.data).toEqual({ folder, reason: `${name} already exists` })
    expect(error.message).toBe(`cannot write backup to ${folder}: ${name} already exists`)
    expect(readdirSync(folder)).toEqual([name])
    expect(selectAll(path, 'select body from notes order by id')).toEqual([{ body: 'first' }])
    closeStore(store)
  })

  it('a clock older than the copies on disk keeps the copy it just wrote', async () => {
    const store = await tempStore()
    const root = tempDir('quaestor-data-')
    const folder = join(root, 'backups')
    const newer = [1, 2, 3, 4, 5].map((day) => `prod-2026-12-0${day}T10-00-00-000Z.sqlite`)
    mkdirSync(folder)
    for (const name of newer) writeFileSync(join(folder, name), name)

    const { path, removed } = await backupStore({ store, env: 'prod', root, now: NOW })

    expect(path).toBe(join(folder, 'prod-2026-11-23T21-04-05-123Z.sqlite'))
    expect(removed).toEqual([])
    expect(readdirSync(folder).toSorted()).toEqual([
      'prod-2026-11-23T21-04-05-123Z.sqlite',
      ...newer,
    ])
    for (const name of newer) expect(readFileSync(join(folder, name), 'utf8')).toBe(name)
    closeStore(store)
  })

  it('a copy that cannot be moved into place is a backup_not_written and leaves no .partial', async () => {
    const store = await tempStore()
    const root = tempDir('quaestor-data-')
    const folder = join(root, 'backups')
    const blocker = 'test-2026-11-23T21-04-05-123Z.sqlite'
    mkdirSync(join(folder, blocker), { recursive: true })

    const error = await notWritten(backupStore({ store, env: 'test', root, now: NOW }))

    expect(error.code).toBe('backup_not_written')
    expect(error.data).toEqual({ folder, reason: expect.stringMatching(/.+/) })
    expect(error.message).toBe(`cannot write backup to ${folder}: ${error.data.reason}`)
    expect(readdirSync(folder)).toEqual([blocker])
    closeStore(store)
  })

  it('a backups folder that cannot be created is a backup_not_written naming that folder', async () => {
    const store = await tempStore()
    const root = tempDir('quaestor-data-')
    chmodSync(root, 0o500)
    lockedFolder = root

    const error = await notWritten(backupStore({ store, env: 'test', root, now: NOW }))

    expect(error.code).toBe('backup_not_written')
    expect(error.data).toEqual({
      folder: join(root, 'backups'),
      reason: expect.stringMatching(/.+/),
    })
    expect(readdirSync(root)).toEqual([])
    closeStore(store)
  })
})

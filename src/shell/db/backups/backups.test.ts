import { readdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { runSql, selectAll } from '../../../../tests/support/store/store.ts'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { closeStore, openStore } from '../database/database.ts'
import { backupStore } from './backups.ts'

describe('backupStore', () => {
  it('the copy opens as a store with the same content', async () => {
    const storePath = join(tempDir('quaestor-store-'), 'store.sqlite')
    const store = await openStore(storePath)
    runSql(storePath, 'create table notes (id integer primary key, body text)')
    runSql(storePath, "insert into notes (body) values ('first'), ('second')")
    const root = tempDir('quaestor-data-')

    const { path, removed } = await backupStore({
      store,
      env: 'test',
      root,
      now: new Date('2026-11-23T21:04:05.123Z'),
    })

    const folder = join(root, 'backups')
    expect(path).toBe(join(folder, 'test-2026-11-23T21-04-05-123Z.sqlite'))
    expect(removed).toEqual([])
    const copy = await openStore(path)
    expect(selectAll(path, 'select * from notes order by id')).toEqual(
      selectAll(storePath, 'select * from notes order by id'),
    )
    expect(readdirSync(folder)).toEqual(['test-2026-11-23T21-04-05-123Z.sqlite'])
    closeStore(copy)
    closeStore(store)
  })
})

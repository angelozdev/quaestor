import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  FAILING_MIGRATIONS,
  FIXTURE_MIGRATIONS,
  MIGRATION_FILE,
  SHIPPED_MIGRATIONS,
} from '../../../../tests/support/fixture-migrations/fixture-migrations.constants.ts'
import { writeMigrations } from '../../../../tests/support/fixture-migrations/fixture-migrations.ts'
import { openTestStore, selectAll } from '../../../../tests/support/store/store.ts'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { closeStore } from '../database/database.ts'

async function newStore(migrationsDir: string): Promise<string> {
  const path = join(tempDir('quaestor-store-'), 'store.sqlite')
  closeStore(await openTestStore(path, migrationsDir))
  return path
}

function firstColumn(path: string, query: string): unknown[] {
  return selectAll(path, query).map((row) => Object.values(row)[0])
}

describe('migrations', () => {
  it('a new store is created with every migration applied', async () => {
    const migrationsDir = writeMigrations(tempDir('quaestor-migrations-'), FIXTURE_MIGRATIONS)
    const store = await newStore(migrationsDir)

    expect(
      firstColumn(
        store,
        "select name from sqlite_master where type = 'table' and name like 'fixture_%' order by name",
      ),
    ).toEqual(['fixture_a', 'fixture_b'])
    expect(firstColumn(store, 'select name from __drizzle_migrations order by id')).toEqual([
      '20261123000000_first',
      '20261123000100_second',
    ])
  })

  it('a failing migration keeps none of the pending ones', async () => {
    const path = join(tempDir('quaestor-store-'), 'store.sqlite')
    const migrationsDir = writeMigrations(tempDir('quaestor-migrations-'), FAILING_MIGRATIONS)

    await expect(openTestStore(path, migrationsDir)).rejects.toThrow(
      new RegExp(
        `^${RegExp.escape('migration 20261123000100_second failed: near "this": syntax error')}$`,
      ),
    )
    expect(
      firstColumn(
        path,
        "select name from sqlite_master where type = 'table' and name like 'fixture_%'",
      ),
    ).toEqual([])
    expect(firstColumn(path, 'select name from __drizzle_migrations')).toEqual([])
  })

  it('the shipped migrations folder opens a store', async () => {
    const shipped = readdirSync(SHIPPED_MIGRATIONS)
      .filter((name) => existsSync(join(SHIPPED_MIGRATIONS, name, MIGRATION_FILE)))
      .toSorted()

    const store = await newStore(SHIPPED_MIGRATIONS)

    expect(firstColumn(store, 'select name from __drizzle_migrations order by name')).toEqual(
      shipped,
    )
  })
})

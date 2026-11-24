import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  FAILING_MIGRATIONS,
  FIXTURE_MIGRATIONS,
} from '../../../../tests/support/fixture-migrations/fixture-migrations.constants.ts'
import {
  noMigrations,
  writeMigrations,
} from '../../../../tests/support/fixture-migrations/fixture-migrations.ts'
import { openTestStore } from '../../../../tests/support/store/store.ts'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { closeStore, openStore } from './database.ts'

afterEach(() => {
  vi.restoreAllMocks()
})

function storePath(): string {
  return join(tempDir('quaestor-store-'), 'store.sqlite')
}

function migrationsWith(migrations: Record<string, string>): string {
  return writeMigrations(tempDir('quaestor-migrations-'), migrations)
}

async function failingOpen(path: string, migrationsDir: string, beforeMigrating = async () => {}) {
  const close = vi.spyOn(DatabaseSync.prototype, 'close')
  await expect(
    openStore({ path, migrationsDir, beforeMigrating, onMigrated: () => {} }),
  ).rejects.toThrow()
  return close
}

describe('openStore', () => {
  it('closes the handle when the file is not a store', async () => {
    const path = storePath()
    writeFileSync(path, 'not a store\n')

    const close = await failingOpen(path, noMigrations())

    expect(close).toHaveBeenCalledTimes(1)
  })

  it('closes the handle when the store has migrations this code does not know', async () => {
    const path = storePath()
    closeStore(await openTestStore(path, migrationsWith(FIXTURE_MIGRATIONS)))

    const close = await failingOpen(path, noMigrations())

    expect(close).toHaveBeenCalledTimes(1)
  })

  it('closes the handle when a migration fails', async () => {
    const close = await failingOpen(storePath(), migrationsWith(FAILING_MIGRATIONS))

    expect(close).toHaveBeenCalledTimes(1)
  })

  it('closes the handle when the hook before migrating fails', async () => {
    const close = await failingOpen(storePath(), migrationsWith(FIXTURE_MIGRATIONS), () =>
      Promise.reject(new Error('backup broke')),
    )

    expect(close).toHaveBeenCalledTimes(1)
  })
})

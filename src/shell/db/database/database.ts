import { DatabaseSync } from 'node:sqlite'
import { drizzle } from 'drizzle-orm/node-sqlite'
import { drawCode, type RandomIndex } from '#core/ledger'
import {
  applyMigrations,
  pendingMigrations,
  refuseUnknownMigrations,
} from '../migrations/migrations.ts'
import {
  BEGIN,
  BUSY_TIMEOUT_MS,
  COMMIT,
  FOREIGN_KEYS_ON,
  ROLLBACK,
  SQLITE_CONSTRAINT_PRIMARYKEY,
  SQLITE_CONSTRAINT_UNIQUE,
} from './database.constants.ts'
import type { Database, Store, StoreRequest } from './database.types.ts'

function asStore(db: Database): Store {
  return db as unknown as Store
}

export function database(store: Store): Database {
  return store as unknown as Database
}

export async function openStore({
  path,
  migrationsDir,
  beforeMigrating,
  onMigrated,
}: StoreRequest): Promise<Store> {
  const client = new DatabaseSync(path, { timeout: BUSY_TIMEOUT_MS })
  const db = drizzle({ client })
  try {
    client.exec(FOREIGN_KEYS_ON)
    refuseUnknownMigrations(db, migrationsDir)
    const pending = pendingMigrations(db, migrationsDir)
    await beforeMigrating(asStore(db), pending)
    applyMigrations(db, migrationsDir)
    for (const name of pending) onMigrated(name)
    return asStore(db)
  } catch (error) {
    client.close()
    throw error
  }
}

export function closeStore(store: Store): void {
  database(store).$client.close()
}

export function inTransaction<T>(store: Store, dryRun: boolean, work: () => T): T {
  const { $client: client } = database(store)
  client.exec(BEGIN)
  try {
    const result = work()
    client.exec(dryRun ? ROLLBACK : COMMIT)
    return result
  } catch (error) {
    client.exec(ROLLBACK)
    throw error
  }
}

function constraintCode(error: unknown): unknown {
  const cause = error instanceof Error ? error.cause : undefined
  return cause instanceof Error && 'errcode' in cause ? cause.errcode : undefined
}

export function isUniqueViolation(error: unknown): boolean {
  return constraintCode(error) === SQLITE_CONSTRAINT_UNIQUE
}

export function isPrimaryKeyViolation(error: unknown): boolean {
  return constraintCode(error) === SQLITE_CONSTRAINT_PRIMARYKEY
}

export function withFreshCode<T>(
  randomIndex: RandomIndex,
  insert: (code: string) => T,
  isTaken: (error: unknown) => boolean = isPrimaryKeyViolation,
): T {
  for (;;) {
    try {
      return insert(drawCode(randomIndex))
    } catch (error) {
      if (!isTaken(error)) throw error
    }
  }
}

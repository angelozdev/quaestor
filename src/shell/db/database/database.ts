import { DatabaseSync } from 'node:sqlite'
import { drizzle } from 'drizzle-orm/node-sqlite'
import { applyMigrations, pendingMigrations } from '../migrations/migrations.ts'
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
  const db = drizzle({ client: new DatabaseSync(path) })
  const pending = pendingMigrations(db, migrationsDir)
  await beforeMigrating(asStore(db), pending)
  applyMigrations(db, migrationsDir)
  for (const name of pending) onMigrated(name)
  return asStore(db)
}

export function closeStore(store: Store): void {
  database(store).$client.close()
}

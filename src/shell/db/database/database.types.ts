import type { DatabaseSync } from 'node:sqlite'
import type { NodeSQLiteDatabase } from 'drizzle-orm/node-sqlite'

declare const storeBrand: unique symbol

export type Store = { readonly [storeBrand]: true }

export type Database = NodeSQLiteDatabase & { $client: DatabaseSync }

type BeforeMigratingHook = (store: Store, pending: string[]) => Promise<void>

type MigratedHook = (name: string) => void

export type StoreRequest = {
  path: string
  migrationsDir: string
  beforeMigrating: BeforeMigratingHook
  onMigrated: MigratedHook
}

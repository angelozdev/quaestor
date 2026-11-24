import { type MigrationMeta, readMigrationFiles } from 'drizzle-orm/migrator'
import { migrate } from 'drizzle-orm/node-sqlite/migrator'
import type { Database } from '../database/database.types.ts'
import { MIGRATIONS_TABLE } from './migrations.constants.ts'
import type { AppliedMigration } from './migrations.types.ts'

function hasMigrationsTable({ $client }: Database): boolean {
  const table = $client
    .prepare("select 1 from sqlite_master where type = 'table' and name = ?")
    .get(MIGRATIONS_TABLE)
  return table !== undefined
}

function appliedMigrations(db: Database): Set<string> {
  if (!hasMigrationsTable(db)) return new Set()
  const rows = db.$client
    .prepare(`select name from ${MIGRATIONS_TABLE}`)
    .all() as AppliedMigration[]
  return new Set(rows.map(({ name }) => name))
}

function pendingMigrationFiles(db: Database, migrationsDir: string): MigrationMeta[] {
  const applied = appliedMigrations(db)
  return readMigrationFiles({ migrationsFolder: migrationsDir }).filter(
    ({ name }) => !applied.has(name),
  )
}

export function pendingMigrations(db: Database, migrationsDir: string): string[] {
  return pendingMigrationFiles(db, migrationsDir).map(({ name }) => name)
}

export function applyMigrations(db: Database, migrationsDir: string): void {
  migrate(db, { migrationsFolder: migrationsDir, migrationsTable: MIGRATIONS_TABLE })
}

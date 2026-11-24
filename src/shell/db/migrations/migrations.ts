import { DrizzleQueryError } from 'drizzle-orm'
import { type MigrationMeta, readMigrationFiles } from 'drizzle-orm/migrator'
import { migrate } from 'drizzle-orm/node-sqlite/migrator'
import type { Database } from '../database/database.types.ts'
import { MIGRATIONS_TABLE } from './migrations.constants.ts'
import { MigrationFailedError, UnknownMigrationsError } from './migrations.errors.ts'
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

function unknownMigrations(db: Database, migrationsDir: string): string[] {
  const shipped = new Set(
    readMigrationFiles({ migrationsFolder: migrationsDir }).map(({ name }) => name),
  )
  return [...appliedMigrations(db)].filter((name) => !shipped.has(name)).toSorted()
}

export function refuseUnknownMigrations(db: Database, migrationsDir: string): void {
  const unknown = unknownMigrations(db, migrationsDir)
  if (unknown.length > 0) throw new UnknownMigrationsError(unknown)
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

function failedMigration(error: unknown, pending: MigrationMeta[]): MigrationFailedError | null {
  if (!(error instanceof DrizzleQueryError) || error.cause === undefined) return null
  const { query, cause } = error
  const migration = pending.find((candidate) => candidate.sql.includes(query))
  return migration === undefined ? null : new MigrationFailedError(migration.name, cause)
}

export function applyMigrations(db: Database, migrationsDir: string): void {
  const pending = pendingMigrationFiles(db, migrationsDir)
  try {
    migrate(db, { migrationsFolder: migrationsDir, migrationsTable: MIGRATIONS_TABLE })
  } catch (error) {
    throw failedMigration(error, pending) ?? error
  }
}

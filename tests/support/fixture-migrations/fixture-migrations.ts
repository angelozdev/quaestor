import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tempDir } from '../temp-dir/temp-dir.ts'
import { MIGRATION_FILE } from './fixture-migrations.constants.ts'
import type { FixtureMigrations } from './fixture-migrations.types.ts'

export function writeMigrations(dir: string, migrations: FixtureMigrations): string {
  for (const [name, sql] of Object.entries(migrations)) {
    mkdirSync(join(dir, name), { recursive: true })
    writeFileSync(join(dir, name, MIGRATION_FILE), sql)
  }
  return dir
}

export function noMigrations(): string {
  return tempDir('quaestor-migrations-')
}

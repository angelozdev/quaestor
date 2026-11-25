import { cpSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { SHIPPED_MIGRATIONS } from '../fixture-migrations/fixture-migrations.constants.ts'
import { shippedMigrationNames, writeMigrations } from '../fixture-migrations/fixture-migrations.ts'
import { runCli } from '../run-cli/run-cli.ts'
import { tempDir } from '../temp-dir/temp-dir.ts'
import { SEED_NAME, SEEDS, TIMESTAMP_LENGTH } from './upgrades.constants.ts'
import type { UpgradeCli } from './upgrades.types.ts'

export function shippedMigration(suffix: string): string {
  const name = shippedMigrationNames().find((shipped) => shipped.endsWith(`_${suffix}`))
  if (name === undefined) throw new Error(`no shipped migration ends with _${suffix}`)
  return name
}

function migrationsFolder(names: string[], seed: Record<string, string>): string {
  const dir = tempDir('quaestor-upgrade-migrations-')
  for (const name of names)
    cpSync(join(SHIPPED_MIGRATIONS, name), join(dir, name), { recursive: true })
  return writeMigrations(dir, seed)
}

export function upgradeCli(seedFile: string, underTest: string): UpgradeCli {
  const earlier = shippedMigrationNames().filter((name) => name < underTest)
  const seedName = `${underTest.slice(0, TIMESTAMP_LENGTH)}_${SEED_NAME}`
  const seed = { [seedName]: readFileSync(join(SEEDS, seedFile), 'utf8') }
  const dataDir = tempDir('quaestor-upgrade-')
  const runIn = (migrationsDir: string) => (argv: string[]) =>
    runCli(argv, { dataDir, defaultEnv: 'test', migrationsDir })
  return {
    before: runIn(migrationsFolder(earlier, seed)),
    after: runIn(migrationsFolder([...earlier, underTest], seed)),
  }
}

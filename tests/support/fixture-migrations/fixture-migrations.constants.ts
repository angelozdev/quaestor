import { join } from 'node:path'
import { REPO_ROOT } from '#shell/cli'

export const SHIPPED_MIGRATIONS = join(REPO_ROOT, 'migrations')

export const MIGRATION_FILE = 'migration.sql'

export const FIXTURE_MIGRATIONS = {
  '20261123000000_first': 'CREATE TABLE fixture_a (id integer primary key);',
  '20261123000100_second': 'CREATE TABLE fixture_b (id integer primary key);',
}

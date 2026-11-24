import { DatabaseSync } from 'node:sqlite'
import { openStore, type Store } from '#shell/db'
import { SHIPPED_MIGRATIONS } from '../fixture-migrations/fixture-migrations.constants.ts'
import type { Row } from './store.types.ts'

export function openTestStore(
  path: string,
  migrationsDir: string = SHIPPED_MIGRATIONS,
): Promise<Store> {
  return openStore({
    path,
    migrationsDir,
    beforeMigrating: () => Promise.resolve(),
    onMigrated: () => {},
  })
}

export function runSql(path: string, sql: string): void {
  const db = new DatabaseSync(path)
  try {
    db.exec(sql)
  } finally {
    db.close()
  }
}

export function selectAll(path: string, sql: string): Row[] {
  const db = new DatabaseSync(path, { readOnly: true })
  try {
    return db.prepare(sql).all()
  } finally {
    db.close()
  }
}

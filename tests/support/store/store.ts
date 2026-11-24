import { DatabaseSync } from 'node:sqlite'
import type { Row } from './store.types.ts'

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

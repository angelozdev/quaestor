import { isNull } from 'drizzle-orm'
import { AlreadyExistsError } from '#core/ledger'
import { database, isPrimaryKeyViolation } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { tags } from './tags.schema.ts'

export function listTags(store: Store): string[] {
  return database(store)
    .select({ name: tags.name })
    .from(tags)
    .where(isNull(tags.deletedAt))
    .orderBy(tags.name)
    .all()
    .map(({ name }) => name)
}

export function insertTag(store: Store, name: string, now: Date): string {
  const instant = now.toISOString()
  try {
    database(store).insert(tags).values({ name, createdAt: instant, updatedAt: instant }).run()
    return name
  } catch (error) {
    if (isPrimaryKeyViolation(error)) throw new AlreadyExistsError('tag', name)
    throw error
  }
}

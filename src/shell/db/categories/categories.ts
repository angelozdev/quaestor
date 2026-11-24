import { isNull } from 'drizzle-orm'
import { AlreadyExistsError, type Category, type CategoryDraft, type WriteDeps } from '#core/ledger'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { categories } from './categories.schema.ts'

const STORED_FIELDS = {
  id: categories.id,
  emoji: categories.emoji,
  name: categories.name,
  archived: categories.archived,
}

export function listCategories(store: Store): Category[] {
  return database(store)
    .select(STORED_FIELDS)
    .from(categories)
    .where(isNull(categories.deletedAt))
    .orderBy(categories.name)
    .all()
}

export function insertCategory(
  store: Store,
  draft: CategoryDraft,
  { randomIndex, now }: WriteDeps,
): Category {
  const instant = now.toISOString()
  try {
    return withFreshCode(randomIndex, (id) =>
      database(store)
        .insert(categories)
        .values({ ...draft, id, createdAt: instant, updatedAt: instant })
        .returning(STORED_FIELDS)
        .get(),
    )
  } catch (error) {
    if (isUniqueViolation(error)) throw new AlreadyExistsError('category', draft.name)
    throw error
  }
}

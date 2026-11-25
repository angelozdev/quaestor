import { and, eq, isNull } from 'drizzle-orm'
import {
  AlreadyExistsError,
  NotFoundError,
  type Category,
  type CategoryDraft,
  type WriteDeps,
} from '#core/ledger'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { liveGroup } from '../groups/groups.ts'
import { categories } from './categories.schema.ts'

const STORED_FIELDS = {
  id: categories.id,
  group: categories.group,
  emoji: categories.emoji,
  name: categories.name,
  archived: categories.archived,
}

export function listCategories(store: Store): Category[] {
  return database(store)
    .select(STORED_FIELDS)
    .from(categories)
    .where(isNull(categories.deletedAt))
    .orderBy(categories.name, categories.id)
    .all()
}

export function insertCategory(
  store: Store,
  draft: CategoryDraft,
  { randomIndex, now }: WriteDeps,
): Category {
  const instant = now.toISOString()
  liveGroup(store, draft.group)
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

export function archiveCategory(store: Store, id: string, now: Date): Category {
  const instant = now.toISOString()
  const live = and(eq(categories.id, id), isNull(categories.deletedAt))
  const db = database(store)
  const category = db.select(STORED_FIELDS).from(categories).where(live).get()
  if (category === undefined) throw new NotFoundError('category', id)
  if (category.archived) return category
  return db
    .update(categories)
    .set({ archived: true, updatedAt: instant })
    .where(live)
    .returning(STORED_FIELDS)
    .get()!
}

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

function liveCategory(store: Store, id: string): Category {
  const category = database(store)
    .select(STORED_FIELDS)
    .from(categories)
    .where(and(eq(categories.id, id), isNull(categories.deletedAt)))
    .get()
  if (category === undefined) throw new NotFoundError('category', id)
  return category
}

function updateCategory(
  store: Store,
  id: string,
  change: { archived?: boolean; group?: string },
  now: Date,
): Category {
  return database(store)
    .update(categories)
    .set({ ...change, updatedAt: now.toISOString() })
    .where(eq(categories.id, id))
    .returning(STORED_FIELDS)
    .get()!
}

export function archiveCategory(store: Store, id: string, now: Date): Category {
  const category = liveCategory(store, id)
  return category.archived ? category : updateCategory(store, id, { archived: true }, now)
}

export function setCategoryGroup(store: Store, id: string, group: string, now: Date): Category {
  liveCategory(store, id)
  liveGroup(store, group)
  return updateCategory(store, id, { group }, now)
}

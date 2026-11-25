import { and, eq, isNull } from 'drizzle-orm'
import {
  AlreadyExistsError,
  GROUP_KINDS,
  NotFoundError,
  type Group,
  type GroupDraft,
  type WriteDeps,
} from '#core/ledger'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { groups } from './groups.schema.ts'

const STORED_FIELDS = {
  id: groups.id,
  kind: groups.kind,
  emoji: groups.emoji,
  name: groups.name,
}

export function listGroups(store: Store): Group[] {
  return database(store)
    .select(STORED_FIELDS)
    .from(groups)
    .where(isNull(groups.deletedAt))
    .orderBy(groups.name, groups.id)
    .all()
    .toSorted((a, b) => GROUP_KINDS.indexOf(a.kind) - GROUP_KINDS.indexOf(b.kind))
}

export function liveGroup(store: Store, id: string): Group {
  const group = database(store)
    .select(STORED_FIELDS)
    .from(groups)
    .where(and(eq(groups.id, id), isNull(groups.deletedAt)))
    .get()
  if (group === undefined) throw new NotFoundError('group', id)
  return group
}

export function insertGroup(
  store: Store,
  draft: GroupDraft,
  { randomIndex, now }: WriteDeps,
): Group {
  const instant = now.toISOString()
  try {
    return withFreshCode(randomIndex, (id) =>
      database(store)
        .insert(groups)
        .values({ ...draft, id, createdAt: instant, updatedAt: instant })
        .returning(STORED_FIELDS)
        .get(),
    )
  } catch (error) {
    if (isUniqueViolation(error)) throw new AlreadyExistsError('group', draft.name)
    throw error
  }
}

export function updateGroup(
  store: Store,
  id: string,
  change: { name?: string; emoji?: string },
  now: Date,
): Group {
  liveGroup(store, id)
  try {
    return database(store)
      .update(groups)
      .set({ ...change, updatedAt: now.toISOString() })
      .where(eq(groups.id, id))
      .returning(STORED_FIELDS)
      .get()!
  } catch (error) {
    if (isUniqueViolation(error)) throw new AlreadyExistsError('group', change.name ?? '')
    throw error
  }
}

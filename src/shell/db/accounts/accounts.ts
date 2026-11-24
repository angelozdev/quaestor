import { isNull } from 'drizzle-orm'
import {
  AlreadyExistsError,
  amountOf,
  type AccountDraft,
  type AccountRow,
  type WriteDeps,
} from '#core/ledger'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { accounts } from './accounts.schema.ts'

const STORED_FIELDS = {
  id: accounts.id,
  emoji: accounts.emoji,
  name: accounts.name,
  type: accounts.type,
  currency: accounts.currency,
  archived: accounts.archived,
  openingAmount: accounts.openingAmount,
  openingDate: accounts.openingDate,
}

function rowOf(stored: Omit<AccountRow, 'balance'>): AccountRow {
  const amount = amountOf(stored.openingAmount)
  return { ...stored, openingAmount: amount, balance: amount }
}

export function listAccounts(store: Store): AccountRow[] {
  return database(store)
    .select(STORED_FIELDS)
    .from(accounts)
    .where(isNull(accounts.deletedAt))
    .orderBy(accounts.name)
    .all()
    .map(rowOf)
}

export function insertAccount(
  store: Store,
  draft: AccountDraft,
  { randomIndex, now }: WriteDeps,
): AccountRow {
  const instant = now.toISOString()
  try {
    return withFreshCode(randomIndex, (id) =>
      rowOf(
        database(store)
          .insert(accounts)
          .values({ ...draft, id, createdAt: instant, updatedAt: instant })
          .returning(STORED_FIELDS)
          .get(),
      ),
    )
  } catch (error) {
    if (isUniqueViolation(error)) throw new AlreadyExistsError('account', draft.name)
    throw error
  }
}

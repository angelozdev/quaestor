import { isNull } from 'drizzle-orm'
import type { AccountRow } from '#core/ledger'
import { database } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { accounts } from './accounts.schema.ts'

export function listAccounts(store: Store): AccountRow[] {
  return database(store)
    .select({
      id: accounts.id,
      emoji: accounts.emoji,
      name: accounts.name,
      type: accounts.type,
      currency: accounts.currency,
      archived: accounts.archived,
      openingAmount: accounts.openingAmount,
      openingDate: accounts.openingDate,
      balance: accounts.openingAmount,
    })
    .from(accounts)
    .where(isNull(accounts.deletedAt))
    .orderBy(accounts.name)
    .all()
}

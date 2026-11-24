import { amountOf } from '#core/ledger'
import type { Ledger } from '#core/legacy'
import { accounts } from '../accounts/accounts.schema.ts'
import { balancesInCents } from '../accounts/accounts.ts'
import { categories } from '../categories/categories.schema.ts'
import { database } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { movementTags, movements } from '../movements/movements.schema.ts'
import { tags } from '../tags/tags.schema.ts'
import { AlreadyImportedError, BalanceMismatchError } from './legacy-import.errors.ts'
import type { ImportCounts } from './legacy-import.types.ts'

function checkBalances(store: Store, expected: Map<string, number>): void {
  const actual = balancesInCents(store)
  for (const [account, cents] of expected)
    if (actual.get(account) !== cents)
      throw new BalanceMismatchError(account, amountOf(cents), amountOf(actual.get(account) ?? 0))
}

export function importLedger(
  store: Store,
  ledger: Ledger,
  expected: Map<string, number>,
  now: Date,
): ImportCounts {
  const db = database(store)
  if (db.select({ id: accounts.id }).from(accounts).limit(1).get() !== undefined)
    throw new AlreadyImportedError()
  const instant = now.toISOString()
  for (const account of ledger.accounts)
    db.insert(accounts)
      .values({ ...account, createdAt: instant, updatedAt: instant })
      .run()
  for (const category of ledger.categories)
    db.insert(categories)
      .values({ ...category, createdAt: instant, updatedAt: instant })
      .run()
  for (const name of ledger.tags)
    db.insert(tags).values({ name, createdAt: instant, updatedAt: instant }).run()
  for (const { account, category, createdAt, ...movement } of ledger.movements)
    db.insert(movements)
      .values({
        ...movement,
        accountId: account,
        categoryId: category,
        createdAt,
        updatedAt: createdAt,
      })
      .run()
  for (const { movement, tag } of ledger.tagLinks)
    db.insert(movementTags).values({ movementId: ledger.movements[movement].id, tag }).run()
  checkBalances(store, expected)
  return {
    accounts: ledger.accounts.length,
    categories: ledger.categories.length,
    tags: ledger.tags.length,
    movements: ledger.movements.length,
    tagLinks: ledger.tagLinks.length,
  }
}

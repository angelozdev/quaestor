import {
  RefusedWriteError,
  amountOf,
  checkWrite,
  type AccountRow,
  type Catalog,
  type MovementDraft,
  type WriteDeps,
  type WriteRequest,
} from '#core/ledger'
import { listAccounts } from '../accounts/accounts.ts'
import { listCategories } from '../categories/categories.ts'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { listTags } from '../tags/tags.ts'
import { TAG_SEPARATOR } from './movements.constants.ts'
import { movementTags, movements } from './movements.schema.ts'
import type { BalanceChange, MovementRow, WriteResult } from './movements.types.ts'

function loadCatalog(store: Store): Catalog {
  return {
    accounts: new Map(listAccounts(store).map((account) => [account.id, account])),
    categories: new Map(listCategories(store).map((category) => [category.id, category])),
    tags: new Set(listTags(store)),
    movements: new Set(),
  }
}

function insertMovement(
  store: Store,
  draft: MovementDraft,
  { randomIndex, now }: WriteDeps,
): MovementRow {
  const instant = now.toISOString()
  const id = withFreshCode(
    randomIndex,
    (code) => {
      database(store)
        .insert(movements)
        .values({
          id: code,
          accountId: draft.account,
          date: draft.date,
          payee: draft.payee,
          amount: draft.amount,
          categoryId: draft.category,
          note: draft.note,
          createdAt: instant,
          updatedAt: instant,
        })
        .run()
      return code
    },
    isUniqueViolation,
  )
  if (draft.tags.length > 0)
    database(store)
      .insert(movementTags)
      .values(draft.tags.map((tag) => ({ movementId: id, tag })))
      .run()
  return {
    id,
    date: draft.date,
    account: draft.account,
    payee: draft.payee,
    amount: amountOf(draft.amount),
    currency: draft.currency,
    category: draft.category,
    tags: draft.tags.join(TAG_SEPARATOR),
    note: draft.note,
    transfer: null,
  }
}

function touchedAccounts(store: Store, ids: Set<string>): AccountRow[] {
  return listAccounts(store)
    .filter(({ id }) => ids.has(id))
    .toSorted((a, b) => (a.id < b.id ? -1 : 1))
}

function changesBetween(before: AccountRow[], after: AccountRow[]): BalanceChange[] {
  return before.map(({ id, currency, balance }, index) => ({
    account: id,
    currency,
    before: balance,
    after: after[index].balance,
  }))
}

export function writeMovements(store: Store, request: WriteRequest, deps: WriteDeps): WriteResult {
  const problems = checkWrite(request, loadCatalog(store))
  if (problems.length > 0) throw new RefusedWriteError(problems)
  const touched = new Set(request.movements.map(({ account }) => account))
  const before = touchedAccounts(store, touched)
  const recorded = request.movements.map((draft) => insertMovement(store, draft, deps))
  return {
    deleted: [],
    recorded,
    balances: changesBetween(before, touchedAccounts(store, touched)),
  }
}

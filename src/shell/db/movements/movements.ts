import { and, desc, eq, gte, isNull, lte, sql } from 'drizzle-orm'
import {
  RefusedWriteError,
  amountOf,
  checkWrite,
  matchesPayee,
  type AccountRow,
  type Catalog,
  type MovementDraft,
  type WriteDeps,
  type WriteRequest,
} from '#core/ledger'
import { listAccounts } from '../accounts/accounts.ts'
import { accounts } from '../accounts/accounts.schema.ts'
import { listCategories } from '../categories/categories.ts'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { listTags } from '../tags/tags.ts'
import { TAG_SEPARATOR } from './movements.constants.ts'
import { movementTags, movements } from './movements.schema.ts'
import type {
  BalanceChange,
  ListedMovement,
  MovementFilter,
  MovementRow,
  WriteResult,
} from './movements.types.ts'

const TAGS = sql<string>`coalesce((select group_concat(${movementTags.tag}, ${TAG_SEPARATOR} order by ${movementTags}.rowid) from ${movementTags} where ${movementTags.movementId} = ${movements.id}), '')`

function rowOf<T extends MovementRow>(stored: T): T {
  return { ...stored, amount: amountOf(stored.amount) }
}

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
  return rowOf({
    id,
    date: draft.date,
    account: draft.account,
    payee: draft.payee,
    amount: draft.amount,
    currency: draft.currency,
    category: draft.category,
    tags: draft.tags.join(TAG_SEPARATOR),
    note: draft.note,
    transfer: null,
  })
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

export function listMovements(store: Store, filter: MovementFilter): ListedMovement[] {
  const db = database(store)
  const sums = db
    .select({
      seq: movements.seq,
      sum: sql<number>`sum(${movements.amount}) over (partition by ${movements.accountId} order by ${movements.date}, ${movements.seq})`.as(
        'sum',
      ),
    })
    .from(movements)
    .where(isNull(movements.deletedAt))
    .as('sums')
  return db
    .select({
      id: movements.id,
      date: movements.date,
      account: movements.accountId,
      payee: movements.payee,
      amount: movements.amount,
      currency: accounts.currency,
      category: movements.categoryId,
      tags: TAGS,
      note: movements.note,
      transfer: movements.transfer,
      balance: sql<number>`${accounts.openingAmount} + ${sums.sum}`,
    })
    .from(movements)
    .innerJoin(accounts, eq(accounts.id, movements.accountId))
    .innerJoin(sums, eq(sums.seq, movements.seq))
    .where(
      and(
        isNull(movements.deletedAt),
        filter.account === undefined ? undefined : eq(movements.accountId, filter.account),
        filter.from === undefined ? undefined : gte(movements.date, filter.from),
        filter.to === undefined ? undefined : lte(movements.date, filter.to),
      ),
    )
    .orderBy(desc(movements.date), desc(movements.seq))
    .all()
    .filter(({ payee }) => filter.payee === undefined || matchesPayee(payee, filter.payee))
    .map(({ balance, ...stored }) => ({ ...rowOf(stored), balance: amountOf(balance) }))
}

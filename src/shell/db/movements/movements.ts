import {
  and,
  desc,
  eq,
  exists,
  gte,
  inArray,
  isNotNull,
  isNull,
  lte,
  ne,
  notExists,
  or,
  sql,
} from 'drizzle-orm'
import { alias } from 'drizzle-orm/sqlite-core'
import {
  NotFoundError,
  RefusedWriteError,
  amountOf,
  checkWrite,
  matchesPayee,
  type AccountRow,
  type Catalog,
  type HalfDraft,
  type TransferDraft,
  type WriteDeps,
  type WriteRequest,
} from '#core/ledger'
import type { CountedMovement } from '#core/report'
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
  CountedFilter,
  ListedMovement,
  MovementFilter,
  MovementRow,
  WriteResult,
} from './movements.types.ts'

const partner = alias(movements, 'partner')

const TAGS = sql<string>`coalesce((select group_concat(${movementTags.tag}, ${TAG_SEPARATOR} order by ${movementTags}.rowid) from ${movementTags} where ${movementTags.movementId} = ${movements.id}), '')`

const MOVEMENT_FIELDS = {
  id: movements.id,
  date: movements.date,
  account: movements.accountId,
  payee: movements.payee,
  amount: movements.amount,
  currency: accounts.currency,
  category: movements.categoryId,
  tags: TAGS,
  note: movements.note,
  transfer: partner.id,
}

const PARTNER_IS_LIVE = and(
  eq(partner.transfer, movements.transfer),
  ne(partner.id, movements.id),
  isNull(partner.deletedAt),
)

function rowOf<T extends MovementRow>(stored: T): T {
  return { ...stored, amount: amountOf(stored.amount) }
}

function deleteTargets(store: Store, codes: string[]): Map<string, string[]> {
  return new Map(
    database(store)
      .select({ id: movements.id, account: movements.accountId, partner: partner.accountId })
      .from(movements)
      .leftJoin(partner, PARTNER_IS_LIVE)
      .where(and(inArray(movements.id, codes), isNull(movements.deletedAt)))
      .all()
      .map(({ id, account, partner }) => [id, partner === null ? [account] : [account, partner]]),
  )
}

function loadCatalog(store: Store, request: WriteRequest): Catalog {
  return {
    accounts: new Map(listAccounts(store).map((account) => [account.id, account])),
    categories: new Map(listCategories(store).map((category) => [category.id, category])),
    tags: new Set(listTags(store)),
    movements: deleteTargets(store, request.delete),
  }
}

function insertMovement(
  store: Store,
  draft: HalfDraft & { category: string | null },
  { randomIndex, now }: WriteDeps,
  transfer: string | null = null,
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
          transfer,
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
    transfer,
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

function insertTransfer(store: Store, { from, to }: TransferDraft, deps: WriteDeps): MovementRow[] {
  const key = crypto.randomUUID()
  const leaving = insertMovement(store, { ...from, category: null }, deps, key)
  const arriving = insertMovement(store, { ...to, category: null }, deps, key)
  return [
    { ...leaving, transfer: arriving.id },
    { ...arriving, transfer: leaving.id },
  ]
}

function movementsToDelete(store: Store, codes: string[]): MovementRow[] {
  const db = database(store)
  const named = db
    .select({ transfer: movements.transfer })
    .from(movements)
    .where(inArray(movements.id, codes))
  return db
    .select(MOVEMENT_FIELDS)
    .from(movements)
    .innerJoin(accounts, eq(accounts.id, movements.accountId))
    .leftJoin(partner, PARTNER_IS_LIVE)
    .where(
      and(
        isNull(movements.deletedAt),
        or(inArray(movements.id, codes), inArray(movements.transfer, named)),
      ),
    )
    .orderBy(movements.date, movements.seq)
    .all()
    .map(rowOf)
}

function markDeleted(store: Store, rows: MovementRow[], { now }: WriteDeps): void {
  const instant = now.toISOString()
  database(store)
    .update(movements)
    .set({ deletedAt: instant, updatedAt: instant })
    .where(
      inArray(
        movements.id,
        rows.map(({ id }) => id),
      ),
    )
    .run()
}

export function writeMovements(store: Store, request: WriteRequest, deps: WriteDeps): WriteResult {
  const problems = checkWrite(request, loadCatalog(store, request))
  if (problems.length > 0) throw new RefusedWriteError(problems)
  const deleted = movementsToDelete(store, request.delete)
  const touched = new Set([
    ...deleted.map(({ account }) => account),
    ...request.movements.map(({ account }) => account),
    ...request.transfers.flatMap(({ from, to }) => [from.account, to.account]),
  ])
  const before = touchedAccounts(store, touched)
  markDeleted(store, deleted, deps)
  const recorded = [
    ...request.movements.map((draft) => insertMovement(store, draft, deps)),
    ...request.transfers.flatMap((draft) => insertTransfer(store, draft, deps)),
  ]
  return {
    deleted,
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
      ...MOVEMENT_FIELDS,
      balance: sql<number>`${accounts.openingAmount} + ${sums.sum}`,
    })
    .from(movements)
    .innerJoin(accounts, eq(accounts.id, movements.accountId))
    .innerJoin(sums, eq(sums.seq, movements.seq))
    .leftJoin(partner, PARTNER_IS_LIVE)
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

function taggedWith(store: Store, tag: string) {
  return database(store)
    .select({ tag: movementTags.tag })
    .from(movementTags)
    .where(and(eq(movementTags.movementId, movements.id), eq(movementTags.tag, tag)))
}

function refuseUnknownTags(store: Store, tags: (string | undefined)[]): void {
  const known = new Set(listTags(store))
  for (const tag of tags)
    if (tag !== undefined && !known.has(tag)) throw new NotFoundError('tag', tag)
}

export function countedMovements(store: Store, filter: CountedFilter): CountedMovement[] {
  refuseUnknownTags(store, [filter.tag, filter.withoutTag])
  return database(store)
    .select({
      date: movements.date,
      cents: movements.amount,
      currency: accounts.currency,
      category: sql<string>`${movements.categoryId}`,
      payee: movements.payee,
    })
    .from(movements)
    .innerJoin(accounts, eq(accounts.id, movements.accountId))
    .where(
      and(
        isNull(movements.deletedAt),
        isNotNull(movements.categoryId),
        gte(movements.date, filter.from),
        lte(movements.date, filter.to),
        filter.tag === undefined ? undefined : exists(taggedWith(store, filter.tag)),
        filter.withoutTag === undefined
          ? undefined
          : notExists(taggedWith(store, filter.withoutTag)),
      ),
    )
    .orderBy(movements.date, movements.seq)
    .all()
    .filter(({ payee }) => filter.payee === undefined || matchesPayee(payee, filter.payee))
    .map(({ payee: _payee, ...counted }) => counted)
}

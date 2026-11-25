import { eq, isNull, sql } from 'drizzle-orm'
import {
  AlreadyExistsError,
  BalanceNotZeroError,
  NotFoundError,
  amountOf,
  type AccountDraft,
  type AccountRow,
  type WriteDeps,
} from '#core/ledger'
import { database, isUniqueViolation, withFreshCode } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { movements } from '../movements/movements.schema.ts'
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

const MOVEMENT_TOTAL = sql<number>`coalesce((select sum(${movements.amount}) from ${movements} where ${movements.accountId} = ${accounts.id} and ${movements.deletedAt} is null), 0)`

function rowOf(stored: Omit<AccountRow, 'balance'>, movementTotal: number): AccountRow {
  return {
    ...stored,
    openingAmount: amountOf(stored.openingAmount),
    balance: amountOf(stored.openingAmount + movementTotal),
  }
}

export function listAccounts(store: Store): AccountRow[] {
  return database(store)
    .select({ ...STORED_FIELDS, movementTotal: MOVEMENT_TOTAL })
    .from(accounts)
    .where(isNull(accounts.deletedAt))
    .orderBy(accounts.name)
    .all()
    .map(({ movementTotal, ...stored }) => rowOf(stored, movementTotal))
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
        0,
      ),
    )
  } catch (error) {
    if (isUniqueViolation(error)) throw new AlreadyExistsError('account', draft.name)
    throw error
  }
}

function liveAccount(store: Store, id: string): AccountRow {
  const account = listAccounts(store).find((row) => row.id === id)
  if (account === undefined) throw new NotFoundError('account', id)
  return account
}

function setArchived(store: Store, account: AccountRow, archived: boolean, now: Date): AccountRow {
  database(store)
    .update(accounts)
    .set({ archived, updatedAt: now.toISOString() })
    .where(eq(accounts.id, account.id))
    .run()
  return { ...account, archived }
}

export function archiveAccount(store: Store, id: string, now: Date): AccountRow {
  const account = liveAccount(store, id)
  if (account.archived) return account
  if (account.balance !== 0)
    throw new BalanceNotZeroError(account.id, account.currency, account.balance)
  return setArchived(store, account, true, now)
}

export function unarchiveAccount(store: Store, id: string, now: Date): AccountRow {
  const account = liveAccount(store, id)
  return account.archived ? setArchived(store, account, false, now) : account
}

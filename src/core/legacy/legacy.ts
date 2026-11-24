import { drawCode, type Account, type RandomIndex } from '#core/ledger'
import {
  INCOME,
  MILLISECOND_DIGITS,
  MONEY_IN,
  NAME_PATTERN,
  POSTED,
  TRANSFER,
  UTC,
} from './legacy.constants.ts'
import type { LegacyExport, LegacyTransaction, Ledger, StoredMovement } from './legacy.types.ts'

type Opening = Pick<Account, 'openingAmount' | 'openingDate'>

function byId(a: { id: number }, b: { id: number }): number {
  return a.id - b.id
}

function inLegacyOrder<T extends { id: number }>(rows: T[]): T[] {
  return rows.toSorted(byId)
}

function codesOf(rows: { id: number }[], randomIndex: RandomIndex): Map<number, string> {
  const codes = new Set<string>()
  while (codes.size < rows.length) codes.add(drawCode(randomIndex))
  const drawn = [...codes]
  return new Map(rows.map(({ id }, index) => [id, drawn[index]]))
}

function emojiAndName(text: string): { emoji: string | null; name: string } {
  const match = NAME_PATTERN.exec(text)
  return match ? { emoji: match[1], name: match[2] } : { emoji: null, name: text }
}

function signedAmount({ type, direction, amount }: LegacyTransaction): number {
  return type === INCOME || direction === MONEY_IN ? amount : 0 - amount
}

function instantOf(createdAt: string): string {
  const [seconds = '', fraction = ''] = createdAt.split('.')
  return `${seconds}.${fraction.padEnd(MILLISECOND_DIGITS, '0').slice(0, MILLISECOND_DIGITS)}Z`
}

function dayBefore(date: string): string {
  return Temporal.PlainDate.from(date).subtract({ days: 1 }).toString()
}

function dayOf(exportedAt: string): string {
  return Temporal.Instant.from(exportedAt).toZonedDateTimeISO(UTC).toPlainDate().toString()
}

function openingOf(balance: number, movements: StoredMovement[], exportedAt: string): Opening {
  const difference = movements.reduce((rest, { amount }) => rest - amount, balance)
  if (difference === 0) return { openingAmount: 0, openingDate: null }
  const [first] = movements.map(({ date }) => date).toSorted()
  return {
    openingAmount: difference,
    openingDate: first === undefined ? dayOf(exportedAt) : dayBefore(first),
  }
}

export function ledgerFrom(legacy: LegacyExport, randomIndex: RandomIndex): Ledger {
  const accounts = inLegacyOrder(legacy.accounts)
  const categories = inLegacyOrder(legacy.categories)
  const posted = inLegacyOrder(legacy.transactions.filter(({ status }) => status === POSTED))
  const accountCodes = codesOf(accounts, randomIndex)
  const categoryCodes = codesOf(categories, randomIndex)
  const movementCodes = codesOf(posted, randomIndex)
  const movements = posted.map((transaction): StoredMovement => {
    const isTransfer = transaction.type === TRANSFER
    return {
      id: movementCodes.get(transaction.id)!,
      account: accountCodes.get(transaction.accountId)!,
      date: transaction.date,
      payee: transaction.payee,
      amount: signedAmount(transaction),
      category:
        isTransfer || transaction.categoryId === null
          ? null
          : categoryCodes.get(transaction.categoryId)!,
      transfer: isTransfer ? transaction.transferGroup : null,
      note: transaction.notes,
      createdAt: instantOf(transaction.createdAt),
    }
  })
  const byAccount = Object.groupBy(movements, ({ account }) => account)
  const movementIndexes = new Map(posted.map(({ id }, index) => [id, index]))
  const tagNames = new Map(legacy.tags.map(({ id, name }) => [id, name]))
  return {
    accounts: accounts.map(({ id, name, type, currency, archived }) => {
      const code = accountCodes.get(id)!
      return {
        id: code,
        ...emojiAndName(name),
        type,
        currency,
        archived,
        ...openingOf(legacy.balances.get(id)!, byAccount[code] ?? [], legacy.exportedAt),
      }
    }),
    categories: categories.map(({ id, name, archived }) => ({
      id: categoryCodes.get(id)!,
      ...emojiAndName(name),
      archived,
    })),
    tags: inLegacyOrder(legacy.tags).map(({ name }) => name),
    movements,
    tagLinks: legacy.tagLinks
      .toSorted((a, b) => a.transactionId - b.transactionId || a.tagId - b.tagId)
      .flatMap(({ transactionId, tagId }) => {
        const movement = movementIndexes.get(transactionId)
        return movement === undefined ? [] : [{ movement, tag: tagNames.get(tagId)! }]
      }),
  }
}

export function expectedBalances(legacy: LegacyExport, ledger: Ledger): Map<string, number> {
  const accounts = inLegacyOrder(legacy.accounts)
  return new Map(
    ledger.accounts.map(({ id }, index) => [id, legacy.balances.get(accounts[index].id)!]),
  )
}

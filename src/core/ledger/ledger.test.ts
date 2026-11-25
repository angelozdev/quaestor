import { describe, expect, it } from 'vitest'
import { checkWrite, type Account, type Catalog, type Category } from '#core/ledger'

function account(id: string, currency: string, extra: Partial<Account> = {}): Account {
  return {
    id,
    emoji: '🏦',
    name: id,
    type: 'debit',
    currency,
    archived: false,
    openingAmount: 0,
    openingDate: '2026-01-05',
    ...extra,
  }
}

function category(id: string, archived = false): Category {
  return { id, emoji: '🎁', name: id, archived }
}

function catalogOf(accounts: Account[], categories: Category[]): Catalog {
  return {
    accounts: new Map(accounts.map((row) => [row.id, row])),
    categories: new Map(categories.map((row) => [row.id, row])),
    tags: new Set(),
    movements: new Set(),
  }
}

function spending(account: string, category: string, extra: Record<string, unknown> = {}) {
  return {
    account,
    date: '2026-11-25',
    payee: 'Netflix',
    amount: -500000,
    currency: 'COP',
    category,
    tags: [],
    note: null,
    ...extra,
  }
}

function halfOf(account: string, currency: string, amount: number) {
  return { account, date: '2026-11-25', payee: 'Move', amount, currency, tags: [], note: null }
}

function archived(item: string, kind: string, id: string) {
  return { code: 'archived', item, message: `${kind} ${id} is archived` }
}

const NO_WRITES = { delete: [], movements: [], transfers: [] }

describe('checkWrite', () => {
  it('an archived account receives no new movement', () => {
    const catalog = catalogOf([account('card', 'COP', { archived: true })], [category('food')])

    const problems = checkWrite(
      {
        ...NO_WRITES,
        movements: [spending('card', 'food'), spending('card', 'food', { currency: 'USD' })],
      },
      catalog,
    )

    expect(problems).toEqual([
      archived('movements[0]', 'account', 'card'),
      archived('movements[1]', 'account', 'card'),
    ])
  })

  it('an archived account cannot be either half', () => {
    const catalog = catalogOf(
      [account('card', 'COP', { archived: true }), account('piggy', 'USD')],
      [],
    )

    const leaving = checkWrite(
      {
        ...NO_WRITES,
        transfers: [{ from: halfOf('card', 'COP', -10000), to: halfOf('piggy', 'USD', 100) }],
      },
      catalog,
    )
    const arriving = checkWrite(
      {
        ...NO_WRITES,
        transfers: [{ from: halfOf('piggy', 'USD', -100), to: halfOf('card', 'USD', 10000) }],
      },
      catalog,
    )

    expect(leaving).toEqual([archived('transfers[0].from', 'account', 'card')])
    expect(arriving).toEqual([archived('transfers[0].to', 'account', 'card')])
  })

  it('an archived category receives no new movement (archived account, archived category and an unknown tag, in that order)', () => {
    const catalog = catalogOf(
      [account('bank', 'COP'), account('card', 'COP', { archived: true })],
      [category('oldg', true), category('gift'), category('misc', true)],
    )

    const refusedOne = checkWrite({ ...NO_WRITES, movements: [spending('bank', 'oldg')] }, catalog)
    const refusedInOrder = checkWrite(
      { ...NO_WRITES, movements: [spending('card', 'misc', { tags: ['trip:nowhere'] })] },
      catalog,
    )
    const accepted = checkWrite({ ...NO_WRITES, movements: [spending('bank', 'gift')] }, catalog)

    expect(refusedOne).toEqual([archived('movements[0]', 'category', 'oldg')])
    expect(refusedInOrder).toEqual([
      archived('movements[0]', 'account', 'card'),
      archived('movements[0]', 'category', 'misc'),
      { code: 'not_found', item: 'movements[0]', message: 'tag trip:nowhere does not exist' },
    ])
    expect(accepted).toEqual([])
  })

  it('an account without an opening date accepts a movement on any date', () => {
    const catalog = catalogOf([account('bank', 'COP', { openingDate: null })], [category('food')])

    const problems = checkWrite(
      { ...NO_WRITES, movements: [spending('bank', 'food', { date: '1999-01-01' })] },
      catalog,
    )

    expect(problems).toEqual([])
  })

  it('an archived account is refused as archived only, even before its opening date', () => {
    const catalog = catalogOf(
      [account('bank', 'COP', { archived: true, openingDate: '2026-11-19' })],
      [category('pay')],
    )

    const problems = checkWrite(
      {
        ...NO_WRITES,
        movements: [spending('bank', 'pay', { date: '2026-11-01', currency: 'USD' })],
      },
      catalog,
    )

    expect(problems).toEqual([archived('movements[0]', 'account', 'bank')])
  })
})

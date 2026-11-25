import { decode } from '@toon-format/toon'
import { amountTextOf } from '../arbitraries/arbitraries.ts'
import type { Booked, Moved } from '../arbitraries/arbitraries.types.ts'
import { ledgerCli } from '../ledger/ledger.ts'
import type { LedgerCli } from '../ledger/ledger.types.ts'
import { CURRENCIES, DAY, OPENING_DATE } from './books.constants.ts'
import type { Books, Json, Mover, Spender, Transfer } from './books.types.ts'

async function added(cli: LedgerCli, argv: string[], kind: string): Promise<string> {
  const { stdout } = await cli.run(argv)
  return (decode(stdout) as Record<string, { id: string }>)[kind]!.id
}

export function addAccount(cli: LedgerCli, name: string, currency: string, opening: string) {
  const flags = { emoji: '🏦', type: 'debit', currency, opening, 'opening-date': OPENING_DATE }
  const argv = Object.entries(flags).flatMap(([flag, value]) => [`--${flag}`, value])
  return added(cli, ['account', 'add', name, ...argv], 'account')
}

async function groupId(cli: LedgerCli, name: string): Promise<string> {
  const { stdout } = await cli.run(['group', 'list'])
  const { groups } = decode(stdout) as { groups: { id: string; name: string }[] }
  const group = groups.find((row) => row.name === name)
  if (group === undefined) throw new Error(`no group named ${name}`)
  return group.id
}

export async function addCategory(
  cli: LedgerCli,
  name = 'Food',
  group = 'Food & Dining',
  emoji = '🍽️',
) {
  const argv = ['category', 'add', name, '--emoji', emoji, '--group', await groupId(cli, group)]
  return added(cli, argv, 'category')
}

export async function openBooks(cli = ledgerCli()): Promise<Books> {
  return {
    cli,
    wallet: await addAccount(cli, 'Wallet', 'USD', '120.50'),
    savings: await addAccount(cli, 'Savings', 'USD', '0'),
    bank: await addAccount(cli, 'Bank', 'COP', '1000000'),
    food: await addCategory(cli),
  }
}

export function write(cli: LedgerCli, body: unknown, ...flags: string[]) {
  const stdin = typeof body === 'string' ? body : JSON.stringify(body)
  return cli.run(['movement', 'write', ...flags], stdin)
}

export function spend(books: Spender, extra: Json = {}): Json {
  return {
    account: books.wallet,
    date: DAY,
    payee: 'Uber',
    amount: '-12.50',
    currency: 'USD',
    category: books.food,
    ...extra,
  }
}

export function bookedMovements(books: Books, items: Booked[]): Json[] {
  const accounts = { wallet: books.wallet, savings: books.savings }
  return items.map(({ account, cents, date }) =>
    spend(books, { account: accounts[account], amount: amountTextOf(cents), date }),
  )
}

export function transfer(books: Mover, from: Json = {}, to: Json = {}): Transfer {
  return {
    from: {
      account: books.wallet,
      date: DAY,
      payee: 'To Savings',
      amount: '-10',
      currency: 'USD',
      ...from,
    },
    to: {
      account: books.savings,
      date: DAY,
      payee: 'From Wallet',
      amount: '10',
      currency: 'USD',
      ...to,
    },
  }
}

export function movedTransfers(books: Books, items: Moved[]): Transfer[] {
  return items.map(({ from, to, sent, received, date }) =>
    transfer(
      books,
      { account: books[from], currency: CURRENCIES[from], amount: amountTextOf(-sent), date },
      { account: books[to], currency: CURRENCIES[to], amount: amountTextOf(received), date },
    ),
  )
}

export function list(cli: LedgerCli, ...flags: string[]) {
  return cli.run(['movement', 'list', ...flags])
}

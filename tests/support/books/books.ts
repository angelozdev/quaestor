import { decode } from '@toon-format/toon'
import { amountTextOf } from '../arbitraries/arbitraries.ts'
import type { Booked } from '../arbitraries/arbitraries.types.ts'
import { ledgerCli } from '../ledger/ledger.ts'
import type { LedgerCli } from '../ledger/ledger.types.ts'
import { DAY, OPENING_DATE } from './books.constants.ts'
import type { Books, Json, Spender } from './books.types.ts'

async function added(cli: LedgerCli, argv: string[], kind: string): Promise<string> {
  const { stdout } = await cli.run(argv)
  return (decode(stdout) as Record<string, { id: string }>)[kind]!.id
}

export function addAccount(cli: LedgerCli, name: string, currency: string, opening: string) {
  const flags = { emoji: '🏦', type: 'debit', currency, opening, 'opening-date': OPENING_DATE }
  const argv = Object.entries(flags).flatMap(([flag, value]) => [`--${flag}`, value])
  return added(cli, ['account', 'add', name, ...argv], 'account')
}

export function addCategory(cli: LedgerCli, name = 'Food') {
  return added(cli, ['category', 'add', name, '--emoji', '🍽️'], 'category')
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

export function list(cli: LedgerCli, ...flags: string[]) {
  return cli.run(['movement', 'list', ...flags])
}

import { encode } from '@toon-format/toon'
import fc from 'fast-check'
import { addAccount, addCategory, write } from '../books/books.ts'
import type { Json } from '../books/books.types.ts'
import { ledgerCli } from '../ledger/ledger.ts'
import type { LedgerCli } from '../ledger/ledger.types.ts'
import { MAX_CENTS, MAX_MOVES, REPORT_CATEGORIES } from './reports.constants.ts'
import type { MixedMove, ReportBooks } from './reports.types.ts'

export async function reportBooks(cli = ledgerCli()): Promise<ReportBooks> {
  return {
    cli,
    bank: await addAccount(cli, 'Bank', 'COP', '1000000'),
    savings: await addAccount(cli, 'Savings', 'COP', '0'),
    wallet: await addAccount(cli, 'Wallet', 'USD', '0'),
    card: await addAccount(cli, 'Card', 'KRW', '0'),
    salary: await addCategory(cli, 'Salary', 'Income', '💼'),
    restaurants: await addCategory(cli, 'Restaurants', 'Food & Dining', '🍽️'),
    clothing: await addCategory(cli, 'Clothing', 'Shopping', '👕'),
    investment: await addCategory(cli, 'Investment', 'Transfers & Investments', '📈'),
  }
}

export function movement(
  account: string,
  category: string,
  date: string,
  amount: string,
  currency = 'COP',
): Json {
  return { account, category, date, amount, currency, payee: 'Payee' }
}

export function record(cli: LedgerCli, ...movements: Json[]) {
  return write(cli, { movements })
}

export function report(cli: LedgerCli, from: string, to: string, ...flags: string[]) {
  return cli.run(['report', '--from', from, '--to', to, ...flags])
}

export function withCodes(stdout: string, codes: Record<string, string>): string {
  return Object.entries(codes).reduce(
    (text, [name, code]) => text.replaceAll(encode(code), `<${name}>`),
    stdout,
  )
}

export function mixedMoves(months: { min: number; max: number }): fc.Arbitrary<MixedMove[]> {
  return fc.array(
    fc.record({
      usd: fc.boolean(),
      cents: fc.integer({ min: -MAX_CENTS, max: MAX_CENTS }).map((cents) => cents || 1),
      category: fc.constantFrom(...REPORT_CATEGORIES),
      month: fc.integer(months),
      day: fc.integer({ min: 1, max: 28 }),
    }),
    { minLength: 1, maxLength: MAX_MOVES },
  )
}

function twoDigits(value: number): string {
  return String(value).padStart(2, '0')
}

export function recordMixed(books: ReportBooks, moves: MixedMove[]) {
  return record(
    books.cli,
    ...moves.map(({ usd, cents, category, month, day }) =>
      movement(
        usd ? books.wallet : books.bank,
        books[category],
        `2026-${twoDigits(month)}-${twoDigits(day)}`,
        (cents / 100).toFixed(2),
        usd ? 'USD' : 'COP',
      ),
    ),
  )
}

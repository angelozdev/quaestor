import { decode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import { addAccount, addCategory, write } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { invalidInput } from '../../../../../tests/support/refusals/refusals.ts'
import {
  movement,
  record,
  report,
  reportBooks,
  withCodes,
} from '../../../../../tests/support/reports/reports.ts'
import type { Report } from '../../../../../tests/support/reports/reports.types.ts'

const OCTOBER = ['2026-10-01', '2026-10-31'] as const

function totalsOf(stdout: string): Record<string, number> {
  const { totals } = decode(stdout) as Report
  return Object.fromEntries(totals.map(({ line, total }) => [line, total]))
}

function recordedIds(stdout: string): string[] {
  return (decode(stdout) as { recorded: { id: string }[] }).recorded.map(({ id }) => id)
}

const EMPTY_OCTOBER = `from: 2026-10-01
to: 2026-10-31
currency: COP
rates: []
totals[4]{line,total}:
  income,0
  spending,0
  left,0
  outside,0
groups: []
categories: []
`

describe('quaestor report', () => {
  it('a month gives income, spending, what is left and the outside line, by group and category', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.salary, '2026-10-31', '5000000'),
      movement(books.bank, books.restaurants, '2026-10-03', '-300000'),
      movement(books.bank, books.restaurants, '2026-10-20', '50000'),
    )

    const run = await report(books.cli, ...OCTOBER)

    expect(run.code).toBe(0)
    expect(run.stderr).toBe('env: test\n')
    expect(withCodes(run.stdout, { salary: books.salary, restaurants: books.restaurants }))
      .toBe(`from: 2026-10-01
to: 2026-10-31
currency: COP
rates: []
totals[4]{line,total}:
  income,5000000
  spending,250000
  left,4750000
  outside,0
groups[2]{id,kind,emoji,name,total}:
  m0z7,income,💰,Income,5000000
  1aae,spending,🍽️,Food & Dining,250000
categories[2]{id,group,emoji,name,total}:
  <salary>,m0z7,💼,Salary,5000000
  <restaurants>,1aae,🍽️,Restaurants,250000
`)
  })

  it('a refund in a later month lowers that month: +200,000 in October, -200,000 in November', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.clothing, '2026-10-28', '-200000'),
      movement(books.bank, books.clothing, '2026-11-03', '200000'),
    )

    const october = decode((await report(books.cli, ...OCTOBER)).stdout) as Report
    const november = decode((await report(books.cli, '2026-11-01', '2026-11-30')).stdout) as Report

    expect(october.categories).toMatchObject([{ name: 'Clothing', total: 200000 }])
    expect(october.totals).toContainEqual({ line: 'spending', total: 200000 })
    expect(november.categories).toMatchObject([{ name: 'Clothing', total: -200000 }])
    expect(november.groups).toMatchObject([{ id: 'q3rh', total: -200000 }])
    expect(november.totals).toEqual([
      { line: 'income', total: 0 },
      { line: 'spending', total: -200000 },
      { line: 'left', total: 200000 },
      { line: 'outside', total: 0 },
    ])
  })

  it('a transfer is never spending or income', async () => {
    const books = await reportBooks()
    await record(books.cli, movement(books.bank, books.restaurants, '2026-10-03', '-300000'))
    const before = await report(books.cli, ...OCTOBER)

    const moved = await write(books.cli, {
      transfers: [
        {
          from: {
            account: books.bank,
            date: '2026-10-05',
            payee: 'To Savings',
            amount: '-500000',
            currency: 'COP',
          },
          to: {
            account: books.savings,
            date: '2026-10-05',
            payee: 'From Bank',
            amount: '500000',
            currency: 'COP',
          },
        },
      ],
    })
    const after = await report(books.cli, ...OCTOBER)

    expect(before.code).toBe(0)
    expect(moved.code).toBe(0)
    expect(after).toEqual(before)
  })

  it('an opening balance is never spending or income', async () => {
    const books = await reportBooks()

    const run = await report(books.cli, '2026-01-01', '2026-01-31')

    expect(run.stdout).toBe(
      EMPTY_OCTOBER.replace('2026-10-01', '2026-01-01').replace('2026-10-31', '2026-01-31'),
    )
  })

  it("a change in an investment's value is outside the totals, with its sign", async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.restaurants, '2026-10-03', '-300000'),
      movement(books.bank, books.investment, '2026-10-31', '-4000000'),
    )

    const run = await report(books.cli, ...OCTOBER)

    expect(totalsOf(run.stdout)).toEqual({
      income: 0,
      spending: 300000,
      left: -300000,
      outside: -4000000,
    })
    expect((decode(run.stdout) as Report).groups).toContainEqual({
      id: '7hdg',
      kind: 'outside',
      emoji: '🔄',
      name: 'Transfers & Investments',
      total: -4000000,
    })
  })

  it('an income category with money out prints a negative income', async () => {
    const books = await reportBooks()
    await record(books.cli, movement(books.bank, books.salary, '2026-10-31', '-100000'))

    const run = await report(books.cli, ...OCTOBER)

    expect(run.code).toBe(0)
    expect(totalsOf(run.stdout)).toEqual({
      income: -100000,
      spending: 0,
      left: -100000,
      outside: 0,
    })
    expect((decode(run.stdout) as Report).categories).toMatchObject([
      { name: 'Salary', total: -100000 },
    ])
  })

  it('a period with no movement prints four totals at 0 and nothing else', async () => {
    const books = await reportBooks()

    const run = await report(books.cli, ...OCTOBER)

    expect(run).toEqual({ code: 0, stdout: EMPTY_OCTOBER, stderr: 'env: test\n' })
  })

  it('both days of the period count, and the days around them do not', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.restaurants, '2026-09-30', '-1000'),
      movement(books.bank, books.restaurants, '2026-10-01', '-20000'),
      movement(books.bank, books.restaurants, '2026-10-31', '-300000'),
      movement(books.bank, books.restaurants, '2026-11-01', '-4000000'),
    )

    const run = await report(books.cli, ...OCTOBER)

    expect(totalsOf(run.stdout).spending).toBe(320000)
  })

  it('a deleted movement never counts', async () => {
    const books = await reportBooks()
    const recorded = await record(
      books.cli,
      movement(books.bank, books.restaurants, '2026-10-03', '-300000'),
    )

    await write(books.cli, { delete: recordedIds(recorded.stdout) })
    const run = await report(books.cli, ...OCTOBER)

    expect(run.stdout).toBe(EMPTY_OCTOBER)
  })

  it('groups come by kind then name, and categories by group then name', async () => {
    const books = await reportBooks()
    const { cli, bank } = books
    const interest = await addCategory(cli, 'Interest', 'Income', '💰')
    const groceries = await addCategory(cli, 'Groceries', 'Food & Dining', '🛒')
    await record(
      cli,
      movement(bank, books.investment, '2026-10-02', '-1000'),
      movement(bank, books.clothing, '2026-10-03', '-2000'),
      movement(bank, books.restaurants, '2026-10-04', '-3000'),
      movement(bank, groceries, '2026-10-05', '-4000'),
      movement(bank, books.salary, '2026-10-06', '5000'),
      movement(bank, interest, '2026-10-07', '6000'),
    )
    await cli.run(['category', 'archive', books.restaurants])
    const second = await addCategory(cli, 'Restaurants', 'Food & Dining', '🍽️')
    await record(cli, movement(bank, second, '2026-10-08', '-7000'))

    const { groups, categories } = decode((await report(cli, ...OCTOBER)).stdout) as Report

    expect(groups.map(({ name }) => name)).toEqual([
      'Income',
      'Food & Dining',
      'Shopping',
      'Transfers & Investments',
    ])
    expect(categories.map(({ id }) => id)).toEqual([
      interest,
      books.salary,
      groceries,
      ...[books.restaurants, second].toSorted(),
      books.clothing,
      books.investment,
    ])
  })

  it('--to before --from is invalid_input', async () => {
    const run = await report(ledgerCli(), '2026-10-31', '2026-10-01')

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('to: must not be before from'),
    })
  })

  it('--from and --to are required', async () => {
    const run = await ledgerCli().run(['report'])

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('from: is required', 'to: is required'),
    })
  })

  it('a period with a foreign currency and no rate is refused as missing_rate', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.restaurants, '2026-10-03', '-10.85', 'USD'),
      movement(books.card, books.restaurants, '2026-10-04', '-15000', 'KRW'),
    )

    const run = await report(books.cli, ...OCTOBER)

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: `env: test
error:
  code: missing_rate
  currencies[2]: KRW,USD
  message: "no rate for KRW, USD; set one with quaestor rate set"
`,
    })
  })

  it('a total beyond 2^53 cents fails as unexpected instead of printing a rounded figure', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.restaurants, '2026-10-03', '-90071992547409.91'),
      movement(books.savings, books.restaurants, '2026-10-04', '-90071992547409.91'),
    )

    const run = await report(books.cli, ...OCTOBER)

    expect(run.code).toBe(2)
    expect(run.stdout).toBe('')
    expect(decode(run.stderr.replace('env: test\n', ''))).toMatchObject({
      error: { code: 'unexpected' },
    })
  })

  it('categories add up to their group and groups to their line, for any movements', async () => {
    const kinds = [
      ['Salary', 'Income', 1],
      ['Interest', 'Income', 1],
      ['Restaurants', 'Food & Dining', -1],
      ['Groceries', 'Food & Dining', -1],
      ['Clothing', 'Shopping', -1],
      ['Investment', 'Transfers & Investments', 1],
    ] as const
    const lineOf = {
      Income: 'income',
      'Food & Dining': 'spending',
      Shopping: 'spending',
      'Transfers & Investments': 'outside',
    } as const
    const items = fc.array(
      fc.record({
        category: fc.nat({ max: kinds.length - 1 }),
        cents: fc.integer({ min: 1, max: 1_000_000_000 }),
        out: fc.boolean(),
        day: fc.integer({ min: 1, max: 28 }),
      }),
      { minLength: 1, maxLength: 20 },
    )
    const transfers = fc.array(fc.integer({ min: 1, max: 1_000_000_000 }), {
      minLength: 1,
      maxLength: 3,
    })

    await fc.assert(
      fc.asyncProperty(items, transfers, async (moves, transferred) => {
        const cli = ledgerCli()
        const bank = await addAccount(cli, 'Bank', 'COP', '0')
        const savings = await addAccount(cli, 'Savings', 'COP', '0')
        const codes: string[] = []
        for (const [name, group] of kinds) codes.push(await addCategory(cli, name, group))
        const signed = moves.map(({ category, cents, out, day }) => ({
          category,
          cents: out ? -cents : cents,
          date: `2026-10-${String(day).padStart(2, '0')}`,
        }))
        await record(
          cli,
          ...signed.map(({ category, cents, date }) =>
            movement(bank, codes[category]!, date, (cents / 100).toFixed(2)),
          ),
        )

        const before = await report(cli, ...OCTOBER)
        await write(cli, {
          transfers: transferred.map((cents) => ({
            from: {
              account: bank,
              date: '2026-10-15',
              payee: 'Out',
              amount: (-cents / 100).toFixed(2),
              currency: 'COP',
            },
            to: {
              account: savings,
              date: '2026-10-15',
              payee: 'In',
              amount: (cents / 100).toFixed(2),
              currency: 'COP',
            },
          })),
        })
        const after = await report(cli, ...OCTOBER)

        const { totals, groups, categories } = decode(before.stdout) as Report
        const cents = (amount: number) => Math.round(amount * 100)
        const expectedCategory = new Map<string, number>()
        for (const { category, cents: amount } of signed) {
          const code = codes[category]!
          const sign = kinds[category]![2]
          expectedCategory.set(code, (expectedCategory.get(code) ?? 0) + sign * amount)
        }
        expect(new Map(categories.map(({ id, total }) => [id, cents(total)]))).toEqual(
          expectedCategory,
        )
        for (const group of groups)
          expect(cents(group.total)).toBe(
            categories
              .filter((row) => row.group === group.id)
              .reduce((sum, row) => sum + cents(row.total), 0),
          )
        const lines = Object.fromEntries(totals.map(({ line, total }) => [line, cents(total)]))
        for (const line of ['income', 'spending', 'outside'])
          expect(lines[line]).toBe(
            groups
              .filter(({ name }) => lineOf[name as keyof typeof lineOf] === line)
              .reduce((sum, row) => sum + cents(row.total), 0),
          )
        expect(lines.left).toBe(lines.income! - lines.spending!)
        expect(after.stdout).toBe(before.stdout)
      }),
      { numRuns: 50 },
    )
  })
})

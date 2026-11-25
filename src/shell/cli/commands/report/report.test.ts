import { decode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import { addAccount, addCategory, write } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { invalidInput, notFound } from '../../../../../tests/support/refusals/refusals.ts'
import {
  mixedMoves,
  movement,
  record,
  recordMixed,
  report,
  reportBooks,
  withCodes,
} from '../../../../../tests/support/reports/reports.ts'
import type { MixedMove, Report } from '../../../../../tests/support/reports/reports.types.ts'

const OCTOBER = ['2026-10-01', '2026-10-31'] as const

function totalsOf(stdout: string): Record<string, number> {
  const { totals } = decode(stdout) as Report
  return Object.fromEntries(totals.map(({ line, total }) => [line, total]))
}

function recordedIds(stdout: string): string[] {
  return (decode(stdout) as { recorded: { id: string }[] }).recorded.map(({ id }) => id)
}

async function usdAndKrwOctober() {
  const books = await reportBooks()
  await record(
    books.cli,
    movement(books.wallet, books.restaurants, '2026-10-03', '-10.85', 'USD'),
    movement(books.card, books.restaurants, '2026-10-04', '-15000', 'KRW'),
  )
  return books
}

const SEPTEMBER = ['2026-09-01', '2026-09-30'] as const

async function tripSeptember() {
  const books = await reportBooks()
  await books.cli.run(['tag', 'add', 'trip:lima-2026'])
  await record(
    books.cli,
    movement(books.wallet, books.restaurants, '2026-09-03', '-20', 'USD', {
      tags: ['trip:lima-2026'],
    }),
    movement(books.wallet, books.restaurants, '2026-09-04', '-5', 'USD'),
    movement(books.bank, books.restaurants, '2026-09-05', '-100000'),
  )
  await books.cli.run(['rate', 'set', 'USD', '4000'])
  return books
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
    const books = await usdAndKrwOctober()

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

  it('every total is in COP at the rate, with the part in each currency next to it (USD, KRW)', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.restaurants, '2026-09-03', '-10.85', 'USD'),
      movement(books.card, books.restaurants, '2026-09-04', '-15000', 'KRW'),
    )
    await books.cli.run(['rate', 'set', 'USD', '3912.45'])
    await books.cli.run(['rate', 'set', 'KRW', '2.85'])

    const run = await report(books.cli, '2026-09-01', '2026-09-30')

    expect(run.code).toBe(0)
    expect(withCodes(run.stdout, { restaurants: books.restaurants })).toBe(`from: 2026-09-01
to: 2026-09-30
currency: COP
rates[2]{currency,rate}:
  KRW,2.85
  USD,3912.45
totals[4]{line,total,KRW,USD}:
  income,0,0,0
  spending,85200.08,15000,10.85
  left,-85200.08,-15000,-10.85
  outside,0,0,0
groups[1]{id,kind,emoji,name,total,KRW,USD}:
  1aae,spending,🍽️,Food & Dining,85200.08,15000,10.85
categories[1]{id,group,emoji,name,total,KRW,USD}:
  <restaurants>,1aae,🍽️,Restaurants,85200.08,15000,10.85
`)
  })

  it('the spec example: 3,000 USD salary at 4,000 is 12,000,000 COP', async () => {
    const books = await reportBooks()
    const { cli, bank, wallet } = books
    const interest = await addCategory(cli, 'Interest', 'Income', '💰')
    const carPayment = await addCategory(cli, 'Car Payment', 'Auto & Transport', '🚘')
    const groceries = await addCategory(cli, 'Groceries', 'Food & Dining', '🛒')
    const aiTools = await addCategory(cli, 'AI Tools', 'Software & AI', '🤖')
    await record(
      cli,
      movement(wallet, books.salary, '2026-10-31', '3000', 'USD'),
      movement(bank, interest, '2026-10-31', '15000.50'),
      movement(bank, carPayment, '2026-10-05', '-1200000'),
      movement(bank, groceries, '2026-10-06', '-600000'),
      movement(bank, books.restaurants, '2026-10-07', '-300000'),
      movement(bank, books.restaurants, '2026-10-08', '50000'),
      movement(wallet, aiTools, '2026-10-09', '-20', 'USD'),
      movement(wallet, books.investment, '2026-10-31', '-1000', 'USD'),
    )
    await cli.run(['rate', 'set', 'USD', '4000'])

    const run = await report(cli, ...OCTOBER)

    const codes = {
      interest,
      salary: books.salary,
      carPayment,
      groceries,
      restaurants: books.restaurants,
      aiTools,
      investment: books.investment,
    }
    expect(withCodes(run.stdout, codes)).toBe(`from: 2026-10-01
to: 2026-10-31
currency: COP
rates[1]{currency,rate}:
  USD,4000
totals[4]{line,total,USD}:
  income,12015000.5,3000
  spending,2130000,20
  left,9885000.5,2980
  outside,-4000000,-1000
groups[5]{id,kind,emoji,name,total,USD}:
  m0z7,income,💰,Income,12015000.5,3000
  y6v7,spending,🚗,Auto & Transport,1200000,0
  1aae,spending,🍽️,Food & Dining,850000,0
  pjbv,spending,💻,Software & AI,80000,20
  7hdg,outside,🔄,Transfers & Investments,-4000000,-1000
categories[7]{id,group,emoji,name,total,USD}:
  <interest>,m0z7,💰,Interest,15000.5,0
  <salary>,m0z7,💼,Salary,12000000,3000
  <carPayment>,y6v7,🚘,Car Payment,1200000,0
  <groceries>,1aae,🛒,Groceries,600000,0
  <restaurants>,1aae,🍽️,Restaurants,250000,0
  <aiTools>,pjbv,🤖,AI Tools,80000,20
  <investment>,7hdg,📈,Investment,-4000000,-1000
`)
  })

  it('each foreign movement converts on its own: two 0.01 USD at 3,912.45 are 78.24 COP, not 78.25', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.restaurants, '2026-10-03', '-0.01', 'USD'),
      movement(books.wallet, books.restaurants, '2026-10-04', '-0.01', 'USD'),
    )
    await books.cli.run(['rate', 'set', 'USD', '3912.45'])

    const { categories } = decode((await report(books.cli, ...OCTOBER)).stdout) as Report

    expect(categories).toMatchObject([{ total: 78.24, USD: 0.02 }])
  })

  it('a purchase and its refund convert to exact opposites', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.clothing, '2026-09-28', '-10.85', 'USD'),
      movement(books.wallet, books.clothing, '2026-10-03', '10.85', 'USD'),
    )
    await books.cli.run(['rate', 'set', 'USD', '3912.45'])

    const september = decode((await report(books.cli, '2026-09-01', '2026-09-30')).stdout) as Report
    const october = decode((await report(books.cli, ...OCTOBER)).stdout) as Report

    expect(september.categories).toMatchObject([{ total: 42450.08, USD: 10.85 }])
    expect(october.categories).toMatchObject([{ total: -42450.08, USD: -10.85 }])
  })

  it('a currency with a rate needs none for the others in COP', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.restaurants, '2026-09-03', '-10', 'USD'),
      movement(books.bank, books.restaurants, '2026-10-03', '-300000'),
    )
    await books.cli.run(['rate', 'set', 'USD', '4000'])
    await books.cli.run(['rate', 'set', 'KRW', '2.85'])

    const september = await report(books.cli, '2026-09-01', '2026-09-30')
    const october = await report(books.cli, ...OCTOBER)

    expect(decode(september.stdout)).toMatchObject({
      rates: [{ currency: 'USD', rate: 4000 }],
      totals: expect.arrayContaining([{ line: 'spending', total: 40000, USD: 10 }]),
    })
    expect(decode(october.stdout)).toMatchObject({
      rates: [],
      totals: expect.arrayContaining([{ line: 'spending', total: 300000 }]),
    })
  })

  it('missing_rate names only the currencies without a rate', async () => {
    const books = await usdAndKrwOctober()
    await books.cli.run(['rate', 'set', 'USD', '3912.45'])

    const run = await report(books.cli, ...OCTOBER)

    expect(run.code).toBe(1)
    expect(run.stderr).toBe(`env: test
error:
  code: missing_rate
  currencies[1]: KRW
  message: no rate for KRW; set one with quaestor rate set
`)
  })

  it('with a whole rate, every figure is its COP part plus each foreign part times the rate', async () => {
    const sign = { salary: 1, restaurants: -1, clothing: -1, investment: 1 } as const
    const lineOf = {
      salary: 'income',
      restaurants: 'spending',
      clothing: 'spending',
      investment: 'outside',
    } as const
    const wholeRate = fc.integer({ min: 1, max: 5000 })

    await fc.assert(
      fc.asyncProperty(mixedMoves({ min: 10, max: 10 }), wholeRate, async (moves, rate) => {
        const books = await reportBooks()
        await recordMixed(books, moves)
        await books.cli.run(['rate', 'set', 'USD', String(rate)])

        const { totals, categories } = decode(
          (await report(books.cli, ...OCTOBER)).stdout,
        ) as Report

        const inCop = (keep: (move: MixedMove) => boolean) =>
          moves
            .filter(keep)
            .reduce(
              (sum, move) => sum + sign[move.category] * move.cents * (move.usd ? rate : 1),
              0,
            )
        const cents = (amount: number) => Math.round(amount * 100)
        for (const row of categories) {
          const name = (Object.keys(sign) as MixedMove['category'][]).find(
            (key) => books[key] === row.id,
          )
          expect(cents(row.total)).toBe(inCop((move) => move.category === name))
        }
        const lines = Object.fromEntries(totals.map(({ line, total }) => [line, cents(total)]))
        for (const line of ['income', 'spending', 'outside'])
          expect(lines[line]).toBe(inCop((move) => lineOf[move.category] === line))
        expect(lines.left).toBe(lines.income! - lines.spending!)
      }),
      { numRuns: 50 },
    )
  })

  it('--by-month names a month before the year 1000 with four digits and goes on into 1000', async () => {
    const { cli } = await reportBooks()

    const run = await report(cli, '0999-12-01', '1000-01-31', '--by-month')

    const { totals } = decode(run.stdout) as Report
    expect([...new Set(totals.map((row) => row['month']))]).toEqual(['0999-12', '1000-01'])
  })

  it('--by-month gives every month its four totals, a month with no movement at 0', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.salary, '2026-09-30', '3000', 'USD'),
      movement(books.bank, books.restaurants, '2026-10-03', '-250000'),
    )
    await books.cli.run(['rate', 'set', 'USD', '4000'])

    const run = await report(books.cli, '2026-09-01', '2026-10-31', '--by-month')

    expect(run.code).toBe(0)
    expect(withCodes(run.stdout, { salary: books.salary, restaurants: books.restaurants }))
      .toBe(`from: 2026-09-01
to: 2026-10-31
currency: COP
rates[1]{currency,rate}:
  USD,4000
totals[8]{month,line,total,USD}:
  2026-09,income,12000000,3000
  2026-09,spending,0,0
  2026-09,left,12000000,3000
  2026-09,outside,0,0
  2026-10,income,0,0
  2026-10,spending,250000,0
  2026-10,left,-250000,0
  2026-10,outside,0,0
groups[2]{month,id,kind,emoji,name,total,USD}:
  2026-09,m0z7,income,💰,Income,12000000,3000
  2026-10,1aae,spending,🍽️,Food & Dining,250000,0
categories[2]{month,id,group,emoji,name,total,USD}:
  2026-09,<salary>,m0z7,💼,Salary,12000000,3000
  2026-10,<restaurants>,1aae,🍽️,Restaurants,250000,0
`)
  })

  it('months are cut to the period', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.restaurants, '2026-09-14', '-1000'),
      movement(books.bank, books.restaurants, '2026-09-15', '-20000'),
      movement(books.bank, books.restaurants, '2026-10-10', '-300000'),
      movement(books.bank, books.restaurants, '2026-10-11', '-4000000'),
    )

    const run = await report(books.cli, '2026-09-15', '2026-10-10', '--by-month')

    const { totals } = decode(run.stdout) as {
      totals: { month: string; line: string; total: number }[]
    }
    expect([...new Set(totals.map(({ month }) => month))]).toEqual(['2026-09', '2026-10'])
    expect(totals.filter(({ line }) => line === 'spending')).toEqual([
      { month: '2026-09', line: 'spending', total: 20000 },
      { month: '2026-10', line: 'spending', total: 300000 },
    ])
  })

  it('groups and categories carry their month, only where they have movements', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.bank, books.restaurants, '2026-08-03', '-1000'),
      movement(books.bank, books.clothing, '2026-10-03', '-2000'),
      movement(books.bank, books.restaurants, '2026-10-04', '-3000'),
    )

    const run = await report(books.cli, '2026-08-01', '2026-10-31', '--by-month')

    const { totals, groups, categories } = decode(run.stdout) as {
      totals: { month: string }[]
      groups: { month: string; id: string }[]
      categories: { month: string; id: string }[]
    }
    expect(totals).toHaveLength(12)
    expect(groups.map(({ month, id }) => [month, id])).toEqual([
      ['2026-08', '1aae'],
      ['2026-10', '1aae'],
      ['2026-10', 'q3rh'],
    ])
    expect(categories.map(({ month, id }) => [month, id])).toEqual([
      ['2026-08', books.restaurants],
      ['2026-10', books.restaurants],
      ['2026-10', books.clothing],
    ])
  })

  it('the months add up to the period, for any movements', async () => {
    const rate = fc.integer({ min: 1, max: 500_000 })

    await fc.assert(
      fc.asyncProperty(mixedMoves({ min: 9, max: 11 }), rate, async (moves, hundredths) => {
        const books = await reportBooks()
        await recordMixed(books, moves)
        await books.cli.run(['rate', 'set', 'USD', (hundredths / 100).toFixed(2)])

        const whole = decode((await report(books.cli, '2026-09-01', '2026-11-30')).stdout) as Report
        const split = decode(
          (await report(books.cli, '2026-09-01', '2026-11-30', '--by-month')).stdout,
        ) as Record<
          'totals' | 'groups' | 'categories',
          ({ month: string } & Record<string, unknown>)[]
        >

        const cents = (amount: unknown) => Math.round(Number(amount) * 100)
        const added = (
          rows: Record<string, unknown>[],
          key: string,
          value: string,
          column: string,
        ) =>
          rows.filter((row) => row[key] === value).reduce((sum, row) => sum + cents(row[column]), 0)
        const columns = ['total', ...(moves.some(({ usd }) => usd) ? ['USD'] : [])]
        for (const column of columns) {
          for (const row of whole.totals)
            expect(added(split.totals, 'line', row.line, column)).toBe(cents(row[column]))
          for (const row of whole.groups)
            expect(added(split.groups, 'id', row.id, column)).toBe(cents(row[column]))
          for (const row of whole.categories)
            expect(added(split.categories, 'id', row.id, column)).toBe(cents(row[column]))
        }
      }),
      { numRuns: 50 },
    )
  })

  it('--tag keeps only the movements with that tag: how much the trip cost', async () => {
    const books = await tripSeptember()

    const run = await report(books.cli, ...SEPTEMBER, '--tag', 'trip:lima-2026')

    expect(totalsOf(run.stdout)).toEqual({ income: 0, spending: 80000, left: -80000, outside: 0 })
    expect((decode(run.stdout) as Report).categories).toMatchObject([{ total: 80000, USD: 20 }])
  })

  it('--without-tag leaves them out: September without the trip', async () => {
    const books = await tripSeptember()

    const run = await report(books.cli, ...SEPTEMBER, '--without-tag', 'trip:lima-2026')

    expect(totalsOf(run.stdout)).toEqual({ income: 0, spending: 120000, left: -120000, outside: 0 })
    expect((decode(run.stdout) as Report).categories).toMatchObject([{ total: 120000, USD: 5 }])
  })

  it('--payee keeps the payees containing the text, ignoring case and accents', async () => {
    const books = await reportBooks()
    await record(
      books.cli,
      movement(books.wallet, books.restaurants, '2026-09-03', '-10', 'USD', {
        payee: 'UBER *TRIP',
      }),
      movement(books.wallet, books.restaurants, '2026-09-04', '-2', 'USD', { payee: 'Úber Eats' }),
      movement(books.wallet, books.restaurants, '2026-09-05', '-7', 'USD', { payee: 'Rappi' }),
    )
    await books.cli.run(['rate', 'set', 'USD', '4000'])

    const run = await report(books.cli, ...SEPTEMBER, '--payee', 'uber')

    expect(totalsOf(run.stdout).spending).toBe(48000)
  })

  it('a tag that does not exist is refused as not_found', async () => {
    const books = await tripSeptember()

    const run = await report(books.cli, ...SEPTEMBER, '--tag', 'trip:lima-2062')
    const without = await report(books.cli, ...SEPTEMBER, '--without-tag', 'trip:lima-2062')

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('tag', 'trip:lima-2062') })
    expect(run.stderr).toBe(`env: test
error:
  code: not_found
  kind: tag
  value: "trip:lima-2062"
  message: "tag trip:lima-2062 does not exist"
`)
    expect(without).toEqual(run)
  })

  it('a movement the filters leave out needs no rate', async () => {
    const books = await reportBooks()
    await books.cli.run(['tag', 'add', 'trip:lima-2026'])
    await record(
      books.cli,
      movement(books.wallet, books.restaurants, '2026-09-03', '-5', 'USD'),
      movement(books.bank, books.restaurants, '2026-09-04', '-100000', 'COP', {
        tags: ['trip:lima-2026'],
      }),
    )

    const run = await report(books.cli, ...SEPTEMBER, '--tag', 'trip:lima-2026')

    expect(run.code).toBe(0)
    expect(totalsOf(run.stdout).spending).toBe(100000)
  })

  it('a figure too long to print to the cent fails as unexpected; the longest exact one prints whole', async () => {
    const exact = await reportBooks()
    const tooLong = await reportBooks()
    await record(exact.cli, movement(exact.bank, exact.salary, '2026-10-03', '9999999999999.99'))
    await record(
      tooLong.cli,
      movement(tooLong.bank, tooLong.salary, '2026-10-03', '10000000000000'),
    )

    const printed = await report(exact.cli, ...OCTOBER)
    const failed = await report(tooLong.cli, ...OCTOBER)

    expect(printed.stdout).toContain('  income,9999999999999.99\n')
    expect(failed.code).toBe(2)
    expect(failed.stdout).toBe('')
    expect(decode(failed.stderr.replace('env: test\n', ''))).toMatchObject({
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

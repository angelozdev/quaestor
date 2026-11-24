import { decode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import {
  amountTextOf,
  booked,
  faultyItems,
} from '../../../../../tests/support/arbitraries/arbitraries.ts'
import type {
  Booked,
  BookedAccount,
  Fault,
} from '../../../../../tests/support/arbitraries/arbitraries.types.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import {
  invalidInput,
  invalidJson,
  refused,
} from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

const CODE = /^[0-9a-hjkmnp-tv-z]{4}$/

const OPENING_DATE = '2026-01-05'

const DAY = '2026-11-20'

const NO_SUCH_CODE = 'zz99'

const AMOUNT_MESSAGE =
  'must be an amount like "-15000" or "-30.39": no thousands separator, at most 2 decimals'

const DATE_MESSAGE = 'must be a date like 2026-11-24'

const NOTHING_TO_WRITE = 'nothing to write: give delete, movements or transfers'

type Json = Record<string, unknown>

type Books = Awaited<ReturnType<typeof openBooks>>

type Spender = Pick<Books, 'wallet' | 'food'>

type Problem = { code: string; item: string; message: string }

async function added(cli: LedgerCli, argv: string[], kind: string): Promise<string> {
  const { stdout } = await cli.run(argv)
  return (decode(stdout) as Record<string, { id: string }>)[kind]!.id
}

function addAccount(cli: LedgerCli, name: string, currency: string, opening: string) {
  const flags = { emoji: '🏦', type: 'debit', currency, opening, 'opening-date': OPENING_DATE }
  const argv = Object.entries(flags).flatMap(([flag, value]) => [`--${flag}`, value])
  return added(cli, ['account', 'add', name, ...argv], 'account')
}

function addCategory(cli: LedgerCli, name = 'Food') {
  return added(cli, ['category', 'add', name, '--emoji', '🍽️'], 'category')
}

async function openBooks(cli = ledgerCli()) {
  return {
    cli,
    wallet: await addAccount(cli, 'Wallet', 'USD', '120.50'),
    savings: await addAccount(cli, 'Savings', 'USD', '0'),
    bank: await addAccount(cli, 'Bank', 'COP', '1000000'),
    food: await addCategory(cli),
  }
}

function write(cli: LedgerCli, body: unknown, ...flags: string[]) {
  const stdin = typeof body === 'string' ? body : JSON.stringify(body)
  return cli.run(['movement', 'write', ...flags], stdin)
}

function spend(books: Spender, extra: Json = {}): Json {
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

function recorded(movement: Json, extra: Json = {}): Json {
  return {
    id: expect.stringMatching(CODE),
    date: movement.date,
    account: movement.account,
    payee: movement.payee,
    amount: Number(movement.amount),
    currency: movement.currency,
    category: movement.category,
    tags: '',
    note: null,
    transfer: null,
    ...extra,
  }
}

function notFound(item: string, kind: string, id: string): Problem {
  return { code: 'not_found', item, message: `${kind} ${id} does not exist` }
}

function wrongCurrency(item: string, account: string, held: string, given: string): Problem {
  return {
    code: 'currency_mismatch',
    item,
    message: `account ${account} holds ${held}, not ${given}`,
  }
}

function beforeOpening(item: string, account: string, date: string): Problem {
  return {
    code: 'before_opening',
    item,
    message: `account ${account} opens on ${OPENING_DATE}, after ${date}`,
  }
}

async function accountsText(cli: LedgerCli): Promise<string> {
  return (await cli.run(['account', 'list'])).stdout
}

function balancesById(stdout: string): Record<string, number> {
  const { accounts } = decode(stdout) as { accounts: { id: string; balance: number }[] }
  return Object.fromEntries(accounts.map(({ id, balance }) => [id, balance]))
}

function drawing(indexes: number[]) {
  let draws = 0
  return () => indexes[draws++]!
}

const OPENING_CENTS = { wallet: 12050, savings: 0 }

function bookedMovements(books: Books, items: Booked[]): Json[] {
  const accounts = { wallet: books.wallet, savings: books.savings }
  return items.map(({ account, cents, date }) =>
    spend(books, { account: accounts[account], amount: amountTextOf(cents), date }),
  )
}

function totalCents(items: Booked[], account: BookedAccount): number {
  return items
    .filter((item) => item.account === account)
    .reduce((total, { cents }) => total + cents, OPENING_CENTS[account])
}

function faultyMovement(books: Books, fault: Fault | undefined): Json {
  if (fault === 'category') return spend(books, { category: NO_SUCH_CODE })
  if (fault === 'currency') return spend(books, { currency: 'EUR' })
  if (fault === 'opening') return spend(books, { date: '2026-01-04' })
  return spend(books)
}

function problemOf(books: Books, fault: Fault, item: string): Problem {
  if (fault === 'category') return notFound(item, 'category', NO_SUCH_CODE)
  if (fault === 'currency') return wrongCurrency(item, books.wallet, 'USD', 'EUR')
  return beforeOpening(item, books.wallet, '2026-01-04')
}

describe('quaestor movement write', () => {
  it('a movement is recorded in its account and its balance moves by its amount (USD)', async () => {
    const books = await openBooks()
    const spending = spend(books)

    const run = await write(books.cli, { movements: [spending] })
    const listed = await accountsText(books.cli)

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(spending)],
      balances: [{ account: books.wallet, currency: 'USD', before: 120.5, after: 108 }],
    })
    expect(balancesById(listed)).toEqual({
      [books.bank]: 1000000,
      [books.savings]: 0,
      [books.wallet]: 108,
    })
  })

  it('a movement carries its tags and its note', async () => {
    const books = await openBooks()
    await books.cli.run(['tag', 'add', 'trip:lima-2026'])
    await books.cli.run(['tag', 'add', 'who:alex'])
    const spending = spend(books, { tags: ['trip:lima-2026', 'who:alex'], note: 'cambio a 4.000' })

    const run = await write(books.cli, { movements: [spending] })

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(spending, { tags: 'trip:lima-2026 who:alex', note: 'cambio a 4.000' })],
      balances: [{ account: books.wallet, currency: 'USD', before: 120.5, after: 108 }],
    })
  })

  it('money in is positive and money out negative', async () => {
    const books = await openBooks()
    const refund = spend(books, { payee: 'Refund', amount: '20' })
    const dinner = spend(books, { payee: 'Dinner', amount: '-50' })

    const run = await write(books.cli, { movements: [refund, dinner] })

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(refund), recorded(dinner)],
      balances: [{ account: books.wallet, currency: 'USD', before: 120.5, after: 90.5 }],
    })
  })

  it('--dry-run shows each movement and the balance before and after, and writes nothing', async () => {
    const books = await openBooks()
    const spending = spend(books)
    const before = await accountsText(books.cli)

    const dry = await write(books.cli, { movements: [spending] }, '--dry-run')

    expectWrite(dry, true, {
      deleted: [],
      recorded: [recorded(spending)],
      balances: [{ account: books.wallet, currency: 'USD', before: 120.5, after: 108 }],
    })
    expect(await accountsText(books.cli)).toBe(before)
  })

  it('balances list every touched account once, sorted by account code', async () => {
    const books = await openBooks()
    const first = spend(books, { account: books.bank, currency: 'COP', amount: '-15000' })
    const second = spend(books, { amount: '-10' })
    const third = spend(books, { account: books.bank, currency: 'COP', amount: '2000' })

    const run = await write(books.cli, { movements: [first, second, third] })

    const touched = [
      { account: books.bank, currency: 'COP', before: 1000000, after: 987000 },
      { account: books.wallet, currency: 'USD', before: 120.5, after: 110.5 },
    ]
    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(first), recorded(second), recorded(third)],
      balances: touched.toSorted((a, b) => (a.account < b.account ? -1 : 1)),
    })
  })

  it('a payee and a category are required', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [spend(books, { payee: undefined, category: undefined })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('movements[0].payee: is required', 'movements[0].category: is required'),
    })
  })

  it('a payee with no text is refused', async () => {
    const books = await openBooks()

    const run = await write(books.cli, { movements: [spend(books, { payee: '  ' })] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('movements[0].payee: is required'),
    })
  })

  it.for(['0', '0.00'])('a zero amount is refused (%s)', async (amount) => {
    const books = await openBooks()

    const run = await write(books.cli, { movements: [spend(books, { amount })] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('movements[0].amount: must not be 0'),
    })
  })

  it('an amount is read back as written (USD)', async () => {
    const books = await openBooks()
    const spending = spend(books, { amount: '-30.39' })

    const run = await write(books.cli, { movements: [spending] })
    const listed = await accountsText(books.cli)

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(spending, { amount: -30.39 })],
      balances: [{ account: books.wallet, currency: 'USD', before: 120.5, after: 90.11 }],
    })
    expect(balancesById(listed)[books.wallet]).toBe(90.11)
  })

  it('a COP amount copied with its thousands dot is refused', async () => {
    const books = await openBooks()
    const copied = spend(books, { account: books.bank, currency: 'COP', amount: '-15.000' })
    const misdated = spend(books, { date: '24/11/2026' })

    const run = await write(books.cli, { movements: [copied, misdated] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        `movements[0].amount: ${AMOUNT_MESSAGE}`,
        `movements[1].date: ${DATE_MESSAGE}`,
      ),
    })
  })

  it('an amount given as a JSON number is refused', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [spend(books, { account: books.bank, currency: 'COP', amount: -15000 })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(`movements[0].amount: ${AMOUNT_MESSAGE}`),
    })
  })

  it("an account's balance is its opening plus the sum of its movements, for any movements (USD)", async () => {
    await fc.assert(
      fc.asyncProperty(booked(OPENING_DATE), async (items) => {
        const books = await openBooks()

        const run = await write(books.cli, { movements: bookedMovements(books, items) })
        const listed = await accountsText(books.cli)

        const expected = {
          [books.wallet]: totalCents(items, 'wallet') / 100,
          [books.savings]: totalCents(items, 'savings') / 100,
        }
        const shown = decode(run.stdout) as { balances: { account: string; after: number }[] }
        expect(run.code).toBe(0)
        expect(balancesById(listed)).toMatchObject(expected)
        for (const { account, after } of shown.balances) expect(after).toBe(expected[account])
      }),
      { numRuns: 50 },
    )
  })

  it('a write with faulty items writes nothing and lists exactly those items, in order', async () => {
    await fc.assert(
      fc.asyncProperty(faultyItems, async (faults) => {
        const books = await openBooks()
        const before = await accountsText(books.cli)
        const movements = faults.map((fault) => faultyMovement(books, fault))

        const run = await write(books.cli, { movements })

        const problems = faults.flatMap((fault, index) =>
          fault === undefined ? [] : [problemOf(books, fault, `movements[${index}]`)],
        )
        expect(run).toEqual({ code: 1, stdout: '', stderr: refused(...problems) })
        expect(await accountsText(books.cli)).toBe(before)
      }),
      { numRuns: 50 },
    )
  })

  it('a dry run changes nothing, and its balances after are what the write then shows', async () => {
    await fc.assert(
      fc.asyncProperty(booked(OPENING_DATE), async (items) => {
        const books = await openBooks()
        const body = { movements: bookedMovements(books, items) }
        const before = await accountsText(books.cli)

        const dry = await write(books.cli, body, '--dry-run')
        const untouched = await accountsText(books.cli)
        const real = await write(books.cli, body)
        const listed = balancesById(await accountsText(books.cli))

        const shown = (run: { stdout: string }) =>
          (decode(run.stdout) as { balances: Json[] }).balances
        expect(dry.stdout.startsWith('dryRun: true\n')).toBe(true)
        expect(real.stdout.startsWith('dryRun: false\n')).toBe(true)
        expect(untouched).toBe(before)
        expect(shown(dry)).toEqual(shown(real))
        for (const { account, after } of shown(dry) as { account: string; after: number }[])
          expect(listed[account]).toBe(after)
      }),
      { numRuns: 50 },
    )
  })

  it('an impossible date such as 2026-02-30 is refused', async () => {
    const books = await openBooks()

    const run = await write(books.cli, { movements: [spend(books, { date: '2026-02-30' })] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(`movements[0].date: ${DATE_MESSAGE}`),
    })
  })

  it('every item at fault is listed at once, and nothing is written', async () => {
    const books = await openBooks()
    const before = await accountsText(books.cli)

    const run = await write(books.cli, {
      movements: [
        spend(books, { category: NO_SUCH_CODE }),
        spend(books),
        spend(books, { currency: 'EUR' }),
      ],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(
        notFound('movements[0]', 'category', NO_SUCH_CODE),
        wrongCurrency('movements[2]', books.wallet, 'USD', 'EUR'),
      ),
    })
    expect(await accountsText(books.cli)).toBe(before)
  })

  it("a movement in another currency than its account's is refused", async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [spend(books, { account: books.bank, currency: 'USD' })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(wrongCurrency('movements[0]', books.bank, 'COP', 'USD')),
    })
  })

  it('an unknown account, category or tag is refused', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [
        spend(books, { account: NO_SUCH_CODE, currency: 'EUR', date: '2000-01-01' }),
        spend(books, { category: NO_SUCH_CODE }),
        spend(books, { tags: ['trip:nowhere'] }),
      ],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(
        notFound('movements[0]', 'account', NO_SUCH_CODE),
        notFound('movements[1]', 'category', NO_SUCH_CODE),
        notFound('movements[2]', 'tag', 'trip:nowhere'),
      ),
    })
  })

  it('an item with several faults is listed once for each, in field order', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [
        spend(books, {
          date: '2026-01-04',
          currency: 'EUR',
          category: NO_SUCH_CODE,
          tags: ['trip:nowhere'],
        }),
        spend(books, { account: NO_SUCH_CODE, category: NO_SUCH_CODE, tags: ['trip:nowhere'] }),
      ],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(
        beforeOpening('movements[0]', books.wallet, '2026-01-04'),
        wrongCurrency('movements[0]', books.wallet, 'USD', 'EUR'),
        notFound('movements[0]', 'category', NO_SUCH_CODE),
        notFound('movements[0]', 'tag', 'trip:nowhere'),
        notFound('movements[1]', 'account', NO_SUCH_CODE),
        notFound('movements[1]', 'category', NO_SUCH_CODE),
        notFound('movements[1]', 'tag', 'trip:nowhere'),
      ),
    })
  })

  it("a movement dated before its account's opening date is refused", async () => {
    const books = await openBooks()

    const run = await write(books.cli, { movements: [spend(books, { date: '2026-01-04' })] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(beforeOpening('movements[0]', books.wallet, '2026-01-04')),
    })
  })

  it("a movement dated on its account's opening date is accepted", async () => {
    const books = await openBooks()
    const spending = spend(books, { date: OPENING_DATE })

    const run = await write(books.cli, { movements: [spending] })

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(spending)],
      balances: [{ account: books.wallet, currency: 'USD', before: 120.5, after: 108 }],
    })
  })

  it('any category takes money in or money out', async () => {
    const books = await openBooks()
    const deposit = spend(books, { account: books.bank, currency: 'COP', amount: '2000' })

    const run = await write(books.cli, { movements: [deposit] })

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(deposit)],
      balances: [{ account: books.bank, currency: 'COP', before: 1000000, after: 1002000 }],
    })
  })

  it('a refusal anywhere in the write writes nothing', async () => {
    const books = await openBooks()
    const before = await accountsText(books.cli)

    const run = await write(books.cli, {
      movements: [spend(books), spend(books, { category: NO_SUCH_CODE })],
    })

    expect(run.code).toBe(1)
    expect(await accountsText(books.cli)).toBe(before)
  })

  it('two movements never share a code, even when the draw repeats', async () => {
    const cli = ledgerCli({
      randomIndex: drawing([0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 4, 5, 6, 7]),
    })
    const wallet = await addAccount(cli, 'Wallet', 'USD', '120.50')
    const food = await addCategory(cli)
    const books = { wallet, food }

    const run = await write(cli, { movements: [spend(books), spend(books)] })

    const shown = decode(run.stdout) as { recorded: { id: string }[] }
    expect(shown.recorded.map(({ id }) => id)).toEqual(['0123', '4567'])
  })

  it('two writes never share a code, even when the draw starts over', async () => {
    const books = await openBooks()

    const first = await write(books.cli, { movements: [spend(books)] })
    const second = await write(books.cli, { movements: [spend(books)] })

    const ids = [first, second].map(
      ({ stdout }) => (decode(stdout) as { recorded: { id: string }[] }).recorded[0]!.id,
    )
    expect(ids[0]).toMatch(CODE)
    expect(ids[1]).toMatch(CODE)
    expect(ids[1]).not.toBe(ids[0])
  })

  it('empty stdin is invalid_json', async () => {
    const run = await ledgerCli().run(['movement', 'write'], '')

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidJson('Unexpected end of JSON input'),
    })
  })

  it('stdin that is not JSON is invalid_json, with its reason on one line', async () => {
    const run = await ledgerCli().run(['movement', 'write'], '{"movements": [\n  {"a": 1,\n')

    expect(run.code).toBe(1)
    expect(run.stdout).toBe('')
    const { error } = decode(run.stderr) as { error: { code: string; message: string } }
    expect(error.code).toBe('invalid_json')
    expect(error.message).toMatch(/^invalid JSON on stdin: [^\n]+$/)
  })

  it.for([
    [
      'a movement',
      (books: Books) => ({ movements: [spend(books, { memo: 'x' })] }),
      'movements[0].memo',
    ],
    ['the write', (books: Books) => ({ movements: [spend(books)], extra: 1 }), 'extra'],
  ] as const)('a field the schema does not know is refused (%s)', async ([, body, path]) => {
    const books = await openBooks()

    const run = await write(books.cli, body(books))

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(`${path}: is not a field`),
    })
  })

  it.for([{}, { movements: [] }, { delete: [], movements: [], transfers: [] }])(
    'a write with nothing in it is refused (%j)',
    async (body) => {
      const run = await write(ledgerCli(), body)

      expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput(NOTHING_TO_WRITE) })
    },
  )

  it('a tag listed twice is refused', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [spend(books, { tags: ['who:alex', 'trip:lima-2026', 'who:alex'] })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('movements[0].tags[2]: is repeated'),
    })
  })

  it('a tag outside lowercase letters, digits, colons and dashes is refused', async () => {
    const books = await openBooks()

    const run = await write(books.cli, { movements: [spend(books, { tags: ['Trip Japón'] })] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        'movements[0].tags[0]: must be lowercase letters, digits, colons and dashes',
      ),
    })
  })
})

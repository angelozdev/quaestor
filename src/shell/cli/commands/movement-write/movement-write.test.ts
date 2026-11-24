import { decode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import {
  booked,
  bookedWithDeletes,
  faultyItems,
  moved,
} from '../../../../../tests/support/arbitraries/arbitraries.ts'
import type {
  Booked,
  BookedAccount,
  Fault,
  Moved,
  MovedAccount,
} from '../../../../../tests/support/arbitraries/arbitraries.types.ts'
import {
  addAccount,
  addCategory,
  bookedMovements,
  list,
  movedTransfers,
  openBooks,
  spend,
  transfer,
  write,
} from '../../../../../tests/support/books/books.ts'
import { OPENING_DATE } from '../../../../../tests/support/books/books.constants.ts'
import type { Books, Json, Transfer } from '../../../../../tests/support/books/books.types.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import {
  invalidInput,
  invalidJson,
  refused,
} from '../../../../../tests/support/refusals/refusals.ts'
import type { CliRun } from '../../../../../tests/support/run-cli/run-cli.types.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

const CODE = /^[0-9a-hjkmnp-tv-z]{4}$/

const NO_SUCH_CODE = 'zz99'

const AMOUNT_MESSAGE =
  'must be an amount like "-15000" or "-30.39": no thousands separator, at most 2 decimals'

const DATE_MESSAGE = 'must be a date like 2026-11-24'

const NOTHING_TO_WRITE = 'nothing to write: give delete, movements or transfers'

const LEAVING_MESSAGE = 'must be negative: the money leaves this account'

const ARRIVING_MESSAGE = 'must be positive: the money arrives in this account'

const ZERO_MESSAGE = 'must not be 0'

const TOO_LARGE_MESSAGE = 'is too large: at most 90071992547409.91 either way'

type Problem = { code: string; item: string; message: string }

type BalanceChange = { account: string; currency: string; before: number; after: number }

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

function half(movement: Json, extra: Json = {}): Json {
  return recorded(movement, { category: null, ...extra })
}

function recordedRows(run: CliRun): Json[] {
  return (decode(run.stdout) as { recorded: Json[] }).recorded
}

function recordedHalves(
  run: CliRun,
  moving: Transfer,
  fromExtra: Json = {},
  toExtra: Json = {},
): Json[] {
  const [leaving, arriving] = recordedRows(run).slice(-2)
  return [
    half(moving.from, { transfer: arriving?.id, ...fromExtra }),
    half(moving.to, { transfer: leaving?.id, ...toExtra }),
  ]
}

function walletToSavings(books: Books): BalanceChange[] {
  return [
    { account: books.wallet, currency: 'USD', before: 120.5, after: 110.5 },
    { account: books.savings, currency: 'USD', before: 0, after: 10 },
  ].toSorted(byAccount)
}

function sameAccount(item: string, account: string): Problem {
  return {
    code: 'same_account_transfer',
    item,
    message: `a transfer needs two different accounts, not ${account} twice`,
  }
}

function byAccount(a: { account: string }, b: { account: string }): number {
  return a.account < b.account ? -1 : 1
}

async function accountsText(cli: LedgerCli): Promise<string> {
  return (await cli.run(['account', 'list'])).stdout
}

function balancesById(stdout: string): Record<string, number> {
  const { accounts } = decode(stdout) as { accounts: { id: string; balance: number }[] }
  return Object.fromEntries(accounts.map(({ id, balance }) => [id, balance]))
}

function idOf(row: Json | undefined): string {
  return String(row?.id)
}

async function recordedBy(cli: LedgerCli, body: Json): Promise<Json[]> {
  return recordedRows(await write(cli, body))
}

async function listedText(cli: LedgerCli): Promise<string> {
  return (await list(cli)).stdout
}

async function bookedRide() {
  const books = await openBooks()
  const [ride] = await recordedBy(books.cli, { movements: [spend(books)] })
  return {
    books,
    ride,
    before: await accountsText(books.cli),
    listedBefore: await listedText(books.cli),
  }
}

function nothingListed(stdout: string): void {
  expect(decode(stdout)).toEqual({ total: 0, movements: [] })
}

function walletBack(books: Pick<Books, 'wallet'>, before: number, after: number): BalanceChange {
  return { account: books.wallet, currency: 'USD', before, after }
}

function drawing(indexes: number[]) {
  let draws = 0
  return () => indexes[draws++]!
}

const OPENING_CENTS = { wallet: 12050, savings: 0, bank: 100_000_000 }

function totalCents(items: Booked[], account: BookedAccount): number {
  return items
    .filter((item) => item.account === account)
    .reduce((total, { cents }) => total + cents, OPENING_CENTS[account])
}

function movedCents(items: Moved[], account: MovedAccount): number {
  return items.reduce(
    (total, { from, to, sent, received }) =>
      total - (from === account ? sent : 0) + (to === account ? received : 0),
    OPENING_CENTS[account],
  )
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
        const listedBefore = (await list(books.cli)).stdout
        const movements = faults.map((fault) => faultyMovement(books, fault))

        const run = await write(books.cli, { movements })

        const problems = faults.flatMap((fault, index) =>
          fault === undefined ? [] : [problemOf(books, fault, `movements[${index}]`)],
        )
        expect(run).toEqual({ code: 1, stdout: '', stderr: refused(...problems) })
        expect(await accountsText(books.cli)).toBe(before)
        expect((await list(books.cli)).stdout).toBe(listedBefore)
      }),
      { numRuns: 50 },
    )
  })

  it('a transfer writes both halves, each in its own account (USD)', async () => {
    const books = await openBooks()
    const moving = transfer(books)

    const run = await write(books.cli, { transfers: [moving] })
    const listed = await accountsText(books.cli)

    expectWrite(run, false, {
      deleted: [],
      recorded: recordedHalves(run, moving),
      balances: walletToSavings(books),
    })
    expect(balancesById(listed)).toEqual({
      [books.bank]: 1000000,
      [books.savings]: 10,
      [books.wallet]: 110.5,
    })
  })

  it('a transfer across currencies carries both amounts and converts nothing', async () => {
    const books = await openBooks()
    const moving = transfer(
      books,
      { amount: '-100' },
      { account: books.bank, currency: 'COP', amount: '400000' },
    )

    const run = await write(books.cli, { transfers: [moving] })

    expectWrite(run, false, {
      deleted: [],
      recorded: recordedHalves(run, moving),
      balances: [
        { account: books.wallet, currency: 'USD', before: 120.5, after: 20.5 },
        { account: books.bank, currency: 'COP', before: 1000000, after: 1400000 },
      ].toSorted(byAccount),
    })
  })

  it('each half keeps its own date, payee and note', async () => {
    const books = await openBooks()
    const moving = transfer(
      books,
      { date: '2026-11-10', payee: 'Wire out', note: 'left on the 10th' },
      { date: '2026-11-11', payee: 'Wire in', note: 'arrived on the 11th' },
    )

    const run = await write(books.cli, { transfers: [moving] })

    expect(recordedRows(run)).toEqual(
      recordedHalves(run, moving, { note: 'left on the 10th' }, { note: 'arrived on the 11th' }),
    )
  })

  it('tags can go on a transfer half', async () => {
    const books = await openBooks()
    await books.cli.run(['tag', 'add', 'trip:lima-2026'])
    await books.cli.run(['tag', 'add', 'who:alex'])
    const moving = transfer(books, { tags: ['trip:lima-2026', 'who:alex'] }, { tags: ['who:alex'] })

    const run = await write(books.cli, { transfers: [moving] })

    expect(recordedRows(run)).toEqual(
      recordedHalves(run, moving, { tags: 'trip:lima-2026 who:alex' }, { tags: 'who:alex' }),
    )
  })

  it('--dry-run of a transfer shows both halves and the balances, and writes nothing', async () => {
    const books = await openBooks()
    const moving = transfer(books)
    const before = await accountsText(books.cli)
    const listedBefore = (await list(books.cli)).stdout

    const dry = await write(books.cli, { transfers: [moving] }, '--dry-run')

    expectWrite(dry, true, {
      deleted: [],
      recorded: recordedHalves(dry, moving),
      balances: walletToSavings(books),
    })
    expect(await accountsText(books.cli)).toBe(before)
    expect((await list(books.cli)).stdout).toBe(listedBefore)
  })

  it('a transfer is written after the movements, and each account joins the balances once', async () => {
    const books = await openBooks()
    const spending = spend(books)
    const moving = transfer(books)

    const run = await write(books.cli, { movements: [spending], transfers: [moving] })

    expectWrite(run, false, {
      deleted: [],
      recorded: [recorded(spending), ...recordedHalves(run, moving)],
      balances: [
        { account: books.wallet, currency: 'USD', before: 120.5, after: 98 },
        { account: books.savings, currency: 'USD', before: 0, after: 10 },
      ].toSorted(byAccount),
    })
  })

  it('a transfer has no category', async () => {
    const books = await openBooks()
    const moving = transfer(books, { category: books.food }, { category: books.food })

    const run = await write(books.cli, { transfers: [moving] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        'transfers[0].from.category: is not a field',
        'transfers[0].to.category: is not a field',
      ),
    })
  })

  it('a transfer between an account and itself is refused', async () => {
    const books = await openBooks()
    const before = await accountsText(books.cli)

    const run = await write(books.cli, {
      transfers: [transfer(books, {}, { account: books.wallet })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(sameAccount('transfers[0]', books.wallet)),
    })
    expect(await accountsText(books.cli)).toBe(before)
  })

  it('the half that leaves must be negative and the half that arrives positive', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      transfers: [transfer(books, { amount: '10' }, { amount: '-10' })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        `transfers[0].from.amount: ${LEAVING_MESSAGE}`,
        `transfers[0].to.amount: ${ARRIVING_MESSAGE}`,
      ),
    })
  })

  it('a half of zero or beyond the limit is refused for that, not for its sign', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      transfers: [
        transfer(books, { amount: '0' }, { amount: '0.00' }),
        transfer(books, { amount: '90071992547409.92' }, { amount: '-90071992547409.92' }),
      ],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        `transfers[0].from.amount: ${ZERO_MESSAGE}`,
        `transfers[0].to.amount: ${ZERO_MESSAGE}`,
        `transfers[1].from.amount: ${TOO_LARGE_MESSAGE}`,
        `transfers[1].to.amount: ${TOO_LARGE_MESSAGE}`,
      ),
    })
  })

  it('a refused half writes neither half', async () => {
    const books = await openBooks()
    const before = await accountsText(books.cli)
    const listedBefore = (await list(books.cli)).stdout

    const run = await write(books.cli, {
      movements: [spend(books)],
      transfers: [transfer(books), transfer(books, {}, { currency: 'EUR' })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(wrongCurrency('transfers[1].to', books.savings, 'USD', 'EUR')),
    })
    expect(await accountsText(books.cli)).toBe(before)
    expect((await list(books.cli)).stdout).toBe(listedBefore)
  })

  it('a transfer lists its accounts, then its from half, then its to half', async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      movements: [spend(books, { category: NO_SUCH_CODE })],
      transfers: [
        transfer(books),
        transfer(
          books,
          { account: books.savings, currency: 'EUR', tags: ['trip:nowhere'] },
          { account: books.savings, date: '2026-01-04' },
        ),
        transfer(books, { account: NO_SUCH_CODE }, { account: NO_SUCH_CODE, tags: ['who:nobody'] }),
      ],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(
        notFound('movements[0]', 'category', NO_SUCH_CODE),
        sameAccount('transfers[1]', books.savings),
        wrongCurrency('transfers[1].from', books.savings, 'USD', 'EUR'),
        notFound('transfers[1].from', 'tag', 'trip:nowhere'),
        beforeOpening('transfers[1].to', books.savings, '2026-01-04'),
        sameAccount('transfers[2]', NO_SUCH_CODE),
        notFound('transfers[2].from', 'account', NO_SUCH_CODE),
        notFound('transfers[2].to', 'account', NO_SUCH_CODE),
        notFound('transfers[2].to', 'tag', 'who:nobody'),
      ),
    })
  })

  it('a transfer moves each account by its own half and no other account (USD and COP)', async () => {
    await fc.assert(
      fc.asyncProperty(moved(OPENING_DATE), async (items) => {
        const books = await openBooks()

        const run = await write(books.cli, { transfers: movedTransfers(books, items) })
        const listed = balancesById(await accountsText(books.cli))

        const rows = recordedRows(run)
        expect(run.code).toBe(0)
        expect(listed).toEqual({
          [books.wallet]: movedCents(items, 'wallet') / 100,
          [books.savings]: movedCents(items, 'savings') / 100,
          [books.bank]: movedCents(items, 'bank') / 100,
        })
        expect(rows).toHaveLength(items.length * 2)
        for (const [index, row] of rows.entries())
          expect(row.transfer).toBe(rows[index % 2 === 0 ? index + 1 : index - 1]?.id)
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

  it('the two halves of a transfer never share a code, even when the draw repeats', async () => {
    const cli = ledgerCli({
      randomIndex: drawing([0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3, 0, 1, 2, 3, 4, 5, 6, 7]),
    })
    const wallet = await addAccount(cli, 'Wallet', 'USD', '120.50')
    const savings = await addAccount(cli, 'Savings', 'USD', '0')

    const run = await write(cli, { transfers: [transfer({ wallet, savings })] })

    expect(recordedRows(run).map(({ id }) => id)).toEqual(['0123', '4567'])
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

  it('a deleted movement leaves every list and its balance returns (USD)', async () => {
    const books = await openBooks()
    const [ride, dinner] = await recordedBy(books.cli, {
      movements: [
        spend(books, { date: '2026-11-20' }),
        spend(books, { date: '2026-11-21', payee: 'Dinner', amount: '-10' }),
      ],
    })

    const run = await write(books.cli, { delete: [idOf(ride)] })
    const listed = await accountsText(books.cli)
    const remaining = await list(books.cli, '--account', books.wallet)

    expectWrite(run, false, {
      deleted: [ride],
      recorded: [],
      balances: [walletBack(books, 98, 110.5)],
    })
    expect(balancesById(listed)[books.wallet]).toBe(110.5)
    expect(decode(remaining.stdout)).toEqual({
      total: 1,
      movements: [{ ...dinner, balance: 110.5 }],
    })
    expect(decode((await list(books.cli)).stdout)).toEqual(decode(remaining.stdout))
  })

  it('a movement already deleted is not_found', async () => {
    const books = await openBooks()
    const [ride] = await recordedBy(books.cli, { movements: [spend(books)] })
    await write(books.cli, { delete: [idOf(ride)] })
    const before = await accountsText(books.cli)

    const run = await write(books.cli, { delete: [idOf(ride)] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(notFound('delete[0]', 'movement', idOf(ride))),
    })
    expect(await accountsText(books.cli)).toBe(before)
  })

  it('deleting one half of a transfer deletes both', async () => {
    const books = await openBooks()
    const [leaving, arriving] = await recordedBy(books.cli, { transfers: [transfer(books)] })

    const run = await write(books.cli, { delete: [idOf(arriving)] })
    const listed = await accountsText(books.cli)

    expectWrite(run, false, {
      deleted: [leaving, arriving],
      recorded: [],
      balances: [
        walletBack(books, 110.5, 120.5),
        { account: books.savings, currency: 'USD', before: 10, after: 0 },
      ].toSorted(byAccount),
    })
    expect(balancesById(listed)).toEqual({
      [books.bank]: 1000000,
      [books.savings]: 0,
      [books.wallet]: 120.5,
    })
    nothingListed(await listedText(books.cli))
  })

  it('naming a movement twice, or both halves, deletes each once', async () => {
    const books = await openBooks()
    const [late, early, leaving, arriving] = await recordedBy(books.cli, {
      movements: [
        spend(books, { date: '2026-11-22' }),
        spend(books, { date: '2026-11-20', payee: 'Dinner' }),
      ],
      transfers: [transfer(books, { date: '2026-11-21' }, { date: '2026-11-21' })],
    })

    const run = await write(books.cli, {
      delete: [idOf(late), idOf(arriving), idOf(late), idOf(leaving), idOf(arriving)],
    })

    expectWrite(run, false, {
      deleted: [leaving, arriving, late],
      recorded: [],
      balances: [
        walletBack(books, 85.5, 108),
        { account: books.savings, currency: 'USD', before: 10, after: 0 },
      ].toSorted(byAccount),
    })
    expect(decode((await list(books.cli)).stdout)).toMatchObject({
      total: 1,
      movements: [early],
    })
  })

  it('a correction is a delete and a new record in one write', async () => {
    const cli = ledgerCli({
      randomIndex: drawing([0, 1, 2, 3, 1, 2, 3, 4, 2, 3, 4, 5, 2, 3, 4, 5, 6, 7, 8, 9]),
    })
    const books = {
      wallet: await addAccount(cli, 'Wallet', 'USD', '120.50'),
      food: await addCategory(cli),
    }
    const [ride] = await recordedBy(cli, { movements: [spend(books)] })
    const correcting = spend(books, { amount: '-15' })

    const run = await write(cli, { delete: [idOf(ride)], movements: [correcting] })
    const listed = await accountsText(cli)

    expect(idOf(ride)).toBe('2345')
    expectWrite(run, false, {
      deleted: [ride],
      recorded: [recorded(correcting, { id: '6789' })],
      balances: [walletBack(books, 108, 105.5)],
    })
    expect(balancesById(listed)[books.wallet]).toBe(105.5)
    expect(decode((await list(cli)).stdout)).toEqual({
      total: 1,
      movements: [{ ...recorded(correcting, { id: '6789' }), balance: 105.5 }],
    })
  })

  it('a correction can move a movement to another account', async () => {
    const books = await openBooks()
    const [ride] = await recordedBy(books.cli, { movements: [spend(books)] })
    const correcting = spend(books, { account: books.savings, amount: '-15' })

    const run = await write(books.cli, { delete: [idOf(ride)], movements: [correcting] })

    expectWrite(run, false, {
      deleted: [ride],
      recorded: [recorded(correcting)],
      balances: [
        walletBack(books, 108, 120.5),
        { account: books.savings, currency: 'USD', before: 0, after: -15 },
      ].toSorted(byAccount),
    })
  })

  it('an unknown movement code is refused and nothing is deleted', async () => {
    const { books, ride, before, listedBefore } = await bookedRide()

    const run = await write(books.cli, { delete: [NO_SUCH_CODE, idOf(ride), NO_SUCH_CODE] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(
        notFound('delete[0]', 'movement', NO_SUCH_CODE),
        notFound('delete[2]', 'movement', NO_SUCH_CODE),
      ),
    })
    expect(await accountsText(books.cli)).toBe(before)
    expect(await listedText(books.cli)).toBe(listedBefore)
  })

  it("a delete's problems are listed before the movements' and the transfers'", async () => {
    const books = await openBooks()

    const run = await write(books.cli, {
      delete: [NO_SUCH_CODE],
      movements: [spend(books, { category: NO_SUCH_CODE })],
      transfers: [transfer(books, {}, { account: books.wallet })],
    })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused(
        notFound('delete[0]', 'movement', NO_SUCH_CODE),
        notFound('movements[0]', 'category', NO_SUCH_CODE),
        sameAccount('transfers[0]', books.wallet),
      ),
    })
  })

  it('--dry-run of a delete writes nothing', async () => {
    const { books, ride, before, listedBefore } = await bookedRide()

    const dry = await write(books.cli, { delete: [idOf(ride)] }, '--dry-run')
    const untouched = await accountsText(books.cli)
    const untouchedList = await listedText(books.cli)
    const real = await write(books.cli, { delete: [idOf(ride)] })

    expect(dry.stdout.startsWith('dryRun: true\n')).toBe(true)
    expectWrite(dry, true, {
      deleted: [ride],
      recorded: [],
      balances: [walletBack(books, 108, 120.5)],
    })
    expect(untouched).toBe(before)
    expect(untouchedList).toBe(listedBefore)
    expect(await listedText(books.cli)).not.toBe(listedBefore)
    expect(decode(real.stdout)).toEqual({ ...(decode(dry.stdout) as Json), dryRun: false })
  })

  it('a delete item that is not a code is refused', async () => {
    const run = await write(ledgerCli(), { delete: ['', 7, null] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        'delete[0]: is required',
        'delete[1]: is required',
        'delete[2]: is required',
      ),
    })
  })

  it("deleting any of an account's movements leaves its balance at the opening plus the rest", async () => {
    await fc.assert(
      fc.asyncProperty(bookedWithDeletes(OPENING_DATE), async ({ items, deletes }) => {
        const books = await openBooks()
        const ids = (await recordedBy(books.cli, { movements: bookedMovements(books, items) })).map(
          idOf,
        )
        const struck = [...new Set(deletes)]
        const kept = items.filter((_, index) => !struck.includes(index))
        const recordedOrder = (index: number) =>
          `${items[index]!.date}#${String(index).padStart(3, '0')}`

        const run = await write(books.cli, { delete: deletes.map((index) => ids[index]) })
        const listed = balancesById(await accountsText(books.cli))

        const shown = decode(run.stdout) as {
          deleted: { id: string }[]
          balances: { account: string; after: number }[]
        }
        const touched = struck.map((index) => books[items[index]!.account])
        expect(run.code).toBe(0)
        expect(listed[books.wallet]).toBe(totalCents(kept, 'wallet') / 100)
        expect(listed[books.savings]).toBe(totalCents(kept, 'savings') / 100)
        expect(shown.deleted.map(({ id }) => id)).toEqual(
          struck
            .toSorted((a, b) => (recordedOrder(a) < recordedOrder(b) ? -1 : 1))
            .map((index) => ids[index]),
        )
        expect(shown.balances.map(({ account }) => account)).toEqual(
          [...new Set(touched)].toSorted(),
        )
        for (const { account, after } of shown.balances) expect(after).toBe(listed[account])
        expect(decode((await list(books.cli)).stdout)).toMatchObject({ total: kept.length })
      }),
      { numRuns: 50 },
    )
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

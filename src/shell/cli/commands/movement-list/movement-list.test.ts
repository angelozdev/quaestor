import { decode, encode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import { booked, dateOnOrAfter } from '../../../../../tests/support/arbitraries/arbitraries.ts'
import { OPENING_DATE } from '../../../../../tests/support/books/books.constants.ts'
import {
  addCategory,
  bookedMovements,
  list,
  openBooks,
  spend,
  transfer,
  write,
} from '../../../../../tests/support/books/books.ts'
import type { Books, Json, Transfer } from '../../../../../tests/support/books/books.types.ts'
import { invalidInput } from '../../../../../tests/support/refusals/refusals.ts'
import type { CliRun } from '../../../../../tests/support/run-cli/run-cli.types.ts'

const NO_SUCH_CODE = 'zz99'

const LIMIT_MESSAGE = 'must be a whole number above 0'

const DATE_MESSAGE = 'must be a date like 2026-11-24'

const CENTS_PER_UNIT = 100

type Listing = { total: number; movements: Json[] }

type Account = { id: string; openingAmount: number; balance: number }

function cents(amount: unknown): number {
  return Math.round(Number(amount) * CENTS_PER_UNIT)
}

async function recordAll(books: Books, movements: Json[]): Promise<Json[]> {
  const run = await write(books.cli, { movements })
  return (decode(run.stdout) as { recorded: Json[] }).recorded
}

async function recordTransfer(books: Books, moving: Transfer): Promise<[Json, Json]> {
  const run = await write(books.cli, { transfers: [moving] })
  const [leaving, arriving] = (decode(run.stdout) as { recorded: Json[] }).recorded
  return [leaving!, arriving!]
}

function shown(run: CliRun): Listing {
  return decode(run.stdout) as Listing
}

function expectListing(run: CliRun, movements: Json[], total = movements.length): void {
  expect(run.code).toBe(0)
  expect(run.stderr).toBe('env: test\n')
  expect(run.stdout).toBe(`${encode({ total, movements })}\n`)
}

function withBalance(row: Json | undefined, balance: number): Json {
  return { ...row, balance }
}

async function accountsOf(books: Books): Promise<Account[]> {
  const { accounts } = decode((await books.cli.run(['account', 'list'])).stdout) as {
    accounts: Account[]
  }
  return accounts
}

describe('quaestor movement list', () => {
  it("movement list shows an account's movements with the balance after each (USD)", async () => {
    const books = await openBooks()
    await books.cli.run(['tag', 'add', 'trip:lima-2026'])
    await books.cli.run(['tag', 'add', 'who:alex'])
    const [ride, refund, dinner] = await recordAll(books, [
      spend(books, { date: '2026-11-20', payee: 'Uber', amount: '-12.50' }),
      spend(books, {
        date: '2026-11-21',
        payee: 'Refund',
        amount: '20',
        tags: ['who:alex', 'trip:lima-2026'],
        note: 'cambio a 4.000',
      }),
      spend(books, { date: '2026-11-22', payee: 'Dinner', amount: '-50.25' }),
      spend(books, { account: books.bank, currency: 'COP', amount: '-15000' }),
    ])

    const run = await list(books.cli, '--account', books.wallet)

    expectListing(run, [
      withBalance(dinner, 77.75),
      withBalance(refund, 128),
      withBalance(ride, 108),
    ])
    expect(refund?.tags).toBe('who:alex trip:lima-2026')
  })

  it("a transfer is listed in each account, with the other half's code and no category (USD and COP)", async () => {
    const books = await openBooks()
    const [leaving, arriving] = await recordTransfer(
      books,
      transfer(
        books,
        { amount: '-100' },
        { account: books.bank, currency: 'COP', amount: '400000' },
      ),
    )

    const everything = await list(books.cli)
    const bank = await list(books.cli, '--account', books.bank)

    expectListing(everything, [withBalance(arriving, 1400000), withBalance(leaving, 20.5)])
    expectListing(bank, [withBalance(arriving, 1400000)])
    expect(arriving?.transfer).toBe(leaving?.id)
    expect(leaving?.transfer).toBe(arriving?.id)
    expect(shown(bank).movements[0]?.category).toBeNull()
  })

  it('movement list without filters shows every account, each with its own balance', async () => {
    const books = await openBooks()
    const [ride, deposit] = await recordAll(books, [
      spend(books, { date: '2026-11-20' }),
      spend(books, { date: '2026-11-21', account: books.bank, currency: 'COP', amount: '2000' }),
    ])

    const run = await list(books.cli)

    expectListing(run, [withBalance(deposit, 1002000), withBalance(ride, 108)])
  })

  it('the balance after a movement counts the movements before --from', async () => {
    const books = await openBooks()
    const [, middle, last] = await recordAll(books, [
      spend(books, { date: '2026-11-10', amount: '-10' }),
      spend(books, { date: '2026-11-15', amount: '-5' }),
      spend(books, { date: '2026-11-20', amount: '-2.50' }),
    ])

    const run = await list(books.cli, '--from', '2026-11-15')

    expectListing(run, [withBalance(last, 103), withBalance(middle, 105.5)])
  })

  it('--from and --to keep the days in between, both included', async () => {
    const books = await openBooks()
    const [, first, second, third] = await recordAll(books, [
      spend(books, { date: '2026-11-09' }),
      spend(books, { date: '2026-11-10' }),
      spend(books, { date: '2026-11-12' }),
      spend(books, { date: '2026-11-15' }),
      spend(books, { date: '2026-11-16' }),
    ])

    const run = await list(books.cli, '--from', '2026-11-10', '--to', '2026-11-15')

    expectListing(run, [
      withBalance(third, 70.5),
      withBalance(second, 83),
      withBalance(first, 95.5),
    ])
  })

  it('a --from after --to gives no movements', async () => {
    const books = await openBooks()
    await recordAll(books, [spend(books, { date: '2026-11-21' })])

    const run = await list(books.cli, '--from', '2026-11-22', '--to', '2026-11-20')

    expectListing(run, [])
  })

  it('an unknown --account matches nothing', async () => {
    const books = await openBooks()
    await recordAll(books, [spend(books)])

    const run = await list(books.cli, '--account', NO_SUCH_CODE)

    expectListing(run, [])
  })

  it('--payee finds Éxito from exito and Uber from UBER', async () => {
    const books = await openBooks()
    const [shop, ride] = await recordAll(books, [
      spend(books, { date: '2026-11-20', payee: 'Éxito', amount: '-10' }),
      spend(books, { date: '2026-11-21', payee: 'Uber', amount: '-12.50' }),
      spend(books, { date: '2026-11-22', payee: 'Rappi', amount: '-4' }),
    ])

    const byExito = await list(books.cli, '--payee', 'exito')
    const byUber = await list(books.cli, '--payee', 'UBER')
    const byAccent = await list(books.cli, '--payee', 'ÉXITO')

    expectListing(byExito, [withBalance(shop, 110.5)])
    expectListing(byUber, [withBalance(ride, 98)])
    expectListing(byAccent, [withBalance(shop, 110.5)])
  })

  it('--payee matches any part of a payee, so uber finds Uber Eats too', async () => {
    const books = await openBooks()
    const [shop, eats, ride] = await recordAll(books, [
      spend(books, { date: '2026-11-20', payee: 'Éxito Chapinero', amount: '-10' }),
      spend(books, { date: '2026-11-21', payee: 'Uber Eats', amount: '-8' }),
      spend(books, { date: '2026-11-22', payee: 'Uber', amount: '-12.50' }),
    ])

    const rides = await list(books.cli, '--payee', 'uber')
    const shops = await list(books.cli, '--payee', 'exito chap')

    expectListing(rides, [withBalance(ride, 90), withBalance(eats, 102.5)])
    expectListing(shops, [withBalance(shop, 110.5)])
  })

  it('--payee across all accounts shows how a payee was categorised before', async () => {
    const books = await openBooks()
    const rides = await addCategory(books.cli, 'Rides')
    const [firstRide, bankRide, , lastRide] = await recordAll(books, [
      spend(books, { date: '2026-11-20', category: rides, amount: '-12.50' }),
      spend(books, {
        date: '2026-11-21',
        account: books.bank,
        currency: 'COP',
        category: rides,
        amount: '-15000',
      }),
      spend(books, { date: '2026-11-22', payee: 'Éxito', amount: '-10' }),
      spend(books, { date: '2026-11-23', amount: '-8' }),
    ])

    const run = await list(books.cli, '--payee', 'uber')

    expectListing(run, [
      withBalance(lastRide, 90),
      withBalance(bankRide, 985000),
      withBalance(firstRide, 108),
    ])
    expect([firstRide, bankRide, lastRide].map((row) => row?.category)).toEqual([
      rides,
      rides,
      books.food,
    ])
  })

  it('movements are listed newest first, and same-day ones by the reverse of their recorded order', async () => {
    const books = await openBooks()
    const [first, third, second, middle] = await recordAll(books, [
      spend(books, { date: '2026-11-20', payee: 'First', amount: '-1' }),
      spend(books, { date: '2026-11-22', payee: 'Third', amount: '-8' }),
      spend(books, { date: '2026-11-20', payee: 'Second', amount: '-2' }),
      spend(books, { date: '2026-11-21', payee: 'Middle', amount: '-4' }),
    ])

    const run = await list(books.cli)

    expectListing(run, [
      withBalance(third, 105.5),
      withBalance(middle, 113.5),
      withBalance(second, 117.5),
      withBalance(first, 119.5),
    ])
  })

  it('movements on the same day keep the order they were recorded in', async () => {
    const books = await openBooks()
    const [early, again] = await recordAll(books, [
      spend(books, { payee: 'Early', amount: '-3' }),
      spend(books, { payee: 'Again', amount: '-2' }),
    ])
    const [late] = await recordAll(books, [spend(books, { payee: 'Late', amount: '-5' })])

    const run = await list(books.cli)

    expectListing(run, [
      withBalance(late, 110.5),
      withBalance(again, 115.5),
      withBalance(early, 117.5),
    ])
  })

  it('without --limit the 50 most recent matches are listed and total counts them all', async () => {
    const books = await openBooks()
    const movements = Array.from({ length: 52 }, (_, index) =>
      spend(books, { payee: `Payee ${index + 1}`, amount: '-1' }),
    )
    await write(books.cli, { movements })

    const run = await list(books.cli)

    const { total, movements: listed } = shown(run)
    expect(run.code).toBe(0)
    expect(total).toBe(52)
    expect(listed.map(({ payee }) => payee)).toEqual(
      Array.from({ length: 50 }, (_, index) => `Payee ${52 - index}`),
    )
    expect(listed[0]?.balance).toBe(68.5)
    expect(listed[49]?.balance).toBe(117.5)
  })

  it('--limit 2 lists the 2 most recent matches', async () => {
    const books = await openBooks()
    const [, middle, last] = await recordAll(books, [
      spend(books, { date: '2026-11-20', amount: '-10' }),
      spend(books, { date: '2026-11-21', amount: '-5' }),
      spend(books, { date: '2026-11-22', amount: '-2.50' }),
    ])

    const run = await list(books.cli, '--limit', '2')

    expectListing(run, [withBalance(last, 103), withBalance(middle, 105.5)], 3)
  })

  it.for(['0', 'abc', '2.5', '1e2', ''])(
    'a --limit that is not a whole number above 0 is refused (%j)',
    async (limit) => {
      const books = await openBooks()

      const run = await list(books.cli, '--limit', limit)

      expect(run).toEqual({
        code: 1,
        stdout: '',
        stderr: invalidInput(`limit: ${LIMIT_MESSAGE}`),
      })
    },
  )

  it('a --from or --to that is not a date is refused, with every flag at fault listed', async () => {
    const books = await openBooks()

    const run = await list(books.cli, '--from', '24/11/2026', '--to', '2026-02-30', '--limit', '0')

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput(
        `from: ${DATE_MESSAGE}`,
        `to: ${DATE_MESSAGE}`,
        `limit: ${LIMIT_MESSAGE}`,
      ),
    })
  })

  it("each listed balance is the next older one of its account plus its own amount, and the newest is the account's balance", async () => {
    await fc.assert(
      fc.asyncProperty(booked(OPENING_DATE), async (items) => {
        const books = await openBooks()
        await write(books.cli, { movements: bookedMovements(books, items) })

        const { movements } = shown(await list(books.cli))

        for (const account of await accountsOf(books)) {
          const rows = movements.filter((row) => row.account === account.id)
          expect(rows.at(0)?.balance ?? account.balance).toBe(account.balance)
          rows.forEach((row, index) => {
            const older = rows[index + 1]?.balance ?? account.openingAmount
            expect(cents(row.balance)).toBe(cents(older) + cents(row.amount))
          })
        }
      }),
      { numRuns: 50 },
    )
  })

  it("--from never changes a listed movement's balance", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.tuple(booked(OPENING_DATE), dateOnOrAfter(OPENING_DATE)),
        async ([items, from]) => {
          const books = await openBooks()
          await write(books.cli, { movements: bookedMovements(books, items) })

          const everything = shown(await list(books.cli)).movements
          const fromThen = shown(await list(books.cli, '--from', from))

          const expected = everything.filter((row) => String(row.date) >= from)
          expect(fromThen.movements).toEqual(expected)
          expect(fromThen.total).toBe(expected.length)
        },
      ),
      { numRuns: 50 },
    )
  })
})

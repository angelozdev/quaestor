import { decode, encode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import { legacyRows } from '../../../../../tests/support/arbitraries/arbitraries.ts'
import { addAccount, list } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import { FIXTURE_ROWS } from '../../../../../tests/support/legacy-export/legacy-export.constants.ts'
import {
  fixtureExport,
  writeLegacyExport,
} from '../../../../../tests/support/legacy-export/legacy-export.ts'
import type { ExportRows } from '../../../../../tests/support/legacy-export/legacy-export.types.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

const CODE = /^[0-9a-hjkmnp-tv-z]{4}$/

const MS_PER_DAY = 86_400_000

const ISO_DATE_LENGTH = 10

const EXPORTED_DAY = '2026-11-24'

const COUNTS = { accounts: 5, categories: 7, tags: 2, movements: 11, tagLinks: 3 }

type Account = {
  id: string
  emoji: string | null
  name: string
  type: string
  currency: string
  archived: boolean
  openingAmount: number
  openingDate: string | null
  balance: number
}

type Category = { id: string; emoji: string | null; name: string; archived: boolean }

type Movement = {
  id: string
  date: string
  account: string
  payee: string
  amount: number
  currency: string
  category: string | null
  tags: string
  note: string | null
  transfer: string | null
  balance: number
}

function plain(name: string): string {
  return name.slice(name.indexOf(' ') + 1)
}

function named<T extends { name: string }>(rows: T[], name: string): T {
  const found = rows.find((row) => row.name === name)
  if (found === undefined) throw new Error(`no row named ${name}`)
  return found
}

async function accountsOf(cli: LedgerCli): Promise<Account[]> {
  return (decode((await cli.run(['account', 'list'])).stdout) as { accounts: Account[] }).accounts
}

async function categoriesOf(cli: LedgerCli): Promise<Category[]> {
  return (decode((await cli.run(['category', 'list'])).stdout) as { categories: Category[] })
    .categories
}

async function movementsOf(cli: LedgerCli, ...flags: string[]): Promise<Movement[]> {
  return (decode((await list(cli, ...flags)).stdout) as { movements: Movement[] }).movements
}

async function imported(flags: string[] = []) {
  const cli = ledgerCli()
  const run = await cli.run(['import', fixtureExport(), ...flags])
  return { cli, run }
}

function exportMismatch(file: string, reason: string): string {
  return `${encode({ error: { code: 'export_mismatch', file, reason, message: `${file}: ${reason}` } })}\n`
}

function dayBefore(date: string): string {
  return new Date(Date.parse(date) - MS_PER_DAY).toISOString().slice(0, ISO_DATE_LENGTH)
}

function legacyCents(rows: ExportRows, accountId: number): number {
  return rows.transactions
    .filter(({ accountId: id, status }) => id === accountId && status === 'posted')
    .reduce((sum, { type, amount }) => sum + (type === 'income' ? amount : 0 - amount), 0)
}

function firstDay(rows: ExportRows, accountId: number): string | undefined {
  return rows.transactions
    .filter(({ accountId: id, status }) => id === accountId && status === 'posted')
    .map(({ date }) => date)
    .toSorted()[0]
}

function payee(rows: Movement[], text: string): Movement {
  const found = rows.find((row) => row.payee === text)
  if (found === undefined) throw new Error(`no movement from ${text}`)
  return found
}

describe('quaestor import', () => {
  it('import brings the export over and every balance equals the export to the cent (USD and COP)', async () => {
    const { cli, run } = await imported()

    const accounts = await accountsOf(cli)

    const wallet = named(accounts, 'Wallet')
    const piggy = named(accounts, 'Piggy')
    expect(run.code).toBe(0)
    expect(run.stderr).toBe('env: test\n')
    expect(run.stdout).toBe(
      `${encode({
        dryRun: false,
        imported: COUNTS,
        openings: [
          { account: piggy.id, name: 'Piggy', amount: 50, currency: 'USD', date: '2026-11-24' },
          {
            account: wallet.id,
            name: 'Wallet',
            amount: 232.75,
            currency: 'USD',
            date: '2026-11-19',
          },
        ],
      })}\n`,
    )
    expect(accounts).toHaveLength(FIXTURE_ROWS.accounts.length)
    for (const { name, balance, currency } of FIXTURE_ROWS.accounts) {
      expect(named(accounts, plain(name))).toMatchObject({ balance: balance / 100, currency })
    }
  })

  it('an account whose balance differs from its movements gets an opening balance the day before its first movement', async () => {
    const { cli } = await imported()

    const accounts = await accountsOf(cli)

    expect(named(accounts, 'Wallet')).toMatchObject({
      openingAmount: 232.75,
      openingDate: '2026-11-19',
    })
    expect(named(accounts, 'Bank')).toMatchObject({ openingAmount: 0, openingDate: null })
    expect(named(accounts, 'Old Card')).toMatchObject({ openingAmount: 0, openingDate: null })
    expect(named(accounts, 'Piggy')).toMatchObject({ openingAmount: 50, openingDate: '2026-11-24' })
  })

  it('posted movements in an archived account are imported', async () => {
    const { cli } = await imported()
    const card = named(await accountsOf(cli), 'Old Card')

    const rows = await movementsOf(cli, '--account', card.id)

    expect(card.archived).toBe(true)
    expect(rows.map(({ payee: text, amount, balance }) => [text, amount, balance])).toEqual([
      ['Reversal', 10000, -15000],
      ['Netflix', -25000, -25000],
    ])
  })

  it('a negative expense becomes money in', async () => {
    const { cli } = await imported()

    const rows = await movementsOf(cli)

    expect(payee(rows, 'Reintegro')).toMatchObject({ amount: 500000, currency: 'COP' })
    expect(payee(rows, 'Dinner')).toMatchObject({ amount: -50.25, currency: 'USD' })
    expect(payee(rows, 'Refund')).toMatchObject({ amount: 20 })
    expect(payee(rows, 'To Bank')).toMatchObject({ amount: -100 })
    expect(payee(rows, 'From Wallet')).toMatchObject({ amount: 400000 })
  })

  it('skipped and planned rows stay in the export', async () => {
    const { cli } = await imported()

    const everything = decode((await list(cli)).stdout) as { total: number; movements: Movement[] }

    expect(everything.total).toBe(COUNTS.movements)
    const payees = everything.movements.map((row) => row.payee)
    expect(payees).not.toContain('Rent')
    expect(payees).not.toContain('Old')
  })

  it('every legacy account, category and movement gets a code, and each movement keeps its account, category, tags and transfer partner', async () => {
    const { cli } = await imported()
    const accounts = await accountsOf(cli)
    const categories = await categoriesOf(cli)

    const rows = await movementsOf(cli)

    for (const entries of [accounts, categories, rows]) {
      const codes = entries.map(({ id }) => id)
      expect(new Set(codes).size).toBe(codes.length)
      for (const code of codes) expect(code).toMatch(CODE)
    }
    const expected = [
      ['Dinner', 'Wallet', 'Restaurants', '', null],
      ['Refund', 'Wallet', 'Restaurants', 'trip:lima-2026 who:alex', null],
      ['Uber', 'Wallet', 'Rideshare/Taxi', 'trip:lima-2026', null],
      ['To Bank', 'Wallet', null, '', 'From Wallet'],
      ['From Wallet', 'Bank', null, '', 'To Bank'],
      ['Reintegro', 'Bank', 'Transfers', '', null],
      ['Salary', 'Bank', 'Salary', '', null],
      ['Almuerzo', 'Bank', 'Restaurants', '', null],
      ['Taxi', 'Bank', 'Rideshare/Taxi', '', null],
      ['Netflix', 'Old Card', 'Restaurants', '', null],
      ['Reversal', 'Old Card', 'Restaurants', '', null],
    ] as const
    expect(rows).toHaveLength(expected.length)
    for (const [text, account, category, tags, partner] of expected) {
      expect(payee(rows, text)).toMatchObject({
        account: named(accounts, account).id,
        category: category === null ? null : named(categories, category).id,
        tags,
        transfer: partner === null ? null : payee(rows, partner).id,
      })
    }
  })

  it('a legacy name splits into its emoji and its name, and a name without one keeps none', async () => {
    const { cli } = await imported()

    const accounts = await accountsOf(cli)
    const categories = (await categoriesOf(cli)).toSorted(
      (a, b) => a.name.localeCompare(b.name) || Number(a.archived) - Number(b.archived),
    )

    expect(accounts.map(({ emoji, name }) => [emoji, name])).toEqual([
      ['🏦', 'Bank'],
      ['🤝', 'Loans'],
      ['💳', 'Old Card'],
      ['🐷', 'Piggy'],
      ['💵', 'Wallet'],
    ])
    expect(categories.map(({ emoji, name, archived }) => [emoji, name, archived])).toEqual([
      ['🎁', 'Gifts', false],
      ['🎁', 'Gifts', true],
      [null, 'Misc', true],
      ['🍽️', 'Restaurants', false],
      ['🚕', 'Rideshare/Taxi', false],
      ['💰', 'Salary', false],
      ['🔁', 'Transfers', false],
    ])
  })

  it('account types and archived marks are kept as stored, and notes too, an empty one included', async () => {
    const { cli } = await imported()

    const accounts = await accountsOf(cli)
    const rows = await movementsOf(cli)

    expect(accounts.map(({ name, type, archived }) => [name, type, archived])).toEqual([
      ['Bank', 'debit', false],
      ['Loans', 'cash', false],
      ['Old Card', 'credit', true],
      ['Piggy', 'savings', false],
      ['Wallet', 'debit', false],
    ])
    expect(payee(rows, 'Dinner').note).toBe('')
    expect(payee(rows, 'Refund').note).toBe('cambio a 4.000')
    expect(payee(rows, 'Uber').note).toBeNull()
  })

  it('movements of the same day keep their legacy order', async () => {
    const { cli } = await imported()
    const bank = named(await accountsOf(cli), 'Bank')

    const rows = await movementsOf(cli, '--account', bank.id)

    expect(rows.map(({ payee: text, balance }) => [text, balance])).toEqual([
      ['Reintegro', 1850000],
      ['Taxi', 1350000],
      ['Almuerzo', 1365000],
      ['From Wallet', 1400000],
      ['Salary', 1000000],
    ])
  })

  it('import --dry-run writes nothing', async () => {
    const { cli, run } = await imported(['--dry-run'])

    const accounts = await accountsOf(cli)

    expectWrite(run, true, {
      imported: COUNTS,
      openings: [
        {
          account: expect.stringMatching(CODE),
          name: 'Piggy',
          amount: 50,
          currency: 'USD',
          date: '2026-11-24',
        },
        {
          account: expect.stringMatching(CODE),
          name: 'Wallet',
          amount: 232.75,
          currency: 'USD',
          date: '2026-11-19',
        },
      ],
    })
    expect(accounts).toEqual([])
    expect(await categoriesOf(cli)).toEqual([])
    expect((await list(cli)).stdout).toBe(`${encode({ total: 0, movements: [] })}\n`)
  })

  it('import refuses a store that already holds data', async () => {
    const cli = ledgerCli()
    await addAccount(cli, 'Savings', 'USD', '10')
    const before = await accountsOf(cli)

    const run = await cli.run(['import', fixtureExport()])

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: `env: test\n${encode({ error: { code: 'already_imported', message: 'the legacy export is imported only into an empty store' } })}\n`,
    })
    expect(await accountsOf(cli)).toEqual(before)
    expect((await list(cli)).stdout).toBe(`${encode({ total: 0, movements: [] })}\n`)
  })

  it('a file whose sha256 differs from manifest.json stops the import', async () => {
    const cli = ledgerCli()
    const folder = fixtureExport({ manifest: { transaction: { sha256: 'f'.repeat(64) } } })

    const run = await cli.run(['import', folder])

    expect(run).toEqual({
      code: 2,
      stdout: '',
      stderr: exportMismatch('tables/transaction.jsonl', 'sha256 differs from manifest.json'),
    })
    expect(await accountsOf(cli)).toEqual([])
  })

  it('a row count that differs from manifest.json stops the import', async () => {
    const cli = ledgerCli()
    const folder = fixtureExport({ manifest: { account: { rows: 6 } } })

    const run = await cli.run(['import', folder])

    expect(run).toEqual({
      code: 2,
      stdout: '',
      stderr: exportMismatch('tables/account.jsonl', 'has 5 rows, manifest.json says 6'),
    })
    expect(await accountsOf(cli)).toEqual([])
  })

  it('a table the import does not use is checked against the manifest too', async () => {
    const cli = ledgerCli()
    const folder = fixtureExport({ manifest: { settings: { rows: 0 } } })

    const run = await cli.run(['import', folder])

    expect(run).toEqual({
      code: 2,
      stdout: '',
      stderr: exportMismatch('tables/settings.jsonl', 'has 1 rows, manifest.json says 0'),
    })
  })

  it.for([
    ['transaction', '{"id":"abc"}', 'line 14: id: must be a whole number'],
    ['tag', 'not json', 'line 3: is not valid JSON'],
  ] as const)(
    'a row that does not parse stops the import before anything is written (%s)',
    async ([table, line, reason], { expect }) => {
      const cli = ledgerCli()
      const folder = fixtureExport({ extraLines: { [table]: [line] } })

      const run = await cli.run(['import', folder])

      expect(run).toEqual({
        code: 2,
        stdout: '',
        stderr: exportMismatch(`tables/${table}.jsonl`, reason),
      })
      expect(await accountsOf(cli)).toEqual([])
    },
  )

  it('a balance that cannot be held to the cent stops the import and writes nothing', async () => {
    const cli = ledgerCli()
    const income = { type: 'income', status: 'posted', categoryId: 1, accountId: 1 } as const
    const folder = writeLegacyExport({
      accounts: [
        { id: 1, name: '💵 Wallet', type: 'debit', currency: 'USD', archived: false, balance: 0 },
      ],
      categories: [{ id: 1, name: '🍽️ Food', archived: false }],
      tags: [],
      transactions: [
        {
          ...income,
          id: 1,
          date: '2026-11-20',
          payee: 'A',
          notes: null,
          amount: 9000000000000001,
          transferGroup: null,
          direction: null,
          createdAt: '2026-11-20T10:00:00',
        },
        {
          ...income,
          id: 2,
          date: '2026-11-20',
          payee: 'B',
          notes: null,
          amount: 9000000000000000,
          transferGroup: null,
          direction: null,
          createdAt: '2026-11-20T10:00:00',
        },
      ],
      tagLinks: [],
    })

    const run = await cli.run(['import', folder])

    expect(run.code).toBe(2)
    expect(run.stdout).toBe('')
    expect(decode(run.stderr.replace('env: test\n', ''))).toEqual({
      error: {
        code: 'balance_mismatch',
        account: expect.stringMatching(CODE),
        expected: 0,
        actual: expect.any(Number),
        message: expect.stringMatching(/^account \w{4} holds .+, the export says 0$/),
      },
    })
    expect(await accountsOf(cli)).toEqual([])
  })

  it("for any export, every imported balance equals the manifest's, whatever the movements (USD and COP)", async () => {
    await fc.assert(
      fc.asyncProperty(legacyRows, async (rows) => {
        const cli = ledgerCli()

        const run = await cli.run(['import', writeLegacyExport(rows)])

        const accounts = await accountsOf(cli)
        expect(run.code).toBe(0)
        expect(accounts).toHaveLength(rows.accounts.length)
        for (const { id, balance, currency } of rows.accounts) {
          const opening = balance - legacyCents(rows, id)
          const first = firstDay(rows, id)
          expect(named(accounts, `Account ${id}`)).toMatchObject({
            currency,
            balance: balance / 100,
            openingAmount: opening / 100,
            openingDate:
              opening === 0 ? null : first === undefined ? EXPORTED_DAY : dayBefore(first),
          })
        }
      }),
      { numRuns: 50 },
    )
  })
})

import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { invalidInput } from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

const RATE_MESSAGE =
  'rate: must be a rate like "3912.45": above 0, no thousands separator, at most 2 decimals'

describe('quaestor rate set', () => {
  it('rate set stores a rate and shows it before and after', async () => {
    const cli = ledgerCli()

    const first = await cli.run(['rate', 'set', 'USD', '3912.45'])
    const second = await cli.run(['rate', 'set', 'USD', '4000'])

    expect(first).toEqual({
      code: 0,
      stdout: 'dryRun: false\nrate:\n  currency: USD\n  before: null\n  after: 3912.45\n',
      stderr: 'env: test\n',
    })
    expectWrite(second, false, { rate: { currency: 'USD', before: 3912.45, after: 4000 } })
  })

  it('a rate works for any foreign currency (KRW)', async () => {
    const run = await ledgerCli().run(['rate', 'set', 'KRW', '2.85'])

    expectWrite(run, false, { rate: { currency: 'KRW', before: null, after: 2.85 } })
  })

  it('--dry-run on rate set shows the change and stores nothing', async () => {
    const cli = ledgerCli()

    const first = await cli.run(['rate', 'set', 'USD', '3912.45', '--dry-run'])
    const second = await cli.run(['rate', 'set', 'USD', '4000', '--dry-run'])

    expectWrite(first, true, { rate: { currency: 'USD', before: null, after: 3912.45 } })
    expectWrite(second, true, { rate: { currency: 'USD', before: null, after: 4000 } })
  })

  it.for(['0', '-1', '3912.455', '3.912,45'])(
    'a rate of 0, a negative one, three decimals or a thousands separator is refused (%s)',
    async (rate) => {
      const run = await ledgerCli().run(['rate', 'set', 'USD', rate])

      expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput(RATE_MESSAGE) })
    },
  )

  it('COP has no rate', async () => {
    const run = await ledgerCli().run(['rate', 'set', 'COP', '1'])

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('currency: must not be COP, the local currency'),
    })
  })

  it('a currency that is not ISO 4217 is refused', async () => {
    const run = await ledgerCli().run(['rate', 'set', 'ABC', '1'])

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('currency: must be an ISO 4217 code such as COP'),
    })
  })
})

import { decode, encode } from '@toon-format/toon'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import { amountText } from '../../../../../tests/support/arbitraries/arbitraries.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'

const CODE = /^[0-9a-hjkmnp-tv-z]{4}$/

const AMOUNT_MESSAGE =
  'must be an amount like "-15000" or "-30.39": no thousands separator, at most 2 decimals'

const WALLET_FLAGS: Record<string, string | undefined> = {
  '--emoji': '💵',
  '--type': 'debit',
  '--currency': 'USD',
  '--opening': '120.50',
  '--opening-date': '2026-01-05',
}

function addArgv(flags: Record<string, string | undefined> = {}, name = 'Wallet'): string[] {
  return [
    'account',
    'add',
    name,
    ...Object.entries({ ...WALLET_FLAGS, ...flags }).flatMap(([flag, value]) =>
      value === undefined ? [] : [flag, value],
    ),
  ]
}

function invalidInput(...issues: string[]): string {
  return `${encode({ error: { code: 'invalid_input', issues, message: issues.join('; ') } })}\n`
}

function repeatingDraw() {
  const indexes = [0, 1, 2, 3, 0, 1, 2, 3, 4, 5, 6, 7]
  let draws = 0
  return () => indexes[draws++]!
}

const WALLET = {
  id: expect.stringMatching(CODE),
  emoji: '💵',
  name: 'Wallet',
  type: 'debit',
  currency: 'USD',
  archived: false,
  openingAmount: 120.5,
  openingDate: '2026-01-05',
  balance: 120.5,
}

describe('quaestor account add', () => {
  it('an account is created with its opening balance as its balance (USD)', async () => {
    const cli = ledgerCli()

    const added = await cli.run(addArgv())
    const listed = await cli.run(['account', 'list'])

    expect(added.code).toBe(0)
    expect(added.stderr).toBe('env: test\n')
    expect(decode(added.stdout)).toEqual({ dryRun: false, account: WALLET })
    expect(decode(listed.stdout)).toEqual({ accounts: [WALLET] })
  })

  it('an account keeps its emoji apart from its name', async () => {
    const cli = ledgerCli()
    await cli.run(addArgv())

    const { stdout } = await cli.run(['account', 'list'])

    expect(decode(stdout)).toMatchObject({ accounts: [{ emoji: '💵', name: 'Wallet' }] })
  })

  it.for(['🏦🏦', 'A'])(
    'an emoji field that is not exactly one emoji is refused (%s)',
    async (emoji, { expect }) => {
      const { code, stdout, stderr } = await ledgerCli().run(addArgv({ '--emoji': emoji }))

      expect(code).toBe(1)
      expect(stdout).toBe('')
      expect(stderr).toBe(invalidInput('emoji: must be one emoji such as 🏦'))
    },
  )

  it('an account gets a four-character code', async () => {
    const { stdout } = await ledgerCli().run(addArgv())

    expect((decode(stdout) as { account: { id: string } }).account.id).toMatch(CODE)
  })

  it('two accounts never share a code, even when the draw repeats', async () => {
    const cli = ledgerCli({ randomIndex: repeatingDraw() })

    const first = await cli.run(addArgv())
    const second = await cli.run(addArgv({}, 'Cash'))
    const listed = await cli.run(['account', 'list'])

    expect(first.code).toBe(0)
    expect(second.code).toBe(0)
    expect(decode(listed.stdout)).toMatchObject({
      accounts: [
        { id: '4567', name: 'Cash' },
        { id: '0123', name: 'Wallet' },
      ],
    })
  })

  it('a credit card in debt opens with a negative balance', async () => {
    const cli = ledgerCli()

    const added = await cli.run(addArgv({ '--type': 'credit', '--opening': '-45000' }, 'Card'))
    const listed = await cli.run(['account', 'list'])

    expect(added.code).toBe(0)
    expect(decode(listed.stdout)).toMatchObject({
      accounts: [{ name: 'Card', type: 'credit', openingAmount: -45000, balance: -45000 }],
    })
  })

  it('--dry-run shows the account and leaves the store unchanged', async () => {
    const cli = ledgerCli()

    const dry = await cli.run([...addArgv(), '--dry-run'])
    const listed = await cli.run(['account', 'list'])

    expect(dry.code).toBe(0)
    expect(dry.stderr).toBe('env: test\n')
    expect(decode(dry.stdout)).toEqual({ dryRun: true, account: WALLET })
    expect(listed.stdout).toBe(`${encode({ accounts: [] })}\n`)
  })

  it('a currency that is not ISO 4217 is refused', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(addArgv({ '--currency': 'UDS' }))

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(invalidInput('currency: must be an ISO 4217 code such as COP'))
  })

  it('a type outside savings, debit, credit and cash is refused', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(addArgv({ '--type': 'checking' }))

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(invalidInput('type: must be one of savings, debit, credit or cash'))
  })

  it('an account name already taken is refused', async () => {
    const cli = ledgerCli()
    await cli.run(addArgv())

    const { code, stdout, stderr } = await cli.run(addArgv({ '--emoji': '🏦' }))
    const listed = await cli.run(['account', 'list'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: test\n${encode({
        error: {
          code: 'already_exists',
          kind: 'account',
          name: 'Wallet',
          message: 'account Wallet already exists',
        },
      })}\n`,
    )
    expect(decode(listed.stdout)).toEqual({ accounts: [WALLET] })
  })

  it.for(['15.000', '1,500'])(
    'an opening amount with a thousands separator or more than two decimals is refused (%s)',
    async (opening, { expect }) => {
      const { code, stdout, stderr } = await ledgerCli().run(addArgv({ '--opening': opening }))

      expect(code).toBe(1)
      expect(stdout).toBe('')
      expect(stderr).toBe(invalidInput(`opening: ${AMOUNT_MESSAGE}`))
    },
  )

  it('the opening date is required', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(addArgv({ '--opening-date': undefined }))

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(invalidInput('openingDate: is required'))
  })

  it('an opening date that is not a calendar day is refused', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(
      addArgv({ '--opening-date': '2026-02-30' }),
    )

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(invalidInput('openingDate: must be a date like 2026-11-24'))
  })

  it('an account name with no text is refused', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(addArgv({}, '  '))

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(invalidInput('name: is required'))
  })

  it('every invalid field is reported, in one error and in field order', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(
      addArgv({ '--type': 'checking', '--currency': 'UDS', '--opening': '1,5' }),
    )

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      invalidInput(
        'type: must be one of savings, debit, credit or cash',
        'currency: must be an ISO 4217 code such as COP',
        `opening: ${AMOUNT_MESSAGE}`,
      ),
    )
  })

  it('any opening amount written as text is read back as the same number (USD)', async () => {
    await fc.assert(
      fc.asyncProperty(amountText, async (text) => {
        const cli = ledgerCli()

        const added = await cli.run(addArgv({ '--opening': text }))
        const listed = await cli.run(['account', 'list'])

        expect(added.code).toBe(0)
        expect(decode(listed.stdout)).toMatchObject({
          accounts: [{ balance: Number(text) + 0, openingAmount: Number(text) + 0 }],
        })
      }),
      { numRuns: 50 },
    )
  })
})

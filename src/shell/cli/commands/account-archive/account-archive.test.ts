import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { addAccount } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import { alreadyExists, notFound } from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

function archive(cli: LedgerCli, code: string, ...flags: string[]) {
  return cli.run(['account', 'archive', code, ...flags])
}

function alex(id: string, archived: boolean) {
  return {
    id,
    emoji: '🏦',
    name: 'Alex',
    type: 'debit',
    currency: 'USD',
    archived,
    openingAmount: 0,
    openingDate: '2026-01-05',
    balance: 0,
  }
}

async function listed(cli: LedgerCli, ...flags: string[]) {
  return decode((await cli.run(['account', 'list', ...flags])).stdout)
}

describe('quaestor account archive', () => {
  it('account archive marks an account archived and account list shows it', async () => {
    const cli = ledgerCli()
    const id = await addAccount(cli, 'Alex', 'USD', '0')

    const run = await archive(cli, id)

    expect(run).toEqual({
      code: 0,
      stdout: `${encode({ dryRun: false, account: alex(id, true) })}\n`,
      stderr: 'env: test\n',
    })
    expect(await listed(cli)).toEqual({ accounts: [alex(id, true)] })
  })

  it('--dry-run on account archive shows it archived and changes nothing', async () => {
    const cli = ledgerCli()
    const id = await addAccount(cli, 'Alex', 'USD', '0')

    const dry = await archive(cli, id, '--dry-run')

    expectWrite(dry, true, { account: alex(id, true) })
    expect(await listed(cli)).toEqual({ accounts: [alex(id, false)] })
  })

  it('archiving an archived account changes nothing', async () => {
    const cli = ledgerCli()
    const id = await addAccount(cli, 'Alex', 'USD', '0')
    await archive(cli, id)

    const again = await archive(cli, id)

    expectWrite(again, false, { account: alex(id, true) })
  })

  it('account archive with an unknown code exits 1 as not_found', async () => {
    const run = await archive(ledgerCli(), 'zzzz')

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('account', 'zzzz') })
  })

  it('an archived account keeps its name', async () => {
    const cli = ledgerCli()
    const id = await addAccount(cli, 'Alex', 'USD', '0')
    await archive(cli, id)

    const run = await cli.run([
      'account',
      'add',
      'Alex',
      '--emoji',
      '🤝',
      '--type',
      'cash',
      '--currency',
      'COP',
      '--opening',
      '0',
      '--opening-date',
      '2026-07-02',
    ])

    expect(run).toEqual({ code: 1, stdout: '', stderr: alreadyExists('account', 'Alex') })
  })
})

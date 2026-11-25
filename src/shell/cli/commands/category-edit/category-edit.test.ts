import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { addAccount, addCategory } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import { invalidInput, notFound } from '../../../../../tests/support/refusals/refusals.ts'
import { movement, record, report } from '../../../../../tests/support/reports/reports.ts'
import type { Report } from '../../../../../tests/support/reports/reports.types.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

function addGifts(cli: LedgerCli) {
  return addCategory(cli, 'Gifts', 'Gifts', '🎁')
}

function edit(cli: LedgerCli, code: string, ...flags: string[]) {
  return cli.run(['category', 'edit', code, ...flags])
}

describe('quaestor category edit', () => {
  it('category edit moves a category to another group', async () => {
    const cli = ledgerCli()
    const gifts = await addGifts(cli)

    const run = await edit(cli, gifts, '--group', 'ex09')
    const listed = await cli.run(['category', 'list'])

    const moved = { id: gifts, group: 'ex09', emoji: '🎁', name: 'Gifts', archived: false }
    expect(run).toEqual({
      code: 0,
      stdout: `${encode({ dryRun: false, category: moved })}\n`,
      stderr: 'env: test\n',
    })
    expect(decode(listed.stdout)).toEqual({ categories: [moved] })
  })

  it('its movements count in the new group, past periods included', async () => {
    const cli = ledgerCli()
    const bank = await addAccount(cli, 'Bank', 'COP', '0')
    const gifts = await addGifts(cli)
    await record(cli, movement(bank, gifts, '2026-10-03', '-80000'))

    await edit(cli, gifts, '--group', 'ex09')
    const { groups, categories } = decode(
      (await report(cli, '2026-10-01', '2026-10-31')).stdout,
    ) as Report

    expect(groups).toEqual([
      { id: 'ex09', kind: 'spending', emoji: '🎢', name: 'Entertainment', total: 80000 },
    ])
    expect(categories).toMatchObject([{ id: gifts, group: 'ex09', total: 80000 }])
  })

  it('an unknown category or group is not_found', async () => {
    const cli = ledgerCli()
    const gifts = await addGifts(cli)

    const category = await edit(cli, 'zzzz', '--group', 'ex09')
    const group = await edit(cli, gifts, '--group', 'zzzz')

    expect(category).toEqual({ code: 1, stdout: '', stderr: notFound('category', 'zzzz') })
    expect(group).toEqual({ code: 1, stdout: '', stderr: notFound('group', 'zzzz') })
  })

  it('the group is required', async () => {
    const run = await edit(ledgerCli(), 'zzzz')

    expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput('group: is required') })
  })

  it('--dry-run changes nothing', async () => {
    const cli = ledgerCli()
    const gifts = await addGifts(cli)
    const before = await cli.run(['category', 'list'])

    const run = await edit(cli, gifts, '--group', 'ex09', '--dry-run')
    const after = await cli.run(['category', 'list'])

    expectWrite(run, true, {
      category: { id: gifts, group: 'ex09', emoji: '🎁', name: 'Gifts', archived: false },
    })
    expect(after.stdout).toBe(before.stdout)
  })
})

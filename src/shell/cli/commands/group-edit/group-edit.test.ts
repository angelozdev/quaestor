import { decode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { addAccount, addCategory, addGroup } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import {
  alreadyExists,
  invalidInput,
  notFound,
} from '../../../../../tests/support/refusals/refusals.ts'
import { movement, record, report } from '../../../../../tests/support/reports/reports.ts'
import type { Report } from '../../../../../tests/support/reports/reports.types.ts'
import { expectWrite, written } from '../../../../../tests/support/writes/writes.ts'

function edit(cli: LedgerCli, code: string, ...flags: string[]) {
  return cli.run(['group', 'edit', code, ...flags])
}

async function groupsOf(cli: LedgerCli): Promise<string> {
  return (await cli.run(['group', 'list'])).stdout
}

describe('quaestor group edit', () => {
  it('group edit renames a group and changes its emoji', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)

    const run = await edit(cli, kids, '--name', 'Children', '--emoji', '🧸')

    expect(run).toEqual(
      written({ group: { id: kids, kind: 'spending', emoji: '🧸', name: 'Children' } }),
    )
    expect(decode(await groupsOf(cli))).toMatchObject({
      groups: expect.arrayContaining([
        { id: kids, kind: 'spending', emoji: '🧸', name: 'Children' },
      ]),
    })
  })

  it('the report shows the new name', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    const bank = await addAccount(cli, 'Bank', 'COP', '0')
    const toys = await addCategory(cli, 'Toys', 'Kids', '🧸')
    await record(cli, movement(bank, toys, '2026-10-03', '-50000'))

    await edit(cli, kids, '--name', 'Children')
    const { groups } = decode((await report(cli, '2026-10-01', '2026-10-31')).stdout) as Report

    expect(groups).toEqual([
      { id: kids, kind: 'spending', emoji: '👶', name: 'Children', total: 50000 },
    ])
  })

  it('group edit with neither flag is invalid_input', async () => {
    const run = await edit(ledgerCli(), 'zyt4')

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('nothing to change: give --name, --emoji or both'),
    })
  })

  it('a name already taken is already_exists', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    const before = await groupsOf(cli)

    const run = await edit(cli, kids, '--name', 'Gifts')

    expect(run).toEqual({ code: 1, stdout: '', stderr: alreadyExists('group', 'Gifts') })
    expect(await groupsOf(cli)).toBe(before)
  })

  it('an unknown group is not_found', async () => {
    const run = await edit(ledgerCli(), 'zzzz', '--emoji', '🧸')

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('group', 'zzzz') })
  })

  it('--dry-run changes nothing', async () => {
    const cli = ledgerCli()
    const before = await groupsOf(cli)

    const run = await edit(cli, 'zyt4', '--name', 'Presents', '--dry-run')

    expectWrite(run, true, {
      group: { id: 'zyt4', kind: 'spending', emoji: '🎁', name: 'Presents' },
    })
    expect(await groupsOf(cli)).toBe(before)
  })
})

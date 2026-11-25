import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import { alreadyExists, invalidInput } from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

type Listed = { id: string; kind: string; emoji: string; name: string }

function addKids(cli: LedgerCli, ...flags: string[]) {
  return cli.run(['group', 'add', 'Kids', '--emoji', '👶', '--kind', 'spending', ...flags])
}

async function groupsOf(cli: LedgerCli): Promise<Listed[]> {
  return (decode((await cli.run(['group', 'list'])).stdout) as { groups: Listed[] }).groups
}

describe('quaestor group add', () => {
  it('group add creates a group and group list shows it among the 14', async () => {
    const cli = ledgerCli()

    const added = await addKids(cli)
    const groups = await groupsOf(cli)

    const { id } = (decode(added.stdout) as { group: { id: string } }).group
    expect(added).toEqual({
      code: 0,
      stdout: `${encode({ dryRun: false, group: { id, kind: 'spending', emoji: '👶', name: 'Kids' } })}\n`,
      stderr: 'env: test\n',
    })
    expect(groups).toHaveLength(15)
    expect(groups.slice(9, 12).map(({ name }) => name)).toEqual(['Housing', 'Kids', 'Shopping'])
    expect(groups).toContainEqual({ id, kind: 'spending', emoji: '👶', name: 'Kids' })
  })

  it('a new category can go into the new group', async () => {
    const cli = ledgerCli()
    const { id } = (decode((await addKids(cli)).stdout) as { group: { id: string } }).group

    const run = await cli.run(['category', 'add', 'Toys', '--emoji', '🧸', '--group', id])

    expect(run.code).toBe(0)
    expect(decode(run.stdout)).toMatchObject({ category: { group: id, name: 'Toys' } })
  })

  it('--dry-run on group add writes nothing', async () => {
    const cli = ledgerCli()

    const dry = await addKids(cli, '--dry-run')
    const groups = await groupsOf(cli)

    expectWrite(dry, true, {
      group: { id: expect.any(String), kind: 'spending', emoji: '👶', name: 'Kids' },
    })
    expect(groups).toHaveLength(14)
  })

  it('a name already taken is already_exists', async () => {
    const cli = ledgerCli()

    const run = await cli.run(['group', 'add', 'Gifts', '--emoji', '🎀', '--kind', 'spending'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: alreadyExists('group', 'Gifts') })
    expect(await groupsOf(cli)).toHaveLength(14)
  })

  it('the kind must be income, spending or outside', async () => {
    const run = await ledgerCli().run(['group', 'add', 'Kids', '--emoji', '👶', '--kind', 'fun'])

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: invalidInput('kind: must be one of income, spending or outside'),
    })
  })

  it.for([
    [['--emoji', 'A'], 'emoji: must be one emoji such as 🏦'],
    [[], 'emoji: is required'],
  ] as const)('the emoji is one emoji and required (%j)', async ([flags, issue]) => {
    const run = await ledgerCli().run(['group', 'add', 'Kids', '--kind', 'spending', ...flags])

    expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput(issue) })
  })
})

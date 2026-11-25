import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { addCategory, addGroup } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import { notFound } from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite, written } from '../../../../../tests/support/writes/writes.ts'

function remove(cli: LedgerCli, code: string, ...flags: string[]) {
  return cli.run(['group', 'delete', code, ...flags])
}

function notEmpty(group: string, categories: string[]): string {
  const count = categories.length
  const message = `group ${group} still holds ${count} ${count === 1 ? 'category' : 'categories'}`
  return `env: test\n${encode({ error: { code: 'group_not_empty', group, categories, message } })}\n`
}

describe('quaestor group delete', () => {
  it('group delete deletes an empty group and group list no longer shows it', async () => {
    const cli = ledgerCli()
    const approved = (await cli.run(['group', 'list'])).stdout
    const kids = await addGroup(cli)
    await cli.run(['group', 'edit', kids, '--name', 'Children', '--emoji', '🧸'])

    const run = await remove(cli, kids)
    const listed = await cli.run(['group', 'list'])

    expect(run).toEqual(
      written({ group: { id: kids, kind: 'spending', emoji: '🧸', name: 'Children' } }),
    )
    expect(listed.stdout).toBe(approved)
  })

  it('a group with a category is refused as group_not_empty', async () => {
    const cli = ledgerCli()
    const gifts = await addCategory(cli, 'Gifts', 'Gifts', '🎁')

    const run = await remove(cli, 'zyt4')

    expect(run).toEqual({ code: 1, stdout: '', stderr: notEmpty('zyt4', [gifts]) })
    expect(run.stderr).toBe(
      `env: test\nerror:\n  code: group_not_empty\n  group: zyt4\n  categories[1]: ${encode(gifts)}\n  message: group zyt4 still holds 1 category\n`,
    )
  })

  it('an archived category still holds its group', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    const toys = await addCategory(cli, 'Toys', 'Kids', '🧸')
    const books = await addCategory(cli, 'Books', 'Kids', '📚')
    await cli.run(['category', 'archive', toys])

    const run = await remove(cli, kids)

    expect(run).toEqual({ code: 1, stdout: '', stderr: notEmpty(kids, [toys, books].toSorted()) })
  })

  it('moving the category out first lets the group go', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    const toys = await addCategory(cli, 'Toys', 'Kids', '🧸')

    await cli.run(['category', 'edit', toys, '--group', 'q3rh'])
    const run = await remove(cli, kids)

    expect(run.code).toBe(0)
  })

  it("a deleted group's name can be taken again", async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    await remove(cli, kids)

    const again = await cli.run(['group', 'add', 'Kids', '--emoji', '👶', '--kind', 'spending'])

    expect(again.code).toBe(0)
    expect((decode(again.stdout) as { group: { id: string } }).group.id).not.toBe(kids)
  })

  it('a deleted group takes no new category', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    await remove(cli, kids)

    const run = await cli.run(['category', 'add', 'Toys', '--emoji', '🧸', '--group', kids])

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('group', kids) })
  })

  it('an unknown group is not_found', async () => {
    const run = await remove(ledgerCli(), 'zzzz')

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('group', 'zzzz') })
  })

  it('--dry-run deletes nothing', async () => {
    const cli = ledgerCli()
    const kids = await addGroup(cli)
    const before = (await cli.run(['group', 'list'])).stdout

    const run = await remove(cli, kids, '--dry-run')

    expectWrite(run, true, { group: { id: kids, kind: 'spending', emoji: '👶', name: 'Kids' } })
    expect((await cli.run(['group', 'list'])).stdout).toBe(before)
  })
})

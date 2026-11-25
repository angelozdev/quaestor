import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { addAccount, spend, write } from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import type { LedgerCli } from '../../../../../tests/support/ledger/ledger.types.ts'
import { notFound, refused } from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

async function addGames(cli: LedgerCli): Promise<string> {
  const { stdout } = await cli.run(['category', 'add', 'Games', '--emoji', '🎮', '--group', 'ex09'])
  return (decode(stdout) as { category: { id: string } }).category.id
}

function archive(cli: LedgerCli, code: string, ...flags: string[]) {
  return cli.run(['category', 'archive', code, ...flags])
}

function games(id: string, archived: boolean) {
  return { id, group: 'ex09', emoji: '🎮', name: 'Games', archived }
}

describe('quaestor category archive', () => {
  it('category archive marks a category archived and category list shows it', async () => {
    const cli = ledgerCli()
    const id = await addGames(cli)

    const archived = await archive(cli, id)
    const listed = await cli.run(['category', 'list'])

    expect(archived).toEqual({
      code: 0,
      stdout: `${encode({ dryRun: false, category: games(id, true) })}\n`,
      stderr: 'env: test\n',
    })
    expect(decode(listed.stdout)).toEqual({ categories: [games(id, true)] })
  })

  it('an archived category takes no new movement', async () => {
    const cli = ledgerCli()
    const wallet = await addAccount(cli, 'Wallet', 'USD', '0')
    const food = await addGames(cli)
    await archive(cli, food)

    const run = await write(cli, { movements: [spend({ wallet, food })] })

    expect(run).toEqual({
      code: 1,
      stdout: '',
      stderr: refused({
        code: 'archived',
        item: 'movements[0]',
        message: `category ${food} is archived`,
      }),
    })
  })

  it('archiving frees the name: a new active category may take it', async () => {
    const cli = ledgerCli()
    const old = await addGames(cli)
    await archive(cli, old)

    const again = await cli.run(['category', 'add', 'Games', '--emoji', '🎮', '--group', 'ex09'])
    const listed = await cli.run(['category', 'list'])

    expect(again.code).toBe(0)
    const fresh = (decode(again.stdout) as { category: { id: string } }).category.id
    expect(decode(listed.stdout)).toEqual({
      categories: [games(old, true), games(fresh, false)].toSorted((a, b) =>
        a.id < b.id ? -1 : 1,
      ),
    })
  })

  it('--dry-run on category archive shows it archived and changes nothing', async () => {
    const cli = ledgerCli()
    const id = await addGames(cli)

    const dry = await archive(cli, id, '--dry-run')
    const listed = await cli.run(['category', 'list'])

    expectWrite(dry, true, { category: games(id, true) })
    expect(decode(listed.stdout)).toEqual({ categories: [games(id, false)] })
  })

  it('category archive with an unknown code exits 1 as not_found', async () => {
    const run = await archive(ledgerCli(), 'zzzz')

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('category', 'zzzz') })
    expect(run.stderr).toBe(
      'env: test\nerror:\n  code: not_found\n  kind: category\n  value: zzzz\n  message: category zzzz does not exist\n',
    )
  })

  it('archiving a category that still holds movements is allowed', async () => {
    const cli = ledgerCli()
    const wallet = await addAccount(cli, 'Wallet', 'USD', '0')
    const food = await addGames(cli)
    await write(cli, { movements: [spend({ wallet, food })] })

    const run = await archive(cli, food)

    expectWrite(run, false, { category: games(food, true) })
  })
})

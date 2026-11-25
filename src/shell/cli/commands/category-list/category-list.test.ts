import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { missingCommand } from '../../../../../tests/support/refusals/refusals.ts'

function descendingCodes() {
  let draws = 0
  return () => {
    const first = draws % 4 === 0
    const code = Math.floor(draws / 4)
    draws += 1
    return first ? 31 - code : 0
  }
}

describe('quaestor category list', () => {
  it('category list on a fresh store prints no categories', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(['category', 'list'])

    expect(code).toBe(0)
    expect(stdout).toBe(`${encode({ categories: [] })}\n`)
    expect(stderr).toBe('env: test\n')
  })

  it('categories are listed by name', async () => {
    const cli = ledgerCli()
    await cli.run(['category', 'add', 'Rideshare', '--emoji', '🚕', '--group', 'y6v7'])
    await cli.run(['category', 'add', 'Games', '--emoji', '🎮', '--group', 'ex09'])

    const { stdout } = await cli.run(['category', 'list'])

    expect(decode(stdout)).toMatchObject({
      categories: [{ name: 'Games' }, { name: 'Rideshare' }],
    })
  })

  it('categories with the same name are listed by code', async () => {
    const cli = ledgerCli({ randomIndex: descendingCodes() })
    const { stdout: added } = await cli.run([
      'category',
      'add',
      'Gifts',
      '--emoji',
      '🎁',
      '--group',
      'zyt4',
    ])
    const first = (decode(added) as { category: { id: string } }).category.id
    await cli.run(['category', 'archive', first])
    await cli.run(['category', 'add', 'Gifts', '--emoji', '🎁', '--group', 'zyt4'])

    const { stdout } = await cli.run(['category', 'list'])

    const gifts = (decode(stdout) as { categories: { id: string; name: string }[] }).categories
      .filter(({ name }) => name === 'Gifts')
      .map(({ id }) => id)
    expect(gifts).toHaveLength(2)
    expect(gifts).toEqual(gifts.toSorted())
  })

  it('a bare group exits 1 as missing_command with its own commands', async () => {
    const run = await ledgerCli().run(['category'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: missingCommand(['list', 'add', 'archive']) })
  })
})

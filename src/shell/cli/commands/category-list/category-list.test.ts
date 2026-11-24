import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { missingCommand } from '../../../../../tests/support/refusals/refusals.ts'

describe('quaestor category list', () => {
  it('category list on a fresh store prints no categories', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(['category', 'list'])

    expect(code).toBe(0)
    expect(stdout).toBe(`${encode({ categories: [] })}\n`)
    expect(stderr).toBe('env: test\n')
  })

  it('categories are listed by name', async () => {
    const cli = ledgerCli()
    await cli.run(['category', 'add', 'Rideshare', '--emoji', '🚕'])
    await cli.run(['category', 'add', 'Games', '--emoji', '🎮'])

    const { stdout } = await cli.run(['category', 'list'])

    expect(decode(stdout)).toMatchObject({
      categories: [{ name: 'Games' }, { name: 'Rideshare' }],
    })
  })

  it('a bare group exits 1 as missing_command with its own commands', async () => {
    const run = await ledgerCli().run(['category'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: missingCommand(['list', 'add']) })
  })
})

import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { missingCommand } from '../../../../../tests/support/refusals/refusals.ts'

describe('quaestor tag list', () => {
  it('tag list on a fresh store prints no tags', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(['tag', 'list'])

    expect(code).toBe(0)
    expect(stdout).toBe(`${encode({ tags: [] })}\n`)
    expect(stderr).toBe('env: test\n')
  })

  it('tags are listed sorted', async () => {
    const cli = ledgerCli()
    await cli.run(['tag', 'add', 'who:alex'])
    await cli.run(['tag', 'add', 'trip:lima-2026'])

    const { stdout } = await cli.run(['tag', 'list'])

    expect(decode(stdout)).toEqual({ tags: ['trip:lima-2026', 'who:alex'] })
  })

  it('a bare group exits 1 as missing_command with its own commands', async () => {
    const run = await ledgerCli().run(['tag'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: missingCommand(['list', 'add']) })
  })
})

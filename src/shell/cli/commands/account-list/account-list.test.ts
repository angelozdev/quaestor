import { encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'

describe('quaestor account list', () => {
  it('account list on a fresh store prints no accounts', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(['account', 'list'])

    expect(code).toBe(0)
    expect(stdout).toBe(`${encode({ accounts: [] })}\n`)
    expect(stderr).toBe('env: test\n')
  })

  it('a bare group exits 1 as missing_command with its own commands', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(['account'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'missing_command',
          commands: ['list'],
          message: 'missing command: use one of list',
        },
      })}\n`,
    )
  })

  it('account help is not a command and exits 1 as excess_arguments', async () => {
    const { code, stdout, stderr } = await ledgerCli().run(['account', 'help'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'excess_arguments',
          message: "too many arguments for 'account'. Expected 0 arguments but got 1: help.",
        },
      })}\n`,
    )
  })
})

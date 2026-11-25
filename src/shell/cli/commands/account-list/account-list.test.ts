import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import {
  addAccount,
  addCategory,
  list,
  spend,
  write,
} from '../../../../../tests/support/books/books.ts'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'

function row(id: string, name: string, currency: string, archived: boolean, balance: number) {
  return {
    id,
    emoji: '🏦',
    name,
    type: 'debit',
    currency,
    archived,
    openingAmount: balance,
    openingDate: '2026-01-05',
    balance,
  }
}

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
          commands: ['list', 'add', 'archive'],
          message: 'missing command: use one of list, add, archive',
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

  it('account list leaves out archived accounts and --all includes them', async () => {
    const cli = ledgerCli()
    const bank = await addAccount(cli, 'Bank', 'COP', '1000000')
    const alex = await addAccount(cli, 'Alex', 'USD', '0')
    await cli.run(['account', 'archive', alex])

    const active = await cli.run(['account', 'list'])
    const all = await cli.run(['account', 'list', '--all'])

    const bankRow = row(bank, 'Bank', 'COP', false, 1000000)
    expect(active).toEqual({
      code: 0,
      stdout: `${encode({ accounts: [bankRow] })}\n`,
      stderr: 'env: test\n',
    })
    expect(all.stdout).toBe(
      `${encode({ accounts: [row(alex, 'Alex', 'USD', true, 0), bankRow] })}\n`,
    )
  })

  it('an archived account still lists its movements and still counts in report', async () => {
    const cli = ledgerCli()
    const wallet = await addAccount(cli, 'Alex', 'USD', '0')
    const food = await addCategory(cli)
    const salary = await addCategory(cli, 'Salary', 'Income', '💼')
    await write(cli, {
      movements: [
        spend({ wallet, food }, { amount: '-5' }),
        spend({ wallet, food: salary }, { amount: '5', payee: 'Acme' }),
      ],
    })
    await cli.run(['account', 'archive', wallet])
    await cli.run(['rate', 'set', 'USD', '4000'])

    const movements = await list(cli, '--account', wallet)
    const report = await cli.run(['report', '--from', '2026-11-20', '--to', '2026-11-20'])

    expect(decode(movements.stdout)).toMatchObject({ total: 2 })
    expect(decode(report.stdout)).toMatchObject({
      categories: [
        { id: salary, total: 20000, USD: 5 },
        { id: food, total: 20000, USD: 5 },
      ],
    })
  })
})

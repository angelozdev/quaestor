import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { missingCommand } from '../../../../../tests/support/refusals/refusals.ts'

const APPROVED_GROUPS = `groups[14]{id,kind,emoji,name}:
  m0z7,income,💰,Income
  y6v7,spending,🚗,Auto & Transport
  jpnq,spending,💡,Bills & Utilities
  d7gd,spending,🧠,Education
  ex09,spending,🎢,Entertainment
  3asb,spending,🧾,Financial
  1aae,spending,🍽️,Food & Dining
  zyt4,spending,🎁,Gifts
  cx75,spending,⚕️,Health & Wellness
  xwvq,spending,🏠,Housing
  q3rh,spending,🛍️,Shopping
  pjbv,spending,💻,Software & AI
  xgn8,spending,✈️,Travel
  7hdg,outside,🔄,Transfers & Investments
`

describe('quaestor group list', () => {
  it('a new store has the 14 approved groups, by kind then name', async () => {
    const run = await ledgerCli().run(['group', 'list'])

    expect(run).toEqual({ code: 0, stdout: APPROVED_GROUPS, stderr: 'env: test\n' })
  })

  it('a bare group exits 1 as missing_command with its own commands', async () => {
    const run = await ledgerCli().run(['group'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: missingCommand(['list', 'add', 'edit']) })
  })
})

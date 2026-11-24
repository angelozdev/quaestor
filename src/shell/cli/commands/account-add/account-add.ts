import { inTransaction, insertAccount } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { accountAddSchema } from './account-add.schema.ts'

export const accountAddCommand: CliCommand = {
  name: 'add',
  group: 'account',
  description: 'create an account with its opening balance',
  argument: { name: 'name', description: 'the account name, such as Wallet' },
  options: [
    { flags: '--emoji <emoji>', description: 'one emoji, such as 🏦' },
    { flags: '--type <type>', description: 'savings, debit, credit or cash' },
    { flags: '--currency <code>', description: 'an ISO 4217 code, such as COP' },
    {
      flags: '--opening <amount>',
      description: 'the balance before the first movement, as text such as "-45000.50"',
      defaultValue: '0',
    },
    { flags: '--opening-date <date>', description: 'the day of that balance, such as 2026-11-24' },
    DRY_RUN_OPTION,
  ],
  run: (context, options, args, flags) => {
    const { opening, openingDate, dryRun, ...rest } = parsed(accountAddSchema, {
      name: args[0],
      ...flags,
    })
    const draft = { ...rest, openingAmount: opening, openingDate }
    return withStore(context, options, async (store) => ({
      dryRun,
      account: inTransaction(store, dryRun, () =>
        insertAccount(store, draft, { randomIndex: context.randomIndex, now: context.clock() }),
      ),
    }))
  },
}

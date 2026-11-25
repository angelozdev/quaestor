import { listAccounts } from '#shell/db'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { accountListSchema } from './account-list.schema.ts'

export const accountListCommand: CliCommand = {
  name: 'list',
  group: 'account',
  description: 'list the active accounts with their balances',
  options: [{ flags: '--all', description: 'include archived accounts' }],
  run: (context, options, _args, flags) => {
    const { all } = parsed(accountListSchema, flags)
    return withStore(context, options, async (store) => ({
      accounts: listAccounts(store).filter((account) => all || !account.archived),
    }))
  },
}

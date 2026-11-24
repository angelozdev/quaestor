import { listAccounts } from '#shell/db'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'

export const accountListCommand: CliCommand = {
  name: 'list',
  group: 'account',
  description: 'list the accounts with their balances',
  run: (context, options) =>
    withStore(context, options, async (store) => ({ accounts: listAccounts(store) })),
}

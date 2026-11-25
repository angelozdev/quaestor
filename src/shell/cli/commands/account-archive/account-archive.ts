import { archiveAccount, inTransaction } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { accountArchiveSchema } from './account-archive.schema.ts'

export const accountArchiveCommand: CliCommand = {
  name: 'archive',
  group: 'account',
  description: 'archive an account at 0: it takes no change until unarchived',
  arguments: [{ name: 'code', description: 'the account code, from account list' }],
  options: [DRY_RUN_OPTION],
  run: (context, options, args, flags) => {
    const { code, dryRun } = parsed(accountArchiveSchema, { code: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      account: inTransaction(store, dryRun, () => archiveAccount(store, code, context.clock())),
    }))
  },
}

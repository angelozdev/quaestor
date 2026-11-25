import type { AccountRow } from '#core/ledger'
import { archiveAccount, inTransaction, unarchiveAccount, type Store } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { accountArchiveSchema } from './account-archive.schema.ts'

function markingCommand(
  name: string,
  description: string,
  mark: (store: Store, id: string, now: Date) => AccountRow,
): CliCommand {
  return {
    name,
    group: 'account',
    description,
    arguments: [{ name: 'code', description: 'the account code, from account list --all' }],
    options: [DRY_RUN_OPTION],
    run: (context, options, args, flags) => {
      const { code, dryRun } = parsed(accountArchiveSchema, { code: args[0], ...flags })
      return withStore(context, options, async (store) => ({
        dryRun,
        account: inTransaction(store, dryRun, () => mark(store, code, context.clock())),
      }))
    },
  }
}

export const accountArchiveCommand = markingCommand(
  'archive',
  'archive an account at 0: it takes no change until unarchived',
  archiveAccount,
)

export const accountUnarchiveCommand = markingCommand(
  'unarchive',
  'open an archived account again',
  unarchiveAccount,
)

import { deleteGroup, inTransaction } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { groupDeleteSchema } from './group-delete.schema.ts'

export const groupDeleteCommand: CliCommand = {
  name: 'delete',
  group: 'group',
  description: 'delete a group that holds no category, archived ones included',
  arguments: [{ name: 'code', description: 'the group code, from group list' }],
  options: [DRY_RUN_OPTION],
  run: (context, options, args, flags) => {
    const { code, dryRun } = parsed(groupDeleteSchema, { code: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      group: inTransaction(store, dryRun, () => deleteGroup(store, code, context.clock())),
    }))
  },
}

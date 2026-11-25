import { inTransaction, updateGroup } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { groupEditSchema } from './group-edit.schema.ts'

export const groupEditCommand: CliCommand = {
  name: 'edit',
  group: 'group',
  description: 'rename a group or change its emoji; its kind stays',
  arguments: [{ name: 'code', description: 'the group code, from group list' }],
  options: [
    { flags: '--name <name>', description: 'the new name in English' },
    { flags: '--emoji <emoji>', description: 'the new emoji' },
    DRY_RUN_OPTION,
  ],
  run: (context, options, args, flags) => {
    const { code, dryRun, ...change } = parsed(groupEditSchema, { code: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      group: inTransaction(store, dryRun, () => updateGroup(store, code, change, context.clock())),
    }))
  },
}

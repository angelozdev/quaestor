import { inTransaction, insertGroup } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { groupAddSchema } from './group-add.schema.ts'

export const groupAddCommand: CliCommand = {
  name: 'add',
  group: 'group',
  description: 'create a group of categories',
  arguments: [{ name: 'name', description: 'the group name in English, such as Kids' }],
  options: [
    { flags: '--emoji <emoji>', description: 'one emoji, such as 👶' },
    {
      flags: '--kind <kind>',
      description: 'income, spending or outside (counted in neither), fixed once created',
    },
    DRY_RUN_OPTION,
  ],
  run: (context, options, args, flags) => {
    const { dryRun, ...draft } = parsed(groupAddSchema, { name: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      group: inTransaction(store, dryRun, () =>
        insertGroup(store, draft, { randomIndex: context.randomIndex, now: context.clock() }),
      ),
    }))
  },
}

import { inTransaction, insertTag } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { tagAddSchema } from './tag-add.schema.ts'

export const tagAddCommand: CliCommand = {
  name: 'add',
  group: 'tag',
  description: 'create a tag',
  argument: {
    name: 'name',
    description: 'lowercase letters, digits, colons and dashes, such as trip:japon-2027',
  },
  options: [DRY_RUN_OPTION],
  run: (context, options, args, flags) => {
    const { name, dryRun } = parsed(tagAddSchema, { name: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      tag: inTransaction(store, dryRun, () => insertTag(store, name, context.clock())),
    }))
  },
}

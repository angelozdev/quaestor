import { inTransaction, setCategoryGroup } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { categoryEditSchema } from './category-edit.schema.ts'

export const categoryEditCommand: CliCommand = {
  name: 'edit',
  group: 'category',
  description: 'move a category to another group; its movements count there, past ones included',
  arguments: [{ name: 'code', description: 'the category code, from category list' }],
  options: [
    { flags: '--group <code>', description: 'its new group, from group list' },
    DRY_RUN_OPTION,
  ],
  run: (context, options, args, flags) => {
    const { code, group, dryRun } = parsed(categoryEditSchema, { code: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      category: inTransaction(store, dryRun, () =>
        setCategoryGroup(store, code, group, context.clock()),
      ),
    }))
  },
}

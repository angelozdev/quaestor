import { inTransaction, insertCategory } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { categoryAddSchema } from './category-add.schema.ts'

export const categoryAddCommand: CliCommand = {
  name: 'add',
  group: 'category',
  description: 'create a category',
  argument: { name: 'name', description: 'the category name in English, such as Restaurants' },
  options: [{ flags: '--emoji <emoji>', description: 'one emoji, such as 🍽️' }, DRY_RUN_OPTION],
  run: (context, options, args, flags) => {
    const { dryRun, ...draft } = parsed(categoryAddSchema, { name: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      category: inTransaction(store, dryRun, () =>
        insertCategory(store, draft, { randomIndex: context.randomIndex, now: context.clock() }),
      ),
    }))
  },
}

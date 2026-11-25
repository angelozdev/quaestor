import { archiveCategory, inTransaction } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { categoryArchiveSchema } from './category-archive.schema.ts'

export const categoryArchiveCommand: CliCommand = {
  name: 'archive',
  group: 'category',
  description: 'archive a category: its movements keep counting, and it takes no new ones',
  arguments: [{ name: 'code', description: 'the category code, from category list' }],
  options: [DRY_RUN_OPTION],
  run: (context, options, args, flags) => {
    const { code, dryRun } = parsed(categoryArchiveSchema, { code: args[0], ...flags })
    return withStore(context, options, async (store) => ({
      dryRun,
      category: inTransaction(store, dryRun, () => archiveCategory(store, code, context.clock())),
    }))
  },
}

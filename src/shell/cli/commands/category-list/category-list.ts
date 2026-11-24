import { listCategories } from '#shell/db'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'

export const categoryListCommand: CliCommand = {
  name: 'list',
  group: 'category',
  description: 'list the categories, archived ones included',
  run: (context, options) =>
    withStore(context, options, async (store) => ({ categories: listCategories(store) })),
}

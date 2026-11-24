import { listTags } from '#shell/db'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'

export const tagListCommand: CliCommand = {
  name: 'list',
  group: 'tag',
  description: 'list the tags',
  run: (context, options) =>
    withStore(context, options, async (store) => ({ tags: listTags(store) })),
}

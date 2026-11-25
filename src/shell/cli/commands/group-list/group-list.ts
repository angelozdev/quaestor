import { listGroups } from '#shell/db'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'

export const groupListCommand: CliCommand = {
  name: 'list',
  group: 'group',
  description: 'list the groups by kind, then by name',
  run: (context, options) =>
    withStore(context, options, async (store) => ({ groups: listGroups(store) })),
}

import { inTransaction, writeMovements } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { readJson } from '../../invocation/stdin/stdin.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { movementWriteSchema } from './movement-write.schema.ts'

export const movementWriteCommand: CliCommand = {
  name: 'write',
  group: 'movement',
  description: 'record, transfer and delete movements from JSON on stdin, all or nothing',
  options: [DRY_RUN_OPTION],
  run: async (context, options, _args, flags) => {
    const request = parsed(movementWriteSchema, await readJson(context))
    const dryRun = flags.dryRun === true
    return withStore(context, options, async (store) => ({
      dryRun,
      ...inTransaction(store, dryRun, () =>
        writeMovements(store, request, {
          randomIndex: context.randomIndex,
          now: context.clock(),
        }),
      ),
    }))
  },
}

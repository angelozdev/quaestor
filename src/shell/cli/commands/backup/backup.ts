import { backUpEnv } from '../../invocation/env-backup/env-backup.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'

export const backupCommand: CliCommand = {
  name: 'backup',
  description: "copy the current env's store to its backups folder",
  run: (context, options) =>
    withStore(context, options, (store, env) => backUpEnv(context, store, env)),
}

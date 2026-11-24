import { dirname } from 'node:path'
import { backupStore, type BackupResult, type Store } from '#shell/db'
import type { CliContext } from '../../main/main.types.ts'
import type { Env } from '../env/env.types.ts'

export function backUpEnv({ clock }: CliContext, store: Store, env: Env): Promise<BackupResult> {
  return backupStore({ store, env: env.name, root: dirname(env.dbPath), now: clock() })
}

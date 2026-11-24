import { backupStore, type BackupResult, type Store } from '#shell/db'
import type { CliContext } from '../../main/main.types.ts'
import type { Env } from '../env/env.types.ts'
import { BackupsDisabledError } from './env-backup.errors.ts'

export function backUpEnv(
  { clock, dataDir }: CliContext,
  store: Store,
  env: Env,
): Promise<BackupResult> {
  if (dataDir === null) throw new BackupsDisabledError()
  return backupStore({ store, env: env.name, root: dataDir, now: clock() })
}

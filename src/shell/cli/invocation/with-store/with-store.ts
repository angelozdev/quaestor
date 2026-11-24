import { mkdir } from 'node:fs/promises'
import { dirname } from 'node:path'
import { closeStore, openStore } from '#shell/db'
import type { CliContext, GlobalOptions } from '../../main/main.types.ts'
import { CUSTOM_ENV } from '../env/env.constants.ts'
import { resolveEnv } from '../env/env.ts'
import { writeEnvLine } from '../output/output.ts'
import type { StoreAction } from './with-store.types.ts'

export async function withStore(
  context: CliContext,
  options: GlobalOptions,
  action: StoreAction,
): Promise<unknown> {
  const env = resolveEnv({
    flag: options.env,
    vars: context.vars,
    defaultEnv: context.defaultEnv,
    dataDir: context.dataDir,
  })
  writeEnvLine(context.stderr, env)
  if (env.name !== CUSTOM_ENV) await mkdir(dirname(env.dbPath), { recursive: true })
  const store = await openStore(env.dbPath)
  try {
    return await action(store, env)
  } finally {
    closeStore(store)
  }
}

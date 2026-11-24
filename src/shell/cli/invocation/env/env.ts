import { join } from 'node:path'
import { DEFAULT_SOURCE, STORE_EXTENSION } from './env.constants.ts'
import { NamedEnvDisabledError } from './env.errors.ts'
import type { Env, EnvSources } from './env.types.ts'

export function resolveEnv({ defaultEnv, dataDir }: EnvSources): Env {
  if (dataDir === null) throw new NamedEnvDisabledError(DEFAULT_SOURCE, defaultEnv)
  return { name: defaultEnv, dbPath: join(dataDir, `${defaultEnv}${STORE_EXTENSION}`) }
}

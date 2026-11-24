import { join } from 'node:path'
import {
  CUSTOM_ENV,
  DB_VAR,
  DEFAULT_SOURCE,
  ENV_FLAG,
  ENV_VAR,
  STORE_EXTENSION,
} from './env.constants.ts'
import {
  EnvNameFormatError,
  NamedEnvDisabledError,
  RelativeDatabasePathError,
  ReservedEnvNameError,
} from './env.errors.ts'
import { dbPathSchema, envNameSchema } from './env.schema.ts'
import type { Env, EnvSources } from './env.types.ts'

function namedEnv(source: string, name: string, dataDir: string | null): Env {
  if (!envNameSchema.safeParse(name).success) throw new EnvNameFormatError(source, name)
  if (name === CUSTOM_ENV) throw new ReservedEnvNameError(source)
  if (dataDir === null) throw new NamedEnvDisabledError(source, name)
  return { name, dbPath: join(dataDir, `${name}${STORE_EXTENSION}`) }
}

function customEnv(dbPath: string): Env {
  if (!dbPathSchema.safeParse(dbPath).success) throw new RelativeDatabasePathError(dbPath)
  return { name: CUSTOM_ENV, dbPath }
}

export function resolveEnv({ flag, vars, defaultEnv, dataDir }: EnvSources): Env {
  if (flag !== undefined) return namedEnv(ENV_FLAG, flag, dataDir)
  const dbPath = vars[DB_VAR]
  if (dbPath !== undefined) return customEnv(dbPath)
  const envVar = vars[ENV_VAR]
  if (envVar !== undefined) return namedEnv(ENV_VAR, envVar, dataDir)
  return namedEnv(DEFAULT_SOURCE, defaultEnv, dataDir)
}

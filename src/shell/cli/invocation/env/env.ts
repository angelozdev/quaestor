import { statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import {
  CUSTOM_ENV,
  DB_VAR,
  DEFAULT_SOURCE,
  ENV_FLAG,
  ENV_VAR,
  INSTALLED_RELEASE,
  STORE_EXTENSION,
} from './env.constants.ts'
import {
  EnvNameFormatError,
  MissingDatabaseFolderError,
  NamedEnvDisabledError,
  RelativeDatabasePathError,
  ReservedEnvNameError,
} from './env.errors.ts'
import { dbPathSchema, envNameSchema } from './env.schema.ts'
import type { Env, EnvSources } from './env.types.ts'

function namedEnv(source: string, name: string, { dataDir, releaseOnlyEnvs }: EnvSources): Env {
  if (!envNameSchema.safeParse(name).success) throw new EnvNameFormatError(source, name)
  if (name === CUSTOM_ENV) throw new ReservedEnvNameError(source, name, DB_VAR)
  if (releaseOnlyEnvs.includes(name))
    throw new ReservedEnvNameError(source, name, INSTALLED_RELEASE)
  if (dataDir === null) throw new NamedEnvDisabledError(source, name)
  return { name, dbPath: join(dataDir, `${name}${STORE_EXTENSION}`) }
}

function customEnv(dbPath: string): Env {
  if (!dbPathSchema.safeParse(dbPath).success) throw new RelativeDatabasePathError(dbPath)
  if (!statSync(dirname(dbPath), { throwIfNoEntry: false })?.isDirectory())
    throw new MissingDatabaseFolderError(dbPath)
  return { name: CUSTOM_ENV, dbPath }
}

export function resolveEnv(sources: EnvSources): Env {
  const { flag, vars, defaultEnv } = sources
  if (flag !== undefined) return namedEnv(ENV_FLAG, flag, sources)
  const dbPath = vars[DB_VAR]
  if (dbPath !== undefined) return customEnv(dbPath)
  const envVar = vars[ENV_VAR]
  if (envVar !== undefined) return namedEnv(ENV_VAR, envVar, sources)
  return namedEnv(DEFAULT_SOURCE, defaultEnv, sources)
}

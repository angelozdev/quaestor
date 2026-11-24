import { join } from 'node:path'
import {
  DEV_VERSION,
  MIGRATIONS_FOLDER,
  RELEASE_DATA_FOLDER,
  RELEASE_DEFAULT_ENV,
  SOURCE_DATA_FOLDER,
  SOURCE_DEFAULT_ENV,
  VITEST_VAR,
} from './context.constants.ts'
import type { Vars } from '../../main/main.types.ts'
import type {
  EntryDefaults,
  InvocationContext,
  Release,
  ReleasedInvocation,
  SourceInvocation,
} from './context.types.ts'

export function releaseVersion(release: Release): string {
  return `${release.version} (${release.commit})`
}

function outsideVitest(vars: Vars, path: string): string | null {
  return vars[VITEST_VAR] ? null : path
}

function invocationContext(
  { version, defaultEnv, releaseOnlyEnvs, dataDir, migrationsDir }: EntryDefaults,
  vars: Vars,
): InvocationContext {
  return {
    version,
    vars,
    clock: () => new Date(),
    defaultEnv,
    releaseOnlyEnvs,
    dataDir: outsideVitest(vars, dataDir),
    migrationsDir,
  }
}

export function sourceContext({ repoRoot, vars }: SourceInvocation): InvocationContext {
  return invocationContext(
    {
      version: DEV_VERSION,
      defaultEnv: SOURCE_DEFAULT_ENV,
      releaseOnlyEnvs: [RELEASE_DEFAULT_ENV],
      dataDir: join(repoRoot, SOURCE_DATA_FOLDER),
      migrationsDir: join(repoRoot, MIGRATIONS_FOLDER),
    },
    vars,
  )
}

export function releasedContext({
  release,
  entryDir,
  vars,
  home,
}: ReleasedInvocation): InvocationContext {
  return invocationContext(
    {
      version: releaseVersion(release),
      defaultEnv: RELEASE_DEFAULT_ENV,
      releaseOnlyEnvs: [],
      dataDir: join(home, RELEASE_DATA_FOLDER),
      migrationsDir: join(entryDir, '..', MIGRATIONS_FOLDER),
    },
    vars,
  )
}

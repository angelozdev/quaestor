import { join } from 'node:path'
import {
  DEV_VERSION,
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
  { version, defaultEnv, dataDir }: EntryDefaults,
  vars: Vars,
): InvocationContext {
  return {
    version,
    vars,
    clock: () => new Date(),
    defaultEnv,
    dataDir: outsideVitest(vars, dataDir),
  }
}

export function sourceContext({ repoRoot, vars }: SourceInvocation): InvocationContext {
  return invocationContext(
    {
      version: DEV_VERSION,
      defaultEnv: SOURCE_DEFAULT_ENV,
      dataDir: join(repoRoot, SOURCE_DATA_FOLDER),
    },
    vars,
  )
}

export function releasedContext({ release, vars, home }: ReleasedInvocation): InvocationContext {
  return invocationContext(
    {
      version: releaseVersion(release),
      defaultEnv: RELEASE_DEFAULT_ENV,
      dataDir: join(home, RELEASE_DATA_FOLDER),
    },
    vars,
  )
}

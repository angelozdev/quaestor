import type { CliContext, Vars } from '../../main/main.types.ts'

export type Release = { version: string; commit: string; repoRoot: string }

type Invocation = { vars: Vars }

export type SourceInvocation = Invocation & { repoRoot: string }

export type ReleasedInvocation = Invocation & { release: Release; entryDir: string; home: string }

export type EntryDefaults = {
  version: string
  defaultEnv: string
  releaseOnlyEnvs: string[]
  dataDir: string
  migrationsDir: string
}

export type InvocationContext = Omit<CliContext, 'stdout' | 'stderr'>

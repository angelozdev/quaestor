import type { CliContext } from '../../main/main.types.ts'

export type Release = { version: string; commit: string; repoRoot: string }

export type SourceInvocation = { repoRoot: string }

export type ReleasedInvocation = { release: Release; entryDir: string }

export type InvocationContext = Omit<CliContext, 'stdout' | 'stderr'>

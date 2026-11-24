import type { CliContext } from '#shell/cli'

export type CliOverrides = Partial<Omit<CliContext, 'stdout' | 'stderr'>>

export type CliRun = { code: number; stdout: string; stderr: string }

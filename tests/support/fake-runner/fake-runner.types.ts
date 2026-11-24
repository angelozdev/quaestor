import type { RunOptions, RunResult } from '#shell/release'

export type RunCall = { command: string; args: string[] } & RunOptions

export type FakeResponses = Record<string, Partial<RunResult>>

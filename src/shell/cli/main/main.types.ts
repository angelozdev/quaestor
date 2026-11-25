import type { RandomIndex } from '#core/ledger'
import type { COMMAND_GROUPS } from './main.constants.ts'

export type Output = { write(chunk: string): unknown }

export type Vars = Record<string, string | undefined>

type Clock = () => Date

export type CliContext = {
  stdout: Output
  stderr: Output
  version: string
  vars: Vars
  clock: Clock
  randomIndex: RandomIndex
  stdin: () => Promise<string>
  defaultEnv: string
  releaseOnlyEnvs: string[]
  dataDir: string | null
  migrationsDir: string
}

export type GlobalOptions = { env?: string; json?: boolean }

export type CommandGroup = keyof typeof COMMAND_GROUPS

type Flags = Record<string, string | boolean | undefined>

export type CliCommand = {
  name: string
  description: string
  group?: CommandGroup
  arguments?: { name: string; description: string }[]
  options?: { flags: string; description: string; defaultValue?: string }[]
  run(context: CliContext, options: GlobalOptions, args: string[], flags: Flags): Promise<unknown>
}

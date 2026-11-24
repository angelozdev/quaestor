export type Output = { write(chunk: string): unknown }

export type Vars = Record<string, string | undefined>

type Clock = () => Date

export type CliContext = {
  stdout: Output
  stderr: Output
  version: string
  vars: Vars
  clock: Clock
  defaultEnv: string
  dataDir: string | null
}

export type GlobalOptions = { env?: string; json?: boolean }

export type CliCommand = {
  name: string
  description: string
  run(context: CliContext, options: GlobalOptions): Promise<unknown>
}

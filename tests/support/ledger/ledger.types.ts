import type { CliRun } from '../run-cli/run-cli.types.ts'

export type LedgerCli = {
  dataDir: string
  run(argv: string[], stdin?: string): Promise<CliRun>
}

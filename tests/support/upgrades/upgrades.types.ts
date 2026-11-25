import type { CliRun } from '../run-cli/run-cli.types.ts'

export type UpgradeCli = {
  before(argv: string[]): Promise<CliRun>
  after(argv: string[]): Promise<CliRun>
}

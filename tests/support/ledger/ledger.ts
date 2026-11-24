import { SHIPPED_MIGRATIONS } from '../fixture-migrations/fixture-migrations.constants.ts'
import { runCli } from '../run-cli/run-cli.ts'
import type { CliRun } from '../run-cli/run-cli.types.ts'
import { tempDir } from '../temp-dir/temp-dir.ts'
import { WARM_UP_ARGV } from './ledger.constants.ts'
import type { LedgerCli } from './ledger.types.ts'

export function ledgerCli(): LedgerCli {
  const dataDir = tempDir('quaestor-ledger-')
  let migrated: Promise<CliRun> | undefined
  const cli = (argv: string[]) =>
    runCli(argv, { dataDir, defaultEnv: 'test', migrationsDir: SHIPPED_MIGRATIONS })
  return {
    dataDir,
    async run(argv) {
      migrated ??= cli(WARM_UP_ARGV)
      await migrated
      return cli(argv)
    },
  }
}

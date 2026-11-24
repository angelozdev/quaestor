import { SHIPPED_MIGRATIONS } from '../fixture-migrations/fixture-migrations.constants.ts'
import { runCli } from '../run-cli/run-cli.ts'
import type { CliOverrides } from '../run-cli/run-cli.types.ts'
import { tempDir } from '../temp-dir/temp-dir.ts'
import { WARM_UP_ARGV } from './ledger.constants.ts'
import type { LedgerCli } from './ledger.types.ts'

export function ledgerCli(overrides: CliOverrides = {}): LedgerCli {
  const dataDir = tempDir('quaestor-ledger-')
  let migrated: Promise<void> | undefined
  const cli = (argv: string[]) =>
    runCli(argv, { dataDir, defaultEnv: 'test', migrationsDir: SHIPPED_MIGRATIONS, ...overrides })
  const warmUp = async () => {
    const { code, stderr } = await cli(WARM_UP_ARGV)
    if (code !== 0) throw new Error(`the warm-up exited ${code}: ${stderr}`)
  }
  return {
    dataDir,
    async run(argv) {
      migrated ??= warmUp()
      await migrated
      return cli(argv)
    },
  }
}

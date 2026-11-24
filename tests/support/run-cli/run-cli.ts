import { ID_LENGTH, type RandomIndex } from '#core/ledger'
import { main } from '#shell/cli'
import { noMigrations } from '../fixture-migrations/fixture-migrations.ts'
import { captureStream } from '../streams/streams.ts'
import { FIXED_INSTANT } from './run-cli.constants.ts'
import type { CliOverrides, CliRun } from './run-cli.types.ts'

function sequentialIndex(): RandomIndex {
  let draws = 0
  return (bound) => {
    const code = Math.floor(draws / ID_LENGTH)
    const place = ID_LENGTH - 1 - (draws++ % ID_LENGTH)
    return Math.floor(code / bound ** place) % bound
  }
}

export async function runCli(argv: string[], overrides: CliOverrides = {}): Promise<CliRun> {
  const stdout = captureStream()
  const stderr = captureStream()
  const code = await main(argv, {
    version: 'dev',
    vars: {},
    clock: () => new Date(FIXED_INSTANT),
    randomIndex: sequentialIndex(),
    defaultEnv: 'test',
    releaseOnlyEnvs: [],
    dataDir: null,
    stdin: () => Promise.resolve(''),
    ...overrides,
    migrationsDir: overrides.migrationsDir ?? noMigrations(),
    stdout,
    stderr,
  })
  return { code, stdout: stdout.text(), stderr: stderr.text() }
}

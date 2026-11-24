import { Command, CommanderError } from '@commander-js/extra-typings'
import { failureOf } from '../invocation/failure/failure.ts'
import { writeFailure } from '../invocation/output/output.ts'
import { ExitCode, JSON_FLAG } from './main.constants.ts'
import type { CliContext } from './main.types.ts'

function program(context: CliContext) {
  return new Command('quaestor')
    .version(context.version, '-V, --version')
    .option('--env <name>', 'use <name>.sqlite in the data folder')
    .option(JSON_FLAG, 'JSON instead of TOON on stdout')
    .exitOverride()
    .configureOutput({
      writeOut: (text) => context.stdout.write(text),
      writeErr: (text) => context.stderr.write(text),
      outputError: () => undefined,
    })
}

export async function main(argv: string[], context: CliContext): Promise<number> {
  try {
    await program(context).parseAsync(argv, { from: 'user' })
    return ExitCode.Success
  } catch (error) {
    if (error instanceof CommanderError && error.exitCode === ExitCode.Success)
      return ExitCode.Success
    const { exitCode, payload } = failureOf(error)
    writeFailure(context.stderr, payload, argv.includes(JSON_FLAG))
    return exitCode
  }
}

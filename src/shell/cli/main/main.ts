import { Command, CommanderError } from '@commander-js/extra-typings'
import type { CliContext } from './main.types.ts'

function program(context: CliContext) {
  return new Command('quaestor')
    .version(context.version, '-V, --version')
    .option('--env <name>', 'use <name>.sqlite in the data folder')
    .option('--json', 'JSON instead of TOON on stdout')
    .exitOverride()
    .configureOutput({
      writeOut: (text) => context.stdout.write(text),
      writeErr: (text) => context.stderr.write(text),
    })
}

export async function main(argv: string[], context: CliContext): Promise<number> {
  try {
    await program(context).parseAsync(argv, { from: 'user' })
    return 0
  } catch (error) {
    if (error instanceof CommanderError && error.exitCode === 0) return 0
    throw error
  }
}

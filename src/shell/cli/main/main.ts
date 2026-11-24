import { Command, CommanderError } from '@commander-js/extra-typings'
import { backupCommand } from '../commands/backup/backup.ts'
import { failureOf } from '../invocation/failure/failure.ts'
import { writeFailure, writeResult } from '../invocation/output/output.ts'
import { ExitCode, HELP_FLAG, JSON_FLAG } from './main.constants.ts'
import type { CliCommand, CliContext } from './main.types.ts'

const COMMANDS: CliCommand[] = [backupCommand]

function ignore(): void {}

function program(context: CliContext) {
  return new Command('quaestor')
    .version(context.version, '-V, --version')
    .option('--env <name>', 'use <name>.sqlite in the data folder')
    .option(JSON_FLAG, 'JSON instead of TOON on stdout')
    .exitOverride()
    .configureOutput({
      writeOut: (text) => context.stdout.write(text),
      writeErr: ignore,
      outputError: ignore,
    })
}

type Program = ReturnType<typeof program>

function register(root: Program, context: CliContext, command: CliCommand): void {
  root
    .command(command.name)
    .description(command.description)
    .action(async () => {
      const options = root.opts()
      const result = await command.run(context, options)
      writeResult(context.stdout, result, options.json === true)
    })
}

export async function main(argv: string[], context: CliContext): Promise<number> {
  const root = program(context)
  for (const command of COMMANDS) register(root, context, command)
  try {
    await root.parseAsync(argv.length === 0 ? [HELP_FLAG] : argv, { from: 'user' })
    return ExitCode.Success
  } catch (error) {
    if (error instanceof CommanderError && error.exitCode === ExitCode.Success)
      return ExitCode.Success
    const { exitCode, payload } = failureOf(error)
    writeFailure(context.stderr, payload, argv.includes(JSON_FLAG))
    return exitCode
  }
}

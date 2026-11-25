import { Command, CommanderError, Option } from '@commander-js/extra-typings'
import { accountAddCommand } from '../commands/account-add/account-add.ts'
import { accountListCommand } from '../commands/account-list/account-list.ts'
import { backupCommand } from '../commands/backup/backup.ts'
import { categoryAddCommand } from '../commands/category-add/category-add.ts'
import { categoryArchiveCommand } from '../commands/category-archive/category-archive.ts'
import { categoryListCommand } from '../commands/category-list/category-list.ts'
import { groupListCommand } from '../commands/group-list/group-list.ts'
import { movementListCommand } from '../commands/movement-list/movement-list.ts'
import { movementWriteCommand } from '../commands/movement-write/movement-write.ts'
import { rateSetCommand } from '../commands/rate-set/rate-set.ts'
import { reportCommand } from '../commands/report/report.ts'
import { tagAddCommand } from '../commands/tag-add/tag-add.ts'
import { tagListCommand } from '../commands/tag-list/tag-list.ts'
import { failureOf } from '../invocation/failure/failure.ts'
import { MissingCommandError } from '../invocation/failure/failure.errors.ts'
import { writeFailure, writeResult } from '../invocation/output/output.ts'
import { COMMAND_GROUPS, ExitCode, HELP_FLAG, JSON_FLAG } from './main.constants.ts'
import type { CliCommand, CliContext, CommandGroup } from './main.types.ts'

const COMMANDS: CliCommand[] = [
  backupCommand,
  accountListCommand,
  accountAddCommand,
  groupListCommand,
  categoryListCommand,
  categoryAddCommand,
  categoryArchiveCommand,
  tagListCommand,
  tagAddCommand,
  movementListCommand,
  movementWriteCommand,
  reportCommand,
  rateSetCommand,
]

const COMMAND_NAMES = [...new Set(COMMANDS.map((command) => command.group ?? command.name))]

function ignore(): void {}

function program(context: CliContext) {
  return new Command('quaestor')
    .version(context.version, '-V, --version')
    .option('--env <name>', 'use <name>.sqlite in the data folder')
    .option(JSON_FLAG, 'JSON instead of TOON on stdout')
    .helpCommand(false)
    .exitOverride()
    .configureOutput({
      writeOut: (text) => context.stdout.write(text),
      writeErr: ignore,
      outputError: ignore,
    })
}

type Program = ReturnType<typeof program>

function registerGroup(root: Program, group: CommandGroup) {
  const names = COMMANDS.filter((command) => command.group === group).map(({ name }) => name)
  return root
    .command(group)
    .description(COMMAND_GROUPS[group])
    .helpCommand(false)
    .action(() => {
      throw new MissingCommandError(names)
    })
}

type Parent = Program | ReturnType<typeof registerGroup>

function register(root: Program, context: CliContext, parent: Parent, command: CliCommand): void {
  const subcommand = parent.command(command.name).description(command.description)
  for (const { name, description } of command.arguments ?? [])
    subcommand.argument(`<${name}>`, description)
  for (const { flags, description, defaultValue } of command.options ?? [])
    subcommand.addOption(new Option(flags, description).default(defaultValue))
  subcommand.action(async () => {
    const options = root.opts()
    const result = await command.run(context, options, subcommand.args, subcommand.opts())
    writeResult(context.stdout, result, options.json === true)
  })
}

function parentOf(root: Program, groups: Map<CommandGroup, Parent>, group?: CommandGroup): Parent {
  if (group === undefined) return root
  const parent = groups.get(group) ?? registerGroup(root, group)
  groups.set(group, parent)
  return parent
}

function registerAll(root: Program, context: CliContext): void {
  const groups = new Map<CommandGroup, Parent>()
  for (const command of COMMANDS)
    register(root, context, parentOf(root, groups, command.group), command)
}

export async function main(argv: string[], context: CliContext): Promise<number> {
  const root = program(context)
  registerAll(root, context)
  try {
    await root.parseAsync(argv.length === 0 ? [HELP_FLAG] : argv, { from: 'user' })
    return ExitCode.Success
  } catch (error) {
    if (error instanceof CommanderError && error.exitCode === ExitCode.Success)
      return ExitCode.Success
    const { exitCode, payload } = failureOf(error, COMMAND_NAMES)
    writeFailure(context.stderr, payload, argv.includes(JSON_FLAG))
    return exitCode
  }
}

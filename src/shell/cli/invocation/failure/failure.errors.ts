import { RefusedError } from '#core/errors'
import { COMMAND_LIST_SEPARATOR } from './failure.constants.ts'

export class MissingCommandError extends RefusedError {
  constructor(commands: string[]) {
    super(
      'missing_command',
      `missing command: use one of ${commands.join(COMMAND_LIST_SEPARATOR)}`,
      { commands },
    )
  }
}

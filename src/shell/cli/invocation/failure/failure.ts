import { CommanderError } from '@commander-js/extra-typings'
import { FailedError, RefusedError } from '#core/errors'
import { ExitCode } from '../../main/main.constants.ts'
import {
  CAMEL_CASE_BOUNDARY,
  COMMANDER_CODE_PREFIX,
  COMMANDER_MESSAGE_PREFIX,
  HELP_ERROR_CODE,
  UNEXPECTED_CODE,
} from './failure.constants.ts'
import { MissingCommandError } from './failure.errors.ts'
import type { Failure } from './failure.types.ts'

function usageCode(commanderCode: string): string {
  return commanderCode
    .replace(COMMANDER_CODE_PREFIX, '')
    .replace(CAMEL_CASE_BOUNDARY, (letter) => `_${letter.toLowerCase()}`)
}

function usageFailure(error: CommanderError): Failure {
  return {
    exitCode: ExitCode.Refused,
    payload: {
      error: {
        code: usageCode(error.code),
        message: error.message.replace(COMMANDER_MESSAGE_PREFIX, ''),
      },
    },
  }
}

function codedFailure(
  exitCode: number,
  { code, data, message }: RefusedError | FailedError,
): Failure {
  return { exitCode, payload: { error: { code, ...data, message } } }
}

function unexpectedFailure(error: unknown): Failure {
  const message = error instanceof Error ? error.message : String(error)
  return {
    exitCode: ExitCode.Failed,
    payload: { error: { code: UNEXPECTED_CODE, message } },
  }
}

function isMissingCommand(error: CommanderError): boolean {
  return error.code === HELP_ERROR_CODE && error.exitCode === ExitCode.Refused
}

export function failureOf(error: unknown, commands: string[]): Failure {
  if (error instanceof CommanderError)
    return isMissingCommand(error)
      ? codedFailure(ExitCode.Refused, new MissingCommandError(commands))
      : usageFailure(error)
  if (error instanceof RefusedError) return codedFailure(ExitCode.Refused, error)
  if (error instanceof FailedError) return codedFailure(ExitCode.Failed, error)
  return unexpectedFailure(error)
}

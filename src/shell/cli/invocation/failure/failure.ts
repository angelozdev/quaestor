import { CommanderError } from '@commander-js/extra-typings'
import { RefusedError } from '#core/errors'
import { ExitCode } from '../../main/main.constants.ts'
import {
  CAMEL_CASE_BOUNDARY,
  COMMANDER_CODE_PREFIX,
  COMMANDER_MESSAGE_PREFIX,
  UNEXPECTED_CODE,
} from './failure.constants.ts'
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

function refusedFailure({ code, data, message }: RefusedError): Failure {
  return { exitCode: ExitCode.Refused, payload: { error: { code, ...data, message } } }
}

function unexpectedFailure(error: unknown): Failure {
  const message = error instanceof Error ? error.message : String(error)
  return {
    exitCode: ExitCode.Failed,
    payload: { error: { code: UNEXPECTED_CODE, message } },
  }
}

export function failureOf(error: unknown): Failure {
  if (error instanceof CommanderError) return usageFailure(error)
  if (error instanceof RefusedError) return refusedFailure(error)
  return unexpectedFailure(error)
}

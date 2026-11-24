import { CommanderError } from '@commander-js/extra-typings'
import { ExitCode } from '../../main/main.constants.ts'
import {
  CAMEL_CASE_BOUNDARY,
  COMMANDER_CODE_PREFIX,
  COMMANDER_MESSAGE_PREFIX,
} from './failure.constants.ts'
import type { Failure } from './failure.types.ts'

function usageCode(commanderCode: string): string {
  return commanderCode
    .replace(COMMANDER_CODE_PREFIX, '')
    .replace(CAMEL_CASE_BOUNDARY, (letter) => `_${letter.toLowerCase()}`)
}

export function failureOf(error: unknown): Failure {
  if (!(error instanceof CommanderError)) throw error
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

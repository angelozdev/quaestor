import { RefusedError } from '#core/errors'
import { INVALID_JSON_PREFIX, SINGLE_SPACE, WHITESPACE_RUN } from './stdin.constants.ts'

export class InvalidJsonError extends RefusedError {
  constructor(reason: string) {
    super('invalid_json', `${INVALID_JSON_PREFIX}${reason.replace(WHITESPACE_RUN, SINGLE_SPACE)}`)
  }
}

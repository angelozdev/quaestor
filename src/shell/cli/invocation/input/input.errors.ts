import { RefusedError } from '#core/errors'
import { ISSUE_SEPARATOR } from './input.constants.ts'

export class InvalidInputError extends RefusedError {
  constructor(issues: string[]) {
    super('invalid_input', issues.join(ISSUE_SEPARATOR), { issues })
  }
}

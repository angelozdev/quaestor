import { RefusedError } from '#core/errors'
import type { WriteProblem } from './ledger.types.ts'

export class AlreadyExistsError extends RefusedError {
  constructor(kind: string, name: string) {
    super('already_exists', `${kind} ${name} already exists`, { kind, name })
  }
}

export class NotFoundError extends RefusedError {
  constructor(kind: string, value: string) {
    super('not_found', `${kind} ${value} does not exist`, { kind, value })
  }
}

export class RefusedWriteError extends RefusedError {
  constructor(problems: WriteProblem[]) {
    super('refused', `${problems.length} ${problems.length === 1 ? 'item' : 'items'} refused`, {
      errors: problems,
    })
  }
}

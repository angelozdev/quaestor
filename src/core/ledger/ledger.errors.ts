import { RefusedError } from '#core/errors'

export class AlreadyExistsError extends RefusedError {
  constructor(kind: string, name: string) {
    super('already_exists', `${kind} ${name} already exists`, { kind, name })
  }
}

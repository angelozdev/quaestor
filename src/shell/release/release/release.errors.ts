import { TRUNK_BRANCH } from './release.constants.ts'

export class ReleaseError extends Error {
  constructor(message: string) {
    super(message)
    this.name = new.target.name
  }
}

class ReleaseRefusedError extends ReleaseError {
  constructor(reason: string) {
    super(`release: refused: ${reason}`)
  }
}

export class NotOnTrunkError extends ReleaseRefusedError {
  readonly branch: string

  constructor(branch: string) {
    super(`on ${branch}, not ${TRUNK_BRANCH}`)
    this.branch = branch
  }
}

export class UncommittedChangesError extends ReleaseRefusedError {
  constructor() {
    super('uncommitted changes')
  }
}

export class CheckFailedError extends ReleaseRefusedError {
  readonly check: string

  constructor(check: string) {
    super(`${check} failed`)
    this.check = check
  }
}

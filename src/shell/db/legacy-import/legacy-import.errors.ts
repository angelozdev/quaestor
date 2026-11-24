import { FailedError, RefusedError } from '#core/errors'

export class AlreadyImportedError extends RefusedError {
  constructor() {
    super('already_imported', 'the legacy export is imported only into an empty store')
  }
}

export class BalanceMismatchError extends FailedError {
  constructor(account: string, expected: number, actual: number) {
    super('balance_mismatch', `account ${account} holds ${actual}, the export says ${expected}`, {
      account,
      expected,
      actual,
    })
  }
}

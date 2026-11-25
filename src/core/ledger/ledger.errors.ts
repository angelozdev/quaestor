import { RefusedError } from '#core/errors'
import type { WriteProblem } from './ledger.types.ts'

export class AlreadyExistsError extends RefusedError {
  constructor(kind: string, name: string) {
    super('already_exists', `${kind} ${name} already exists`, { kind, name })
  }
}

export class BalanceNotZeroError extends RefusedError {
  constructor(account: string, currency: string, balance: number) {
    super(
      'balance_not_zero',
      `account ${account} holds ${balance} ${currency}; only an account at 0 can be archived`,
      { account, currency, balance },
    )
  }
}

export class GroupNotEmptyError extends RefusedError {
  constructor(group: string, categories: string[]) {
    const count = categories.length
    super(
      'group_not_empty',
      `group ${group} still holds ${count} ${count === 1 ? 'category' : 'categories'}`,
      { group, categories },
    )
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

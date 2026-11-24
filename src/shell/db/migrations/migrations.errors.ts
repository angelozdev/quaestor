import { FailedError } from '#core/errors'

export class MigrationFailedError extends FailedError {
  constructor(migration: string, cause: Error) {
    super('migration_failed', `migration ${migration} failed: ${cause.message}`, {
      migration,
      reason: cause.message,
    })
  }
}

export class UnknownMigrationsError extends FailedError {
  constructor(names: string[]) {
    super(
      'unknown_migrations',
      `the store has migrations this code does not know: ${names.join(', ')}`,
      { names },
    )
  }
}

import { RefusedError } from '#core/errors'
import { CUSTOM_ENV, DB_VAR } from './env.constants.ts'

class InvalidEnvError extends RefusedError {
  constructor(source: string, value: string, problem: string) {
    super('invalid_env', `invalid ${source} "${value}": ${problem}`, { source, value })
  }
}

export class EnvNameFormatError extends InvalidEnvError {
  constructor(source: string, value: string) {
    super(source, value, 'use lowercase letters, digits and dashes')
  }
}

export class ReservedEnvNameError extends InvalidEnvError {
  constructor(source: string) {
    super(source, CUSTOM_ENV, `${CUSTOM_ENV} is reserved for ${DB_VAR}`)
  }
}

export class RelativeDatabasePathError extends InvalidEnvError {
  constructor(value: string) {
    super(DB_VAR, value, 'must be an absolute path')
  }
}

export class NamedEnvDisabledError extends RefusedError {
  constructor(source: string, env: string) {
    super(
      'named_env_disabled',
      `named environments are disabled here (${source}: ${env}); set ${DB_VAR} to a temporary file`,
      { source, env },
    )
  }
}

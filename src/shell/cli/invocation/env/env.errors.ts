import { RefusedError } from '#core/errors'
import { DB_VAR } from './env.constants.ts'

class InvalidEnvError extends RefusedError {
  constructor(source: string, value: string, problem: string) {
    super('invalid_env', `invalid ${source} "${value}": ${problem}`, { source, value })
  }
}

export class EnvNameFormatError extends InvalidEnvError {
  constructor(source: string, value: string) {
    super(
      source,
      value,
      'start with a lowercase letter, then use lowercase letters, digits and dashes',
    )
  }
}

export class ReservedEnvNameError extends InvalidEnvError {
  constructor(source: string, name: string, owner: string) {
    super(source, name, `${name} is reserved for ${owner}`)
  }
}

export class RelativeDatabasePathError extends InvalidEnvError {
  constructor(value: string) {
    super(DB_VAR, value, 'must be an absolute path')
  }
}

export class MissingDatabaseFolderError extends InvalidEnvError {
  constructor(value: string) {
    super(DB_VAR, value, 'its folder does not exist')
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

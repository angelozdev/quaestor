import { RefusedError } from '#core/errors'
import { DB_VAR } from './env.constants.ts'

export class NamedEnvDisabledError extends RefusedError {
  constructor(source: string, env: string) {
    super(
      'named_env_disabled',
      `named environments are disabled here (${source}: ${env}); set ${DB_VAR} to a temporary file`,
      { source, env },
    )
  }
}

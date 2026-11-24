import { RefusedError } from '#core/errors'

export class BackupsDisabledError extends RefusedError {
  constructor() {
    super('backups_disabled', 'backups are disabled here (under vitest)')
  }
}

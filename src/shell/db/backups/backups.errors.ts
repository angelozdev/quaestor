import { FailedError } from '#core/errors'

export class BackupNotWrittenError extends FailedError {
  constructor(folder: string, cause: Error) {
    super('backup_not_written', `cannot write backup to ${folder}: ${cause.message}`, {
      folder,
      reason: cause.message,
    })
  }
}

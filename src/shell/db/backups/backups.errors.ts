import { FailedError } from '#core/errors'

export class BackupNotWrittenError extends FailedError {
  constructor(folder: string, reason: string) {
    super('backup_not_written', `cannot write backup to ${folder}: ${reason}`, { folder, reason })
  }
}

export class BackupAlreadyExistsError extends BackupNotWrittenError {
  constructor(folder: string, name: string) {
    super(folder, `${name} already exists`)
  }
}

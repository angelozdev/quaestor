import { FailedError } from '#core/errors'

export class ExportMismatchError extends FailedError {
  constructor(file: string, reason: string) {
    super('export_mismatch', `${file}: ${reason}`, { file, reason })
  }
}

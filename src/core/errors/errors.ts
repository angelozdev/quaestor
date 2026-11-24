import type { ErrorData } from './errors.types.ts'

class CodedError extends Error {
  readonly code: string
  readonly data: ErrorData

  constructor(code: string, message: string, data: ErrorData = {}) {
    super(message)
    this.name = new.target.name
    this.code = code
    this.data = data
  }
}

export class RefusedError extends CodedError {}

export class FailedError extends CodedError {}

import type { ErrorData } from './errors.types.ts'

export class RefusedError extends Error {
  readonly code: string
  readonly data: ErrorData

  constructor(code: string, message: string, data: ErrorData = {}) {
    super(message)
    this.name = new.target.name
    this.code = code
    this.data = data
  }
}

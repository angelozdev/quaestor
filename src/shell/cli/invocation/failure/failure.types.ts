import type { ErrorData } from '#core/errors'

export type FailurePayload = { error: ErrorData & { code: string; message: string } }

export type Failure = { exitCode: number; payload: FailurePayload }

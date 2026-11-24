export type FailurePayload = { error: { code: string; message: string } }

export type Failure = { exitCode: number; payload: FailurePayload }

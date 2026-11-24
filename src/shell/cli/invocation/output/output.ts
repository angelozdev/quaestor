import { encode } from '@toon-format/toon'
import type { Output } from '../../main/main.types.ts'
import type { Env } from '../env/env.types.ts'
import type { FailurePayload } from '../failure/failure.types.ts'
import { ENV_PREFIX, LINE_END } from './output.constants.ts'

function line(value: unknown, json: boolean): string {
  return `${json ? JSON.stringify(value) : encode(value)}${LINE_END}`
}

export function writeResult(stdout: Output, result: unknown, json: boolean): void {
  stdout.write(line(result, json))
}

export function writeFailure(stderr: Output, payload: FailurePayload, json: boolean): void {
  stderr.write(line(payload, json))
}

export function writeEnvLine(stderr: Output, { name }: Env): void {
  stderr.write(`${ENV_PREFIX}${name}${LINE_END}`)
}

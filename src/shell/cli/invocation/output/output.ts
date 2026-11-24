import { encode } from '@toon-format/toon'
import type { FailurePayload } from '../failure/failure.types.ts'
import type { Output } from '../../main/main.types.ts'
import { LINE_END } from './output.constants.ts'

export function writeFailure(stderr: Output, payload: FailurePayload, json: boolean): void {
  stderr.write(`${json ? JSON.stringify(payload) : encode(payload)}${LINE_END}`)
}

import { encode } from '@toon-format/toon'
import type { Output } from '../../main/main.types.ts'
import { CUSTOM_ENV } from '../env/env.constants.ts'
import type { Env } from '../env/env.types.ts'
import type { FailurePayload } from '../failure/failure.types.ts'
import {
  BACKUP_PREFIX,
  BEFORE_MIGRATING_SUFFIX,
  ENV_PREFIX,
  LINE_END,
  MIGRATED_PREFIX,
} from './output.constants.ts'

function line(value: unknown, json: boolean): string {
  return `${json ? JSON.stringify(value) : encode(value)}${LINE_END}`
}

export function writeResult(stdout: Output, result: unknown, json: boolean): void {
  stdout.write(line(result, json))
}

export function writeFailure(stderr: Output, payload: FailurePayload, json: boolean): void {
  stderr.write(line(payload, json))
}

export function writeEnvLine(stderr: Output, { name, dbPath }: Env): void {
  const shown = name === CUSTOM_ENV ? `${name} (${dbPath})` : name
  stderr.write(`${ENV_PREFIX}${shown}${LINE_END}`)
}

export function writeBackupBeforeMigratingLine(stderr: Output, path: string): void {
  stderr.write(`${BACKUP_PREFIX}${path}${BEFORE_MIGRATING_SUFFIX}${LINE_END}`)
}

export function writeMigratedLine(stderr: Output, name: string): void {
  stderr.write(`${MIGRATED_PREFIX}${name}${LINE_END}`)
}

import { decode, encode } from '@toon-format/toon'
import { expect } from 'vitest'
import type { CliRun } from '../run-cli/run-cli.types.ts'

export function expectWrite(run: CliRun, dryRun: boolean, result: Record<string, unknown>): void {
  expect(run.code).toBe(0)
  expect(run.stderr).toBe('env: test\n')
  expect(run.stdout.split('\n')[0]).toBe(`dryRun: ${dryRun}`)
  expect(decode(run.stdout)).toEqual({ dryRun, ...result })
}

export function written(result: Record<string, unknown>): CliRun {
  return { code: 0, stdout: `${encode({ dryRun: false, ...result })}\n`, stderr: 'env: test\n' }
}

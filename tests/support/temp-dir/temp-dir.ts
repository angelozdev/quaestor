import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { onTestFinished } from 'vitest'
import type { OnTestFinished } from './temp-dir.types.ts'

export function tempDir(prefix: string, onFinished: OnTestFinished = onTestFinished): string {
  const template = join(tmpdir(), prefix)
  const dir = mkdtempSync(template)
  onFinished(() => rmSync(dir, { recursive: true, force: true }))
  return dir
}

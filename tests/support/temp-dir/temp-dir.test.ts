import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it, onTestFinished } from 'vitest'
import { tempDir } from './temp-dir.ts'

const prefix = 'quaestor-temp-dir-'

function fill(dir: string): void {
  mkdirSync(join(dir, 'nested'))
  writeFileSync(join(dir, 'nested', 'file.txt'), 'content')
}

describe('tempDir', () => {
  it('makes an empty folder in the system temp dir', () => {
    const dir = tempDir(prefix)

    const template = join(tmpdir(), prefix)
    expect(dir.startsWith(template)).toBe(true)
    expect(readdirSync(dir)).toEqual([])
  })

  it('the folder and its contents are gone once the test finishes', () => {
    let dir = ''
    onTestFinished(() => expect(existsSync(dir)).toBe(false))

    dir = tempDir(prefix)
    fill(dir)
  })

  it("with the test context's onTestFinished the folder is gone once that test finishes", (context) => {
    let dir = ''
    context.onTestFinished(() => expect(existsSync(dir)).toBe(false))

    dir = tempDir(prefix, context.onTestFinished)
    fill(dir)
  })
})

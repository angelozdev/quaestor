import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { REPO_ROOT } from './bin.constants.ts'

const bin = join(REPO_ROOT, 'src/shell/cli/bin/bin.ts')

describe('source bin', () => {
  it('the source bin prints help from a folder outside the repo', () => {
    const cwd = tempDir('quaestor-bin-')

    const result = spawnSync(process.execPath, [bin, '--help'], { cwd, encoding: 'utf8' })

    expect(result.status).toBe(0)
    expect(result.stdout).toContain('--env')
    expect(result.stderr).toBe('')
  })
})

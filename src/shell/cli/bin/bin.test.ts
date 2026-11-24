import { encode } from '@toon-format/toon'
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { REPO_ROOT } from './bin.constants.ts'

const bin = join(REPO_ROOT, 'src/shell/cli/bin/bin.ts')

afterEach(() => {
  vi.unstubAllEnvs()
})

function runBin(args: string[]) {
  return spawnSync(process.execPath, [bin, ...args], {
    cwd: tempDir('quaestor-bin-'),
    encoding: 'utf8',
    env: { ...process.env, QUAESTOR_DB: undefined, QUAESTOR_ENV: undefined },
  })
}

describe('source bin', () => {
  it('the source bin prints help from a folder outside the repo', () => {
    const result = runBin(['--help'])

    expect(result.status).toBe(0)
    expect(result.stdout).toContain('--env')
    expect(result.stderr).toBe('')
  })

  it('the source bin under vitest refuses its default env', () => {
    const result = runBin(['backup'])

    expect(process.env.VITEST).toBeTruthy()
    expect(result.status).toBe(1)
    expect(result.stdout).toBe('')
    expect(result.stderr).toContain('code: named_env_disabled')
  })

  it('an exported QUAESTOR_DB or QUAESTOR_ENV does not reach the source bin', () => {
    const leaked = join(tempDir('quaestor-leak-'), 'leaked.sqlite')
    vi.stubEnv('QUAESTOR_DB', leaked)
    vi.stubEnv('QUAESTOR_ENV', 'leaked')

    const result = runBin(['backup'])

    expect(result.status).toBe(1)
    expect(result.stdout).toBe('')
    expect(result.stderr).toBe(
      `${encode({
        error: {
          code: 'named_env_disabled',
          source: 'default',
          env: 'test',
          message:
            'named environments are disabled here (default: test); set QUAESTOR_DB to a temporary file',
        },
      })}\n`,
    )
    expect(existsSync(leaked)).toBe(false)
  })
})

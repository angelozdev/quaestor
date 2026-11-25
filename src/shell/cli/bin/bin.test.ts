import { encode } from '@toon-format/toon'
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MIGRATION_FILE,
  SHIPPED_MIGRATIONS,
} from '../../../../tests/support/fixture-migrations/fixture-migrations.constants.ts'
import { invalidInput } from '../../../../tests/support/refusals/refusals.ts'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'
import { REPO_ROOT } from './bin.constants.ts'

const bin = join(REPO_ROOT, 'src/shell/cli/bin/bin.ts')

afterEach(() => {
  vi.unstubAllEnvs()
})

function runBin(
  args: string[],
  { input = '', vars = {} }: { input?: string; vars?: Record<string, string | undefined> } = {},
) {
  return spawnSync(process.execPath, [bin, ...args], {
    cwd: tempDir('quaestor-bin-'),
    encoding: 'utf8',
    input,
    env: { ...process.env, QUAESTOR_DB: undefined, QUAESTOR_ENV: undefined, ...vars },
  })
}

describe('source bin', () => {
  it('the source bin prints help from a folder outside the repo', () => {
    const result = runBin(['--help'])

    expect(result.status).toBe(0)
    expect(result.stdout).toContain('--env')
    expect(result.stderr).toBe('')
  })

  it('the source bin reads the JSON of movement write from its stdin', () => {
    const result = runBin(['movement', 'write'], { input: '{}' })

    expect(result.status).toBe(1)
    expect(result.stdout).toBe('')
    expect(result.stderr).toBe(
      invalidInput('nothing to write: give delete, movements or transfers'),
    )
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

  it('the source bin prints dev for --version', () => {
    const result = runBin(['--version'])

    expect(result.status).toBe(0)
    expect(result.stdout).toBe('dev\n')
    expect(result.stderr).toBe('')
  })

  it.each([
    { source: '--env', args: ['--env', 'prod', 'backup'], vars: {} },
    { source: 'QUAESTOR_ENV', args: ['backup'], vars: { QUAESTOR_ENV: 'prod' } },
  ])('the source bin refuses prod from $source as invalid_env', ({ source, args, vars }) => {
    const result = runBin(args, { vars })

    expect(result.status).toBe(1)
    expect(result.stdout).toBe('')
    expect(result.stderr).toBe(
      `${encode({
        error: {
          code: 'invalid_env',
          source,
          value: 'prod',
          message: `invalid ${source} "prod": prod is reserved for the installed quaestor`,
        },
      })}\n`,
    )
  })

  it('the source bin migrates a new store with every shipped migration', () => {
    const dbPath = join(tempDir('quaestor-store-'), 'x.sqlite')
    const shipped = readdirSync(SHIPPED_MIGRATIONS)
      .filter((name) => existsSync(join(SHIPPED_MIGRATIONS, name, MIGRATION_FILE)))
      .toSorted()

    const result = runBin(['account', 'list'], { vars: { QUAESTOR_DB: dbPath } })

    expect(result.status).toBe(0)
    expect(result.stdout).toBe('accounts: []\n')
    expect(result.stderr).toBe(
      `env: custom (${dbPath})\n${shipped.map((name) => `migrated: ${name}\n`).join('')}`,
    )
  })
})

import { encode } from '@toon-format/toon'
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'
import { runCli } from '../../../../../tests/support/run-cli/run-cli.ts'
import type { CliOverrides } from '../../../../../tests/support/run-cli/run-cli.types.ts'
import { tempDir } from '../../../../../tests/support/temp-dir/temp-dir.ts'

let dataDir: string

beforeEach(() => {
  dataDir = tempDir('quaestor-cli-')
})

function backup(argv: string[] = [], overrides: CliOverrides = {}) {
  return runCli(['backup', ...argv], { dataDir, ...overrides })
}

function refused(error: Record<string, string>) {
  return { code: 1, stdout: '', stderr: `${encode({ error })}\n` }
}

describe('env resolution', () => {
  it('QUAESTOR_DB wins over QUAESTOR_ENV', async () => {
    const dbPath = join(tempDir('quaestor-store-'), 'x.sqlite')

    const { code, stderr } = await backup([], {
      vars: { QUAESTOR_DB: dbPath, QUAESTOR_ENV: 'staging' },
    })

    expect(code).toBe(0)
    expect(stderr).toBe(`env: custom (${dbPath})\n`)
    expect(existsSync(join(dataDir, 'staging.sqlite'))).toBe(false)
  })

  it('QUAESTOR_ENV wins over the default', async () => {
    const { code, stderr } = await backup([], { vars: { QUAESTOR_ENV: 'staging' } })

    expect(code).toBe(0)
    expect(stderr).toBe('env: staging\n')
    expect(existsSync(join(dataDir, 'staging.sqlite'))).toBe(true)
  })

  it.each([
    { source: 'QUAESTOR_ENV', value: 'a b', argv: [], vars: { QUAESTOR_ENV: 'a b' } },
    { source: '--env', value: '1prod', argv: ['--env', '1prod'], vars: {} },
  ])(
    'an env name that breaks the naming rule is refused as invalid_env with the whole rule: $value',
    async ({ source, value, argv, vars }) => {
      expect(await backup(argv, { vars })).toEqual(
        refused({
          code: 'invalid_env',
          source,
          value,
          message: `invalid ${source} "${value}": start with a lowercase letter, then use lowercase letters, digits and dashes`,
        }),
      )
      expect(readdirSync(dataDir)).toEqual([])
    },
  )

  it.each([
    { source: '--env', argv: ['--env', 'custom'], vars: {} },
    { source: 'QUAESTOR_ENV', argv: [], vars: { QUAESTOR_ENV: 'custom' } },
  ])(
    'custom is refused unless it comes from QUAESTOR_DB: $source',
    async ({ source, argv, vars }) => {
      expect(await backup(argv, { vars })).toEqual(
        refused({
          code: 'invalid_env',
          source,
          value: 'custom',
          message: `invalid ${source} "custom": custom is reserved for QUAESTOR_DB`,
        }),
      )
      expect(readdirSync(dataDir)).toEqual([])
    },
  )

  it('a relative QUAESTOR_DB is refused as invalid_env', async () => {
    expect(await backup([], { vars: { QUAESTOR_DB: 'rel/x.sqlite' } })).toEqual(
      refused({
        code: 'invalid_env',
        source: 'QUAESTOR_DB',
        value: 'rel/x.sqlite',
        message: 'invalid QUAESTOR_DB "rel/x.sqlite": must be an absolute path',
      }),
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it.each([
    { source: '--env', env: 'prod', argv: ['--env', 'prod'], vars: {} },
    { source: 'QUAESTOR_ENV', env: 'x', argv: [], vars: { QUAESTOR_ENV: 'x' } },
  ])(
    'with no data folder a named env is refused naming where it came from: $source',
    async ({ source, env, argv, vars }) => {
      expect(await backup(argv, { dataDir: null, vars })).toEqual(
        refused({
          code: 'named_env_disabled',
          source,
          env,
          message: `named environments are disabled here (${source}: ${env}); set QUAESTOR_DB to a temporary file`,
        }),
      )
      expect(readdirSync(dataDir)).toEqual([])
    },
  )
})

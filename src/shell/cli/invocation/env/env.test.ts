import { describe, expect, it } from 'vitest'
import { resolveEnv } from './env.ts'
import type { Env, EnvSources } from './env.types.ts'

const base: EnvSources = { flag: undefined, vars: {}, defaultEnv: 'test', dataDir: '/d' }

const everySource = { QUAESTOR_DB: '/tmp/x.sqlite', QUAESTOR_ENV: 'staging' }

const precedence: Array<{ name: string; sources: Partial<EnvSources>; env: Env }> = [
  {
    name: '--env over QUAESTOR_DB and QUAESTOR_ENV',
    sources: { flag: 'dev', vars: everySource },
    env: { name: 'dev', dbPath: '/d/dev.sqlite' },
  },
  {
    name: 'QUAESTOR_DB over QUAESTOR_ENV and the default',
    sources: { vars: everySource },
    env: { name: 'custom', dbPath: '/tmp/x.sqlite' },
  },
  {
    name: 'QUAESTOR_ENV over the default',
    sources: { vars: { QUAESTOR_ENV: 'staging' } },
    env: { name: 'staging', dbPath: '/d/staging.sqlite' },
  },
  {
    name: 'the default when nothing else is set',
    sources: {},
    env: { name: 'test', dbPath: '/d/test.sqlite' },
  },
]

function refusal(code: string, message: string, data: Record<string, string>) {
  return expect.objectContaining({ code, message, data })
}

describe('resolveEnv', () => {
  it.each(precedence)(
    '--env wins over QUAESTOR_DB, QUAESTOR_DB over QUAESTOR_ENV, QUAESTOR_ENV over the default: $name',
    ({ sources, env }) => {
      expect(resolveEnv({ ...base, ...sources })).toEqual(env)
    },
  )

  it('--env x maps to <dataDir>/x.sqlite', () => {
    expect(resolveEnv({ ...base, flag: 'x' }).dbPath).toBe('/d/x.sqlite')
  })

  it.each([
    { source: '--env', value: 'Prod', sources: { flag: 'Prod' } },
    { source: 'QUAESTOR_ENV', value: 'a b', sources: { vars: { QUAESTOR_ENV: 'a b' } } },
    { source: '--env', value: '1prod', sources: { flag: '1prod' } },
  ])(
    'an env name that breaks the naming rule is refused as invalid_env with the whole rule: $value',
    ({ source, value, sources }) => {
      expect(() => resolveEnv({ ...base, ...sources })).toThrow(
        refusal(
          'invalid_env',
          `invalid ${source} "${value}": start with a lowercase letter, then use lowercase letters, digits and dashes`,
          { source, value },
        ),
      )
    },
  )

  it('custom is refused unless it comes from QUAESTOR_DB', () => {
    expect(() => resolveEnv({ ...base, flag: 'custom' })).toThrow(
      refusal('invalid_env', 'invalid --env "custom": custom is reserved for QUAESTOR_DB', {
        source: '--env',
        value: 'custom',
      }),
    )
    expect(() => resolveEnv({ ...base, vars: { QUAESTOR_ENV: 'custom' } })).toThrow(
      refusal('invalid_env', 'invalid QUAESTOR_ENV "custom": custom is reserved for QUAESTOR_DB', {
        source: 'QUAESTOR_ENV',
        value: 'custom',
      }),
    )
  })

  it('a relative QUAESTOR_DB is refused as invalid_env', () => {
    expect(() => resolveEnv({ ...base, vars: { QUAESTOR_DB: 'rel/x.sqlite' } })).toThrow(
      refusal('invalid_env', 'invalid QUAESTOR_DB "rel/x.sqlite": must be an absolute path', {
        source: 'QUAESTOR_DB',
        value: 'rel/x.sqlite',
      }),
    )
  })

  it('with no data folder a named env is refused naming where it came from', () => {
    const noData = { ...base, dataDir: null }
    const disabled = (source: string, env: string) =>
      refusal(
        'named_env_disabled',
        `named environments are disabled here (${source}: ${env}); set QUAESTOR_DB to a temporary file`,
        { source, env },
      )

    expect(() => resolveEnv({ ...noData, flag: 'prod' })).toThrow(disabled('--env', 'prod'))
    expect(() => resolveEnv({ ...noData, vars: { QUAESTOR_ENV: 'x' } })).toThrow(
      disabled('QUAESTOR_ENV', 'x'),
    )
    expect(() => resolveEnv(noData)).toThrow(disabled('default', 'test'))
  })

  it('with no data folder QUAESTOR_DB still names a custom store', () => {
    expect(resolveEnv({ ...base, dataDir: null, vars: { QUAESTOR_DB: '/tmp/x.sqlite' } })).toEqual({
      name: 'custom',
      dbPath: '/tmp/x.sqlite',
    })
  })
})

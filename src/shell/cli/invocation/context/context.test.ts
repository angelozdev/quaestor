import { encode } from '@toon-format/toon'
import { existsSync, mkdirSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { runCli } from '../../../../../tests/support/run-cli/run-cli.ts'
import { tempDir } from '../../../../../tests/support/temp-dir/temp-dir.ts'
import { releasedContext, sourceContext } from './context.ts'
import type { ReleasedInvocation } from './context.types.ts'

function released(vars: ReleasedInvocation['vars'], home = '/h'): ReleasedInvocation {
  return {
    release: { version: '0.0.0', commit: '2033257', repoRoot: '/r' },
    entryDir: '/pkg/dist',
    vars,
    home,
  }
}

describe('invocation context', () => {
  it('the release context prints <version> (<commit>) for --version', async () => {
    const context = releasedContext(released({}))

    expect(await runCli(['--version'], context)).toEqual({
      code: 0,
      stdout: '0.0.0 (2033257)\n',
      stderr: '',
    })
  })

  it('the source context prints dev', async () => {
    const context = sourceContext({ repoRoot: '/r', vars: {} })

    expect(await runCli(['--version'], context)).toEqual({
      code: 0,
      stdout: 'dev\n',
      stderr: '',
    })
  })

  it('the source context defaults to test under <repoRoot>/data and the release context to prod under <home>/.quaestor', () => {
    const source = sourceContext({ repoRoot: '/r', vars: {} })
    const release = releasedContext(released({}))

    expect(source).toMatchObject({ defaultEnv: 'test', dataDir: '/r/data' })
    expect(release).toMatchObject({ defaultEnv: 'prod', dataDir: '/h/.quaestor' })
  })

  it('the source context finds migrations in <repoRoot>/migrations and the release context in <entryDir>/../migrations', () => {
    expect(sourceContext({ repoRoot: '/r', vars: {} }).migrationsDir).toBe('/r/migrations')
    expect(releasedContext(released({})).migrationsDir).toBe('/pkg/migrations')
  })

  it("the release's first run creates ~/.quaestor and its store", async () => {
    const home = tempDir('quaestor-home-')
    const entryDir = join(tempDir('quaestor-package-'), 'dist')
    mkdirSync(entryDir)
    mkdirSync(join(entryDir, '..', 'migrations'))

    const { code, stdout, stderr } = await runCli(
      ['backup'],
      releasedContext({ ...released({}, home), entryDir }),
    )

    expect(code).toBe(0)
    expect(stderr).toBe('env: prod\n')
    expect(existsSync(join(home, '.quaestor', 'prod.sqlite'))).toBe(true)
    const copies = readdirSync(join(home, '.quaestor', 'backups'))
    expect(copies).toEqual([expect.stringMatching(/^prod-.+\.sqlite$/)])
    expect(stdout).toBe(
      `${encode({ path: join(home, '.quaestor', 'backups', copies[0]), removed: [] })}\n`,
    )
  })

  it.each([
    { source: '--env', argv: ['--env', 'prod', 'backup'], vars: {} },
    { source: 'QUAESTOR_ENV', argv: ['backup'], vars: { QUAESTOR_ENV: 'prod' } },
  ])(
    'the source context refuses prod from $source as invalid_env and creates nothing',
    async ({ source, argv, vars }) => {
      const repoRoot = tempDir('quaestor-repo-')

      expect(await runCli(argv, sourceContext({ repoRoot, vars }))).toEqual({
        code: 1,
        stdout: '',
        stderr: `${encode({
          error: {
            code: 'invalid_env',
            source,
            value: 'prod',
            message: `invalid ${source} "prod": prod is reserved for the installed quaestor`,
          },
        })}\n`,
      })
      expect(existsSync(join(repoRoot, 'data'))).toBe(false)
    },
  )

  it('under vitest the contexts have no data folder', async () => {
    const vars = { VITEST: 'true' }
    const repoRoot = tempDir('quaestor-repo-')
    const source = sourceContext({ repoRoot, vars })

    expect(source.dataDir).toBeNull()
    expect(releasedContext(released(vars)).dataDir).toBeNull()
    const { code, stdout, stderr } = await runCli(['backup'], source)
    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toContain('code: named_env_disabled')
    expect(existsSync(join(repoRoot, 'data'))).toBe(false)
  })
})

import { decode, encode } from '@toon-format/toon'
import { spawnSync } from 'node:child_process'
import { cpSync, existsSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, sep } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'
import { REPO_ROOT } from '#shell/cli'
import { SHIPPED_MIGRATIONS } from '../../../tests/support/fixture-migrations/fixture-migrations.constants.ts'
import { shippedMigrationNames } from '../../../tests/support/fixture-migrations/fixture-migrations.ts'
import { tempDir } from '../../../tests/support/temp-dir/temp-dir.ts'
import { buildRelease } from '../release/build/build.ts'

const PROD_COPY = /^prod-.+\.sqlite$/

let pkg: string

beforeEach(async () => {
  pkg = tempDir('quaestor-package-')
  await buildRelease({ version: '0.0.0', commit: 'abc1234', repoRoot: REPO_ROOT }, pkg)
  cpSync(SHIPPED_MIGRATIONS, join(pkg, 'migrations'), { recursive: true })
})

function installed(
  args: string[],
  { home, vars = {} }: { home: string; vars?: Record<string, string> },
) {
  if (!home.startsWith(`${tmpdir()}${sep}`)) throw new Error(`not a temporary home: ${home}`)
  return spawnSync(process.execPath, [join(pkg, 'dist', 'quaestor.js'), ...args], {
    cwd: home,
    encoding: 'utf8',
    env: { PATH: process.env.PATH, HOME: home, ...vars },
  })
}

describe('the installed quaestor', () => {
  it('the installed quaestor prints its version and commit', () => {
    const result = installed(['--version'], { home: tempDir('quaestor-home-') })

    expect(result.status).toBe(0)
    expect(result.stdout).toBe('0.0.0 (abc1234)\n')
    expect(result.stderr).toBe('')
  })

  it("the installed quaestor's first run creates ~/.quaestor/prod.sqlite, backs it up before migrating, and applies every shipped migration", () => {
    const home = tempDir('quaestor-home-')
    const backups = join(home, '.quaestor', 'backups')

    const result = installed(['backup'], { home })

    expect(result.status).toBe(0)
    const copies = readdirSync(backups).toSorted()
    expect(copies).toEqual([expect.stringMatching(PROD_COPY), expect.stringMatching(PROD_COPY)])
    const [beforeMigrating = '', own = ''] = copies
    expect(result.stderr).toBe(
      `env: prod\nbackup: ${join(backups, beforeMigrating)} (before migrating)\n${shippedMigrationNames()
        .map((name) => `migrated: ${name}\n`)
        .join('')}`,
    )
    expect(decode(result.stdout)).toEqual({ path: join(backups, own), removed: [] })
    expect(existsSync(join(home, '.quaestor', 'prod.sqlite'))).toBe(true)
  })

  it('the installed quaestor under vitest refuses its default env', () => {
    const home = tempDir('quaestor-home-')

    const result = installed(['backup'], { home, vars: { VITEST: 'true' } })

    expect(result.status).toBe(1)
    expect(result.stdout).toBe('')
    expect(result.stderr).toBe(
      `${encode({
        error: {
          code: 'named_env_disabled',
          source: 'default',
          env: 'prod',
          message:
            'named environments are disabled here (default: prod); set QUAESTOR_DB to a temporary file',
        },
      })}\n`,
    )
    expect(existsSync(join(home, '.quaestor'))).toBe(false)
  })
})

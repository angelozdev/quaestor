import { encode } from '@toon-format/toon'
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'
import { runCli } from '../../../../../tests/support/run-cli/run-cli.ts'
import type { CliOverrides } from '../../../../../tests/support/run-cli/run-cli.types.ts'
import { tempDir } from '../../../../../tests/support/temp-dir/temp-dir.ts'

const COPY_NAME = 'test-2026-11-23T21-04-05-123Z.sqlite'

let dataDir: string

beforeEach(() => {
  dataDir = tempDir('quaestor-cli-')
})

function backup(argv: string[] = [], overrides: CliOverrides = {}) {
  return runCli(['backup', ...argv], { defaultEnv: 'test', dataDir, ...overrides })
}

describe('quaestor backup', () => {
  it("backup copies the default env's store and prints the copy, TOON by default", async () => {
    const { code, stdout } = await backup()

    expect(code).toBe(0)
    expect(existsSync(join(dataDir, 'test.sqlite'))).toBe(true)
    expect(stdout).toBe(`${encode({ path: join(dataDir, 'backups', COPY_NAME), removed: [] })}\n`)
    expect(existsSync(join(dataDir, 'backups', COPY_NAME))).toBe(true)
  })

  it('--json prints the same fields as one line of JSON', async () => {
    const { code, stdout } = await backup(['--json'])

    expect(code).toBe(0)
    expect(stdout).toBe(`{"path":"${join(dataDir, 'backups', COPY_NAME)}","removed":[]}\n`)
  })

  it('stderr is exactly env: test and stdout holds only the result', async () => {
    const { stdout, stderr } = await backup()

    expect(stderr).toBe('env: test\n')
    expect(stdout).toBe(`${encode({ path: join(dataDir, 'backups', COPY_NAME), removed: [] })}\n`)
  })

  it('backup --help opens no store and prints no env line', async () => {
    const { code, stdout, stderr } = await backup(['--help'])

    expect(code).toBe(0)
    expect(stdout).toContain('Usage: quaestor backup')
    expect(stderr).toBe('')
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('an unknown command exits 1 as unknown_command', async () => {
    const { code, stdout, stderr } = await runCli(['nope'], { dataDir })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'unknown_command', message: "unknown command 'nope'" } })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('backup --bogus exits 1 and opens no store', async () => {
    const { code, stdout, stderr } = await backup(['--bogus'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'unknown_option', message: "unknown option '--bogus'" } })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('with no data folder backup exits 1 as named_env_disabled and creates nothing', async () => {
    const { code, stdout, stderr } = await backup([], { dataDir: null })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
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
    expect(readdirSync(dataDir)).toEqual([])
  })

  it('a data folder whose path holds a space works', async () => {
    const spaced = tempDir('quaestor cli-')

    const { code, stdout, stderr } = await backup([], { dataDir: spaced })

    expect(code).toBe(0)
    expect(stderr).toBe('env: test\n')
    expect(stdout).toBe(`${encode({ path: join(spaced, 'backups', COPY_NAME), removed: [] })}\n`)
    expect(existsSync(join(spaced, 'backups', COPY_NAME))).toBe(true)
  })

  it('bare quaestor prints the help on stdout and exits 0', async () => {
    const { code, stdout, stderr } = await runCli([], { dataDir })

    expect(code).toBe(0)
    expect(stdout).toContain('Usage: quaestor')
    expect(stdout).toContain('backup')
    expect(stderr).toBe('')
    expect(readdirSync(dataDir)).toEqual([])
  })

  it.for([
    [
      'an error no class names',
      () => {
        throw new Error('clock broke')
      },
    ],
    [
      'a thrown value that is not an Error',
      () => {
        throw 'clock broke'
      },
    ],
  ] as const)('%s exits 2 as unexpected with its message', async ([, clock], { expect }) => {
    const { code, stdout, stderr } = await backup([], { clock })

    expect(code).toBe(2)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `env: test\n${encode({ error: { code: 'unexpected', message: 'clock broke' } })}\n`,
    )
  })
})

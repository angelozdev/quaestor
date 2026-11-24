import { encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { runCli } from '../../../../tests/support/run-cli/run-cli.ts'

const ONE_ERROR_OBJECT = /^error:\n {2}code: \S+\n {2}message: .+\n$/

describe('main', () => {
  it('--help prints usage with --env, --json and backup on stdout and exits 0', async () => {
    const { code, stdout, stderr } = await runCli(['--help'])

    expect(code).toBe(0)
    expect(stdout).toContain('Usage: quaestor ')
    expect(stdout).toMatch(/--env <name>\s+use <name>\.sqlite in the data folder/)
    expect(stdout).toContain('--json')
    expect(stdout).toMatch(/^ {2}backup\s+copy the current env's store to its backups folder$/m)
    expect(stderr).toBe('')
  })

  it('--version from the sources prints dev', async () => {
    const { code, stdout, stderr } = await runCli(['--version'])

    expect(code).toBe(0)
    expect(stdout).toBe('dev\n')
    expect(stderr).toBe('')
  })

  it('an unknown option exits 1 with a structured error on stderr and nothing on stdout', async () => {
    const { code, stdout, stderr } = await runCli(['--nope'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'unknown_option', message: "unknown option '--nope'" } })}\n`,
    )
  })

  it('with --json anywhere in argv the error is one line of JSON', async () => {
    const { code, stdout, stderr } = await runCli(['--nope', '--json'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(`{"error":{"code":"unknown_option","message":"unknown option '--nope'"}}\n`)
  })

  it('--json before the bad option still makes the error one line of JSON', async () => {
    const { code, stdout, stderr } = await runCli(['--json', '--nope'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(`{"error":{"code":"unknown_option","message":"unknown option '--nope'"}}\n`)
  })

  it('a commander message with a suggestion stays one error object', async () => {
    const { code, stdout, stderr } = await runCli(['--jsn'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'unknown_option',
          message: "unknown option '--jsn'\n(Did you mean --json?)",
        },
      })}\n`,
    )
  })

  it('a missing option argument exits 1 as option_missing_argument', async () => {
    const { code, stdout, stderr } = await runCli(['--env'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'option_missing_argument', message: "option '--env <name>' argument missing" } })}\n`,
    )
  })

  it.for([
    ['an option and no command', ['--env', 'test']],
    ['an unexpected argument for a command', ['backup', 'extra']],
  ])(
    'with %s stderr holds the one structured error and no help text',
    async ([, argv], { expect }) => {
      const { code, stdout, stderr } = await runCli(argv as string[])

      expect(code).toBe(1)
      expect(stdout).toBe('')
      expect(stderr).toMatch(ONE_ERROR_OBJECT)
      expect(stderr).not.toContain('Usage:')
    },
  )
})

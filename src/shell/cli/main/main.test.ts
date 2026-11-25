import { encode } from '@toon-format/toon'
import { readdirSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { runCli } from '../../../../tests/support/run-cli/run-cli.ts'
import { tempDir } from '../../../../tests/support/temp-dir/temp-dir.ts'

const MISSING_COMMAND = {
  code: 'missing_command',
  commands: ['backup', 'account', 'group', 'category', 'tag', 'movement', 'import'],
  message: 'missing command: use one of backup, account, group, category, tag, movement, import',
}

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

  it('--help lists backup, the account, group, category, tag and movement groups and import as its commands', async () => {
    const { stdout } = await runCli(['--help'])

    const commands = stdout.slice(stdout.indexOf('Commands:')).trimEnd().split('\n').slice(1)
    expect(commands).toEqual([
      expect.stringMatching(/^ {2}backup\s+copy the current env's store to its backups folder$/),
      expect.stringMatching(/^ {2}account\s+accounts and their balances$/),
      expect.stringMatching(/^ {2}group\s+groups of categories and their kind$/),
      expect.stringMatching(/^ {2}category\s+categories a movement can take$/),
      expect.stringMatching(/^ {2}tag\s+tags a movement can carry$/),
      expect.stringMatching(/^ {2}movement\s+movements and transfers$/),
      expect.stringMatching(
        /^ {2}import \[options\] <folder>\s+import the legacy export, once, into an empty store$/,
      ),
    ])
  })

  it.for([['help'], ['help', 'nope']])(
    '%j exits 1 as unknown_command because help is not a command',
    async (argv, { expect }) => {
      const { code, stdout, stderr } = await runCli(argv)

      expect(code).toBe(1)
      expect(stdout).toBe('')
      expect(stderr).toBe(
        `${encode({ error: { code: 'unknown_command', message: "unknown command 'help'" } })}\n`,
      )
    },
  )

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

  it('--env without a value exits 1 as option_missing_argument', async () => {
    const dataDir = tempDir('quaestor-cli-')

    const { code, stdout, stderr } = await runCli(['backup', '--env'], { dataDir })

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'option_missing_argument', message: "option '--env <name>' argument missing" } })}\n`,
    )
    expect(readdirSync(dataDir)).toEqual([])
  })

  it.for([['--env', 'test'], ['--json']])(
    'global options and no command exit 1 as missing_command and open no store (%j)',
    async (argv, { expect }) => {
      const dataDir = tempDir('quaestor-cli-')

      const { code, stdout, stderr } = await runCli(argv, { dataDir })

      expect(code).toBe(1)
      expect(stdout).toBe('')
      expect(stderr).toBe(
        argv.includes('--json')
          ? `${JSON.stringify({ error: MISSING_COMMAND })}\n`
          : `${encode({ error: MISSING_COMMAND })}\n`,
      )
      expect(readdirSync(dataDir)).toEqual([])
    },
  )

  it('an unexpected argument for a command exits 1 as excess_arguments with nothing else on stderr', async () => {
    const { code, stdout, stderr } = await runCli(['backup', 'extra'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({
        error: {
          code: 'excess_arguments',
          message: "too many arguments for 'backup'. Expected 0 arguments but got 1: extra.",
        },
      })}\n`,
    )
  })
})

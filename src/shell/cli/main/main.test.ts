import { encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { captureStream } from '../../../../tests/support/streams/streams.ts'
import { main } from './main.ts'

async function invoke(argv: string[]) {
  const stdout = captureStream()
  const stderr = captureStream()
  const code = await main(argv, { stdout, stderr, version: 'dev' })
  return { code, stdout: stdout.text(), stderr: stderr.text() }
}

describe('main', () => {
  it('--help prints usage with --env and --json on stdout and exits 0', async () => {
    const { code, stdout, stderr } = await invoke(['--help'])

    expect(code).toBe(0)
    expect(stdout).toContain('Usage: quaestor ')
    expect(stdout).toMatch(/--env <name>\s+use <name>\.sqlite in the data folder/)
    expect(stdout).toContain('--json')
    expect(stderr).toBe('')
  })

  it('--version from the sources prints dev', async () => {
    const { code, stdout, stderr } = await invoke(['--version'])

    expect(code).toBe(0)
    expect(stdout).toBe('dev\n')
    expect(stderr).toBe('')
  })

  it('an unknown option exits 1 with a structured error on stderr and nothing on stdout', async () => {
    const { code, stdout, stderr } = await invoke(['--nope'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'unknown_option', message: "unknown option '--nope'" } })}\n`,
    )
  })

  it('with --json anywhere in argv the error is one line of JSON', async () => {
    const { code, stdout, stderr } = await invoke(['--nope', '--json'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(`{"error":{"code":"unknown_option","message":"unknown option '--nope'"}}\n`)
  })

  it('a missing option argument exits 1 as option_missing_argument', async () => {
    const { code, stdout, stderr } = await invoke(['--env'])

    expect(code).toBe(1)
    expect(stdout).toBe('')
    expect(stderr).toBe(
      `${encode({ error: { code: 'option_missing_argument', message: "option '--env <name>' argument missing" } })}\n`,
    )
  })
})

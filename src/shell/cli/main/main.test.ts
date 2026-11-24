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
})

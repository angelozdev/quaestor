import { describe, expect, it, vi } from 'vitest'
import { fakeRunner } from '../../../../tests/support/fake-runner/fake-runner.ts'
import type { RunCall } from '../../../../tests/support/fake-runner/fake-runner.types.ts'
import { captureStream } from '../../../../tests/support/streams/streams.ts'
import { release } from './release.ts'
import type { PackageJson } from './release.types.ts'

const repoRoot = '/r'
const checks = ['test', 'lint', 'format:check', 'typecheck', 'dead-code', 'duplication']
const packageJson = {
  name: 'quaestor',
  version: '0.0.0',
  scripts: { check: checks.map((name) => `pnpm ${name}`).join(' && ') },
}
const onCleanRebuild = {
  'git rev-parse --abbrev-ref HEAD': { stdout: 'rebuild\n' },
  'git status --porcelain': { stdout: '' },
}

async function releaseWith(
  responses: Parameters<typeof fakeRunner>[0],
  manifest: PackageJson = packageJson,
) {
  const runner = fakeRunner(responses)
  const build = vi.fn(async () => {})
  const stdout = captureStream()
  const stderr = captureStream()
  const code = await release({
    run: runner.run,
    build,
    packageJson: manifest,
    repoRoot,
    makeTempDir: () => '/t',
    removeTempDir: () => {},
    stdout,
    stderr,
  })
  return { code, stdout: stdout.text(), stderr: stderr.text(), calls: runner.calls, build }
}

function commandLines(calls: RunCall[]) {
  return calls.map(({ command, args }) => [command, ...args].join(' '))
}

function expectRefused(result: Awaited<ReturnType<typeof releaseWith>>, reason: string) {
  expect(result.code).toBe(1)
  expect(result.stderr).toBe(`release: refused: ${reason}\n`)
  expect(result.stdout).toBe('')
  expect(result.build).not.toHaveBeenCalled()
  const lines = commandLines(result.calls)
  expect(lines.filter((line) => line.startsWith('pnpm pack'))).toEqual([])
  expect(lines.filter((line) => line.startsWith('pnpm add'))).toEqual([])
}

describe('release refusals', () => {
  it('refuses off rebuild', async () => {
    const result = await releaseWith({
      'git rev-parse --abbrev-ref HEAD': { stdout: 'skeleton\n' },
    })

    expectRefused(result, 'on skeleton, not rebuild')
  })

  it('refuses with uncommitted changes', async () => {
    const result = await releaseWith({
      ...onCleanRebuild,
      'git status --porcelain': { stdout: ' M src/x.ts\n' },
    })

    expectRefused(result, 'uncommitted changes')
  })

  it('refuses naming the failing check', async () => {
    const result = await releaseWith({ ...onCleanRebuild, 'pnpm run lint': { status: 1 } })

    expectRefused(result, 'lint failed')
    expect(commandLines(result.calls).filter((line) => line.startsWith('pnpm run'))).toEqual([
      'pnpm run test',
      'pnpm run lint',
    ])
    expect(result.calls.find(({ args }) => args.includes('lint'))?.cwd).toBe(repoRoot)
  })

  it('runs the checks named in scripts.check, whatever they are', async () => {
    const custom = { ...packageJson, scripts: { check: 'pnpm one && pnpm two:x && pnpm three' } }

    const result = await releaseWith({ ...onCleanRebuild, 'pnpm run two:x': { status: 1 } }, custom)

    expectRefused(result, 'two:x failed')
    expect(commandLines(result.calls).filter((line) => line.startsWith('pnpm run'))).toEqual([
      'pnpm run one',
      'pnpm run two:x',
    ])
  })
})

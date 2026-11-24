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

const tempDir = '/t'
const tarball = '/r/.release/quaestor-0.0.0.tgz'
const packedBin = '/t/package/dist/quaestor.js'
const released = '0.0.0 (2033257)'
const packedWithoutMigrations = ['package/package.json', 'package/dist/quaestor.js']
const onGreenRebuild = {
  ...onCleanRebuild,
  'git rev-parse --short HEAD': { stdout: '2033257\n' },
  [`tar -tzf ${tarball}`]: {
    stdout: `${[...packedWithoutMigrations, 'package/migrations/.gitkeep'].join('\n')}\n`,
  },
  [`node ${packedBin} --version`]: { stdout: `${released}\n` },
  'quaestor --version': { stdout: `${released}\n` },
}

async function releaseWith(
  responses: Parameters<typeof fakeRunner>[0],
  manifest: PackageJson = packageJson,
) {
  const runner = fakeRunner(responses)
  let callsBeforeBuild: number | undefined
  const build = vi.fn(async () => {
    callsBeforeBuild = runner.calls.length
  })
  let callsBeforeRemoval: number | undefined
  const removeTempDir = vi.fn(() => {
    callsBeforeRemoval = runner.calls.length
  })
  const stdout = captureStream()
  const stderr = captureStream()
  const code = await release({
    run: runner.run,
    build,
    packageJson: manifest,
    repoRoot,
    makeTempDir: () => tempDir,
    removeTempDir,
    stdout,
    stderr,
  })
  return {
    code,
    stdout: stdout.text(),
    stderr: stderr.text(),
    calls: runner.calls,
    build,
    callsBeforeBuild,
    removeTempDir,
    callsBeforeRemoval,
  }
}

type ReleaseResult = Awaited<ReturnType<typeof releaseWith>>

function step(line: string, cwd?: string) {
  const [command = '', ...args] = line.split(' ')
  return { command, args, cwd }
}

function commandLines(calls: RunCall[]) {
  return calls.map(({ command, args }) => [command, ...args].join(' '))
}

function commandsStartingWith(result: ReleaseResult, prefix: string) {
  return commandLines(result.calls).filter((line) => line.startsWith(prefix))
}

function expectRefused(result: ReleaseResult, reason: string) {
  expect(result.code).toBe(1)
  expect(result.stderr).toBe(`release: refused: ${reason}\n`)
  expect(result.stdout).toBe('')
  expect(commandsStartingWith(result, 'pnpm add')).toEqual([])
}

function expectRefusedBeforeBuild(result: ReleaseResult, reason: string) {
  expectRefused(result, reason)
  expect(result.build).not.toHaveBeenCalled()
  expect(commandsStartingWith(result, 'pnpm pack')).toEqual([])
}

function expectTempDirRemovedLast(result: ReleaseResult) {
  expect(result.removeTempDir).toHaveBeenCalledExactlyOnceWith(tempDir)
  expect(result.callsBeforeRemoval).toBe(result.calls.length)
}

describe('release refusals', () => {
  it('refuses off rebuild', async () => {
    const result = await releaseWith({
      'git rev-parse --abbrev-ref HEAD': { stdout: 'skeleton\n' },
    })

    expectRefusedBeforeBuild(result, 'on skeleton, not rebuild')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual([])
  })

  it('refuses with uncommitted changes', async () => {
    const result = await releaseWith({
      ...onCleanRebuild,
      'git status --porcelain': { stdout: ' M src/x.ts\n' },
    })

    expectRefusedBeforeBuild(result, 'uncommitted changes')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual([])
  })

  it('refuses naming the failing check', async () => {
    const result = await releaseWith({ ...onCleanRebuild, 'pnpm run lint': { status: 1 } })

    expectRefusedBeforeBuild(result, 'lint failed')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual(['pnpm run test', 'pnpm run lint'])
    expect(result.calls.find(({ args }) => args.includes('lint'))?.cwd).toBe(repoRoot)
  })

  it('runs the checks named in scripts.check, whatever they are', async () => {
    const custom = { ...packageJson, scripts: { check: 'pnpm one && pnpm two:x && pnpm three' } }

    const result = await releaseWith({ ...onCleanRebuild, 'pnpm run two:x': { status: 1 } }, custom)

    expectRefusedBeforeBuild(result, 'two:x failed')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual(['pnpm run one', 'pnpm run two:x'])
  })
})

describe('release from a clean green rebuild', () => {
  it('builds, packs, smoke-runs and installs from a clean green rebuild', async () => {
    const result = await releaseWith(onGreenRebuild)

    expect(result.calls.slice(0, result.callsBeforeBuild)).toEqual([
      step('git rev-parse --abbrev-ref HEAD', repoRoot),
      step('git status --porcelain', repoRoot),
      ...checks.map((name) => step(`pnpm run ${name}`, repoRoot)),
      step('git rev-parse --short HEAD', repoRoot),
    ])
    expect(result.build).toHaveBeenCalledExactlyOnceWith({
      version: '0.0.0',
      commit: '2033257',
      repoRoot,
    })
    expect(result.calls.slice(result.callsBeforeBuild)).toEqual([
      step('pnpm pack --pack-destination .release', repoRoot),
      step(`tar -tzf ${tarball}`),
      step(`tar -xzf ${tarball} -C ${tempDir}`),
      step(`node ${packedBin} --help`, tempDir),
      step(`node ${packedBin} --version`, tempDir),
      step(`pnpm add -g ${tarball}`, tempDir),
      step('quaestor --version', tempDir),
    ])
    expect(result).toMatchObject({
      code: 0,
      stdout: `release: ${released} installed\n`,
      stderr: '',
    })
  })

  it('refuses before installing when the package has no migrations/', async () => {
    const result = await releaseWith({
      ...onGreenRebuild,
      [`tar -tzf ${tarball}`]: { stdout: `${packedWithoutMigrations.join('\n')}\n` },
    })

    expectRefused(result, 'package is missing migrations/')
  })

  it('refuses before installing when the packed CLI fails its smoke run', async () => {
    const result = await releaseWith({
      ...onGreenRebuild,
      [`node ${packedBin} --version`]: { stdout: 'dev\n' },
    })

    expectRefused(result, `smoke run failed: --version printed "dev", expected "${released}"`)
  })

  it('refuses before installing when the packed --help fails', async () => {
    const result = await releaseWith({
      ...onGreenRebuild,
      [`node ${packedBin} --help`]: { status: 3 },
    })

    expectRefused(result, 'smoke run failed: --help exited 3')
  })

  it('reports a PATH mismatch after installing', async () => {
    const result = await releaseWith({
      ...onGreenRebuild,
      'quaestor --version': { stdout: '0.0.0 (1111111)\n' },
    })

    expect(result).toMatchObject({
      code: 2,
      stdout: '',
      stderr: `release: failed: quaestor on PATH prints "0.0.0 (1111111)", expected "${released}"\n`,
    })
  })
})

describe('release temp folder', () => {
  it.for<[string, Parameters<typeof fakeRunner>[0]]>([
    ['once installed', onGreenRebuild],
    [
      'when the smoke run fails',
      { ...onGreenRebuild, [`node ${packedBin} --help`]: { status: 3 } },
    ],
    [
      'when PATH prints another version',
      { ...onGreenRebuild, 'quaestor --version': { stdout: '0.0.0 (1111111)\n' } },
    ],
  ])('removes its temp folder after its last command %s', async ([, responses]) => {
    const result = await releaseWith(responses)

    expectTempDirRemovedLast(result)
  })
})

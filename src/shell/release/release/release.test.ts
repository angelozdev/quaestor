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
const onCleanMain = {
  'git rev-parse --abbrev-ref HEAD': { stdout: 'main\n' },
  'git status --porcelain': { stdout: '' },
}

const tempDir = '/t'
const tarball = '/r/.release/quaestor-0.0.0.tgz'
const packedBin = '/t/package/dist/quaestor.js'
const released = '0.0.0 (2033257)'
const packedWithoutMigrations = ['package/package.json', 'package/dist/quaestor.js']
const onGreenMain = {
  ...onCleanMain,
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
  it('refuses off main, the old rebuild trunk included', async () => {
    const result = await releaseWith({
      'git rev-parse --abbrev-ref HEAD': { stdout: 'rebuild\n' },
    })

    expectRefusedBeforeBuild(result, 'on rebuild, not main')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual([])
  })

  it('refuses with uncommitted changes', async () => {
    const result = await releaseWith({
      ...onCleanMain,
      'git status --porcelain': { stdout: ' M src/x.ts\n' },
    })

    expectRefusedBeforeBuild(result, 'uncommitted changes')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual([])
  })

  it('refuses naming the failing check', async () => {
    const result = await releaseWith({ ...onCleanMain, 'pnpm run lint': { status: 1 } })

    expectRefusedBeforeBuild(result, 'lint failed')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual(['pnpm run test', 'pnpm run lint'])
    expect(result.calls.find(({ args }) => args.includes('lint'))?.cwd).toBe(repoRoot)
  })

  it('runs the checks named in scripts.check, whatever they are', async () => {
    const custom = { ...packageJson, scripts: { check: 'pnpm one && pnpm two:x && pnpm three' } }

    const result = await releaseWith({ ...onCleanMain, 'pnpm run two:x': { status: 1 } }, custom)

    expectRefusedBeforeBuild(result, 'two:x failed')
    expect(commandsStartingWith(result, 'pnpm run')).toEqual(['pnpm run one', 'pnpm run two:x'])
  })
})

describe('release from a clean green main', () => {
  it('builds, packs, smoke-runs and installs from a clean green main', async () => {
    const result = await releaseWith(onGreenMain)

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
      ...onGreenMain,
      [`tar -tzf ${tarball}`]: { stdout: `${packedWithoutMigrations.join('\n')}\n` },
    })

    expectRefused(result, 'package is missing migrations/')
  })

  it('refuses before installing when the packed CLI fails its smoke run', async () => {
    const result = await releaseWith({
      ...onGreenMain,
      [`node ${packedBin} --version`]: { stdout: 'dev\n' },
    })

    expectRefused(result, `smoke run failed: --version printed "dev", expected "${released}"`)
  })

  it('refuses before installing when the packed --help fails', async () => {
    const result = await releaseWith({
      ...onGreenMain,
      [`node ${packedBin} --help`]: { status: 3 },
    })

    expectRefused(result, 'smoke run failed: --help exited 3')
  })

  it('reports a PATH mismatch after installing', async () => {
    const result = await releaseWith({
      ...onGreenMain,
      'quaestor --version': { stdout: '0.0.0 (1111111)\n' },
    })

    expect(result).toMatchObject({
      code: 2,
      stdout: '',
      stderr: `release: failed: quaestor on PATH prints "0.0.0 (1111111)", expected "${released}"\n`,
    })
  })
})

describe('release command failures', () => {
  const preBuild = false
  const postBuild = true
  const freshTempDir = true

  it.for<[string, string, number, boolean, boolean]>([
    ['git rev-parse --abbrev-ref HEAD', 'git rev-parse --abbrev-ref HEAD', 128, preBuild, false],
    ['git status --porcelain', 'git status --porcelain', 128, preBuild, false],
    ['git rev-parse --short HEAD', 'git rev-parse --short HEAD', 129, preBuild, false],
    ['pnpm pack', 'pnpm pack --pack-destination .release', 4, postBuild, false],
    ['tar -tzf', `tar -tzf ${tarball}`, 2, postBuild, false],
    ['tar -xzf', `tar -xzf ${tarball} -C ${tempDir}`, 2, postBuild, freshTempDir],
    ['pnpm add -g', `pnpm add -g ${tarball}`, 1, postBuild, freshTempDir],
  ])(
    'fails with exit 2 and stops when %s exits non-zero',
    async ([, line, status, built, removesTempDir]) => {
      const result = await releaseWith({ ...onGreenMain, [line]: { status } })

      expect(result).toMatchObject({
        code: 2,
        stdout: '',
        stderr: `release: failed: ${line} exited ${status}\n`,
      })
      expect(commandLines(result.calls).at(-1)).toBe(line)
      expect(result.build.mock.calls.length > 0).toBe(built)
      if (removesTempDir) expectTempDirRemovedLast(result)
      else expect(result.removeTempDir).not.toHaveBeenCalled()
    },
  )

  it('keeps the PATH mismatch failure when quaestor --version exits non-zero', async () => {
    const result = await releaseWith({ ...onGreenMain, 'quaestor --version': { status: 127 } })

    expect(result).toMatchObject({
      code: 2,
      stdout: '',
      stderr: `release: failed: quaestor on PATH prints "", expected "${released}"\n`,
    })
  })

  it('keeps the smoke refusal when the packed --version exits non-zero', async () => {
    const result = await releaseWith({
      ...onGreenMain,
      [`node ${packedBin} --version`]: { status: 127 },
    })

    expectRefused(result, `smoke run failed: --version printed "", expected "${released}"`)
  })
})

describe('release temp folder', () => {
  it.for<[string, Parameters<typeof fakeRunner>[0]]>([
    ['once installed', onGreenMain],
    ['when the smoke run fails', { ...onGreenMain, [`node ${packedBin} --help`]: { status: 3 } }],
    [
      'when PATH prints another version',
      { ...onGreenMain, 'quaestor --version': { stdout: '0.0.0 (1111111)\n' } },
    ],
  ])('removes its temp folder after its last command %s', async ([, responses]) => {
    const result = await releaseWith(responses)

    expectTempDirRemovedLast(result)
  })
})

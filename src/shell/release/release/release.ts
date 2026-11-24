import { join } from 'node:path'
import { ExitCode, releaseVersion, type Release } from '#shell/cli'
import { BUNDLE_FILE } from '../build/build.constants.ts'
import type { RunResult, Runner } from '../runner/runner.types.ts'
import {
  CHECK_SCRIPT,
  CHECK_SEPARATOR,
  HELP_FLAG,
  INSTALLED_BIN,
  PACKED_MIGRATIONS,
  PACKED_ROOT,
  PNPM_PREFIX,
  RELEASE_DIR,
  TARBALL_EXTENSION,
  TRUNK_BRANCH,
  VERSION_FLAG,
} from './release.constants.ts'
import {
  CheckFailedError,
  CommandFailedError,
  MissingMigrationsError,
  NotOnTrunkError,
  PackedHelpFailedError,
  PackedVersionMismatchError,
  PathMismatchError,
  ReleaseError,
  UncommittedChangesError,
} from './release.errors.ts'
import type { PackageJson, ReleaseDeps } from './release.types.ts'

async function printed(run: Runner, command: string, args: string[], cwd?: string) {
  return (await run(command, args, { cwd })).stdout.trim()
}

async function checked(
  run: Runner,
  command: string,
  args: string[],
  cwd?: string,
): Promise<RunResult> {
  const result = await run(command, args, { cwd })
  if (result.status !== ExitCode.Success) throw new CommandFailedError(command, args, result.status)
  return result
}

async function checkedPrinted(run: Runner, command: string, args: string[], cwd?: string) {
  return (await checked(run, command, args, cwd)).stdout.trim()
}

async function assertOnTrunk({ run, repoRoot }: ReleaseDeps): Promise<void> {
  const branch = await checkedPrinted(run, 'git', ['rev-parse', '--abbrev-ref', 'HEAD'], repoRoot)
  if (branch !== TRUNK_BRANCH) throw new NotOnTrunkError(branch)
}

async function assertCleanTree({ run, repoRoot }: ReleaseDeps): Promise<void> {
  const changes = await checkedPrinted(run, 'git', ['status', '--porcelain'], repoRoot)
  if (changes) throw new UncommittedChangesError()
}

function checkNames(scripts: PackageJson['scripts']): string[] {
  return scripts[CHECK_SCRIPT]
    .split(CHECK_SEPARATOR)
    .map((step) => step.trim().replace(PNPM_PREFIX, ''))
}

async function assertChecksPass({ run, packageJson, repoRoot }: ReleaseDeps): Promise<void> {
  for (const check of checkNames(packageJson.scripts)) {
    const { status } = await run('pnpm', ['run', check], { cwd: repoRoot })
    if (status !== ExitCode.Success) throw new CheckFailedError(check)
  }
}

async function releaseOfHead({ run, packageJson, repoRoot }: ReleaseDeps): Promise<Release> {
  const commit = await checkedPrinted(run, 'git', ['rev-parse', '--short', 'HEAD'], repoRoot)
  return { version: packageJson.version, commit, repoRoot }
}

async function pack({ run, packageJson, repoRoot }: ReleaseDeps): Promise<string> {
  await checked(run, 'pnpm', ['pack', '--pack-destination', RELEASE_DIR], repoRoot)
  const tarballName = `${packageJson.name}-${packageJson.version}${TARBALL_EXTENSION}`
  return join(repoRoot, RELEASE_DIR, tarballName)
}

async function assertShipsMigrations(run: Runner, tarball: string): Promise<void> {
  const entries = (await checkedPrinted(run, 'tar', ['-tzf', tarball])).split('\n')
  const prefix = `${PACKED_ROOT}/${PACKED_MIGRATIONS}`
  if (!entries.some((entry) => entry.startsWith(prefix))) throw new MissingMigrationsError()
}

async function smokeRun(run: Runner, tarball: string, dir: string, expected: string) {
  await checked(run, 'tar', ['-xzf', tarball, '-C', dir])
  const bin = join(dir, PACKED_ROOT, BUNDLE_FILE)
  const help = await run('node', [bin, HELP_FLAG], { cwd: dir })
  if (help.status !== ExitCode.Success) throw new PackedHelpFailedError(help.status)
  const version = await printed(run, 'node', [bin, VERSION_FLAG], dir)
  if (version !== expected) throw new PackedVersionMismatchError(version, expected)
}

async function install(run: Runner, tarball: string, dir: string, expected: string) {
  await checked(run, 'pnpm', ['add', '-g', tarball], dir)
  const version = await printed(run, INSTALLED_BIN, [VERSION_FLAG], dir)
  if (version !== expected) throw new PathMismatchError(version, expected)
}

async function releaseSteps(deps: ReleaseDeps): Promise<void> {
  await assertOnTrunk(deps)
  await assertCleanTree(deps)
  await assertChecksPass(deps)
  const target = await releaseOfHead(deps)
  await deps.build(target)
  const tarball = await pack(deps)
  await assertShipsMigrations(deps.run, tarball)
  const dir = deps.makeTempDir()
  const expected = releaseVersion(target)
  try {
    await smokeRun(deps.run, tarball, dir, expected)
    await install(deps.run, tarball, dir, expected)
  } finally {
    deps.removeTempDir(dir)
  }
  deps.stdout.write(`release: ${expected} installed\n`)
}

export async function release(deps: ReleaseDeps): Promise<number> {
  try {
    await releaseSteps(deps)
    return ExitCode.Success
  } catch (error) {
    if (!(error instanceof ReleaseError)) throw error
    deps.stderr.write(`${error.message}\n`)
    return error.exitCode
  }
}

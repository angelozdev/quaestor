import { ExitCode } from '#shell/cli'
import type { Runner } from '../runner/runner.types.ts'
import { CHECK_SCRIPT, CHECK_SEPARATOR, PNPM_PREFIX, TRUNK_BRANCH } from './release.constants.ts'
import {
  CheckFailedError,
  NotOnTrunkError,
  ReleaseError,
  UncommittedChangesError,
} from './release.errors.ts'
import type { PackageJson, ReleaseDeps } from './release.types.ts'

async function printed(run: Runner, command: string, args: string[], cwd?: string) {
  return (await run(command, args, { cwd })).stdout.trim()
}

async function assertOnTrunk({ run, repoRoot }: ReleaseDeps): Promise<void> {
  const branch = await printed(run, 'git', ['rev-parse', '--abbrev-ref', 'HEAD'], repoRoot)
  if (branch !== TRUNK_BRANCH) throw new NotOnTrunkError(branch)
}

async function assertCleanTree({ run, repoRoot }: ReleaseDeps): Promise<void> {
  const changes = await printed(run, 'git', ['status', '--porcelain'], repoRoot)
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

async function releaseSteps(deps: ReleaseDeps): Promise<void> {
  await assertOnTrunk(deps)
  await assertCleanTree(deps)
  await assertChecksPass(deps)
}

export async function release(deps: ReleaseDeps): Promise<number> {
  try {
    await releaseSteps(deps)
    return ExitCode.Success
  } catch (error) {
    if (!(error instanceof ReleaseError)) throw error
    deps.stderr.write(`${error.message}\n`)
    return ExitCode.Refused
  }
}

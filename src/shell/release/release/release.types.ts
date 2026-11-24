import type { Output, Release } from '#shell/cli'
import type { Runner } from '../runner/runner.types.ts'

export type PackageJson = { name: string; version: string; scripts: Record<string, string> }

export type ReleaseDeps = {
  run: Runner
  build(release: Release): Promise<void>
  packageJson: PackageJson
  repoRoot: string
  makeTempDir(): string
  removeTempDir(dir: string): void
  stdout: Output
  stderr: Output
}

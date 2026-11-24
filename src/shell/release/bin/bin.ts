import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { REPO_ROOT } from '#shell/cli'
import { buildRelease } from '../build/build.ts'
import { release } from '../release/release.ts'
import { runCommand } from '../runner/runner.ts'
import { TEMP_DIR_PREFIX } from './bin.constants.ts'

const packageJsonText = readFileSync(join(REPO_ROOT, 'package.json'), 'utf8')
const tempDirTemplate = join(tmpdir(), TEMP_DIR_PREFIX)

process.exitCode = await release({
  run: runCommand,
  build: buildRelease,
  packageJson: JSON.parse(packageJsonText),
  repoRoot: REPO_ROOT,
  makeTempDir: () => mkdtempSync(tempDirTemplate),
  removeTempDir: (dir) => rmSync(dir, { recursive: true, force: true }),
  stdout: process.stdout,
  stderr: process.stderr,
})

import { spawnSync } from 'node:child_process'
import { ExitCode } from '#shell/cli'
import type { Runner } from './runner.types.ts'

export const runCommand: Runner = (command, args, options) => {
  const result = spawnSync(command, args, { cwd: options?.cwd, encoding: 'utf8' })
  return Promise.resolve({
    status: result.status ?? ExitCode.Failed,
    stdout: result.stdout ?? '',
    stderr: result.stderr ?? result.error?.message ?? '',
  })
}

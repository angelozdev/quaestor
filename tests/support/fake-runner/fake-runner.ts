import { ExitCode } from '#shell/cli'
import type { Runner } from '#shell/release'
import type { FakeResponses, RunCall } from './fake-runner.types.ts'

export function fakeRunner(responses: FakeResponses) {
  const calls: RunCall[] = []
  const run: Runner = async (command, args, options) => {
    calls.push({ command, args, cwd: options?.cwd })
    return {
      status: ExitCode.Success,
      stdout: '',
      stderr: '',
      ...responses[`${command} ${args.join(' ')}`],
    }
  }
  return { run, calls }
}

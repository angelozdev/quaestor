import { describe, expect, it } from 'vitest'
import { captureStream } from '../../../../../tests/support/streams/streams.ts'
import { main } from '../../main/main.ts'
import { releasedContext, sourceContext } from './context.ts'
import type { InvocationContext } from './context.types.ts'

async function printedVersion(context: InvocationContext) {
  const stdout = captureStream()
  const stderr = captureStream()
  const code = await main(['--version'], { ...context, stdout, stderr })
  return { code, stdout: stdout.text(), stderr: stderr.text() }
}

describe('invocation context', () => {
  it('the release context prints <version> (<commit>) for --version', async () => {
    const context = releasedContext({
      release: { version: '0.0.0', commit: '2033257', repoRoot: '/r' },
      entryDir: '/pkg/dist',
    })

    expect(await printedVersion(context)).toEqual({
      code: 0,
      stdout: '0.0.0 (2033257)\n',
      stderr: '',
    })
  })

  it('the source context prints dev', async () => {
    const context = sourceContext({ repoRoot: '/r' })

    expect(await printedVersion(context)).toEqual({ code: 0, stdout: 'dev\n', stderr: '' })
  })
})

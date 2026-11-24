import { DEV_VERSION } from './context.constants.ts'
import type {
  InvocationContext,
  Release,
  ReleasedInvocation,
  SourceInvocation,
} from './context.types.ts'

function releaseVersion(release: Release): string {
  return `${release.version} (${release.commit})`
}

export function sourceContext(_invocation: SourceInvocation): InvocationContext {
  return { version: DEV_VERSION }
}

export function releasedContext({ release }: ReleasedInvocation): InvocationContext {
  return { version: releaseVersion(release) }
}

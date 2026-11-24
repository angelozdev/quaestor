import type { CapturedStream } from './streams.types.ts'

export function captureStream(): CapturedStream {
  let captured = ''
  return {
    write(chunk: string) {
      captured += chunk
      return true
    },
    text() {
      return captured
    },
  }
}

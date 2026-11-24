import type { Output } from '#shell/cli'

export type CapturedStream = Output & { text(): string }

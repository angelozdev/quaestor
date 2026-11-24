import type { Output } from '../../../src/shell/cli/main/main.types.ts'

export type CapturedStream = Output & { text(): string }

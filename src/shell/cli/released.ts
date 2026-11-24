#!/usr/bin/env node
import { releasedContext } from './invocation/context/context.ts'
import type { Release } from './invocation/context/context.types.ts'
import { main } from './main/main.ts'

declare const __QUAESTOR_RELEASE__: Release

process.exitCode = await main(process.argv.slice(2), {
  ...releasedContext({ release: __QUAESTOR_RELEASE__, entryDir: import.meta.dirname }),
  stdout: process.stdout,
  stderr: process.stderr,
})

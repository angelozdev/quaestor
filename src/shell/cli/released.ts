#!/usr/bin/env node
import { randomInt } from 'node:crypto'
import { homedir } from 'node:os'
import { releasedContext } from './invocation/context/context.ts'
import type { Release } from './invocation/context/context.types.ts'
import { main } from './main/main.ts'

declare const __QUAESTOR_RELEASE__: Release

process.exitCode = await main(process.argv.slice(2), {
  ...releasedContext({
    release: __QUAESTOR_RELEASE__,
    entryDir: import.meta.dirname,
    vars: process.env,
    home: homedir(),
  }),
  randomIndex: randomInt,
  stdout: process.stdout,
  stderr: process.stderr,
})

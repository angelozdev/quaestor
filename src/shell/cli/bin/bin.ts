#!/usr/bin/env node
import { main } from '../main/main.ts'
import { DEV_VERSION } from './bin.constants.ts'

process.exitCode = await main(process.argv.slice(2), {
  version: DEV_VERSION,
  stdout: process.stdout,
  stderr: process.stderr,
})

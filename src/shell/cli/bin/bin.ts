#!/usr/bin/env node
import { sourceContext } from '../invocation/context/context.ts'
import { main } from '../main/main.ts'
import { REPO_ROOT } from './bin.constants.ts'

process.exitCode = await main(process.argv.slice(2), {
  ...sourceContext({ repoRoot: REPO_ROOT, vars: process.env }),
  stdout: process.stdout,
  stderr: process.stderr,
})

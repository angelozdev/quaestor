import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { REPO_ROOT } from '../../src/shell/cli/bin/bin.constants.ts'

const packageJson = JSON.parse(readFileSync(join(REPO_ROOT, 'package.json'), 'utf8'))
const checks = ['test', 'lint', 'format:check', 'typecheck', 'dead-code', 'duplication']

describe('checks', () => {
  it('pnpm check runs test, lint, format:check, typecheck, dead-code and duplication in order', () => {
    expect(packageJson.scripts.check).toBe(checks.map((name) => `pnpm ${name}`).join(' && '))
    for (const name of checks) expect(packageJson.scripts[name], name).toEqual(expect.any(String))
  })
})

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { REPO_ROOT } from '#shell/cli'
import { runCli } from '../support/run-cli/run-cli.ts'

const SKILL_PATH = join(REPO_ROOT, '.claude', 'skills', 'record-movements', 'SKILL.md')
const COMMAND = /\bquaestor (?:(?:account|category|tag|movement) [a-z]+|import|backup)\b/g

function skill(): string {
  return readFileSync(SKILL_PATH, 'utf8')
}

function commandsNamedBy(text: string): string[][] {
  const named = new Set([...text.matchAll(COMMAND)].map(([command]) => command))
  return [...named].map((command) => command.split(' ').slice(1))
}

describe('the record-movements skill', () => {
  it('every quaestor command the record-movements skill names exists', async () => {
    const commands = commandsNamedBy(skill())

    expect(commands.length).toBeGreaterThan(0)
    for (const words of commands) {
      const { code, stdout } = await runCli([...words, '--help'])

      expect(code, words.join(' ')).toBe(0)
      expect(stdout, words.join(' ')).toContain(`Usage: quaestor ${words.join(' ')} `)
    }
  })

  it('the skill never calls pnpm quaestor', () => {
    expect(skill()).not.toMatch(/pnpm\s+quaestor/)
  })
})

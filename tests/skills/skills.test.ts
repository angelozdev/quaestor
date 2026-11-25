import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { REPO_ROOT } from '#shell/cli'
import { runCli } from '../support/run-cli/run-cli.ts'

const SKILLS = ['record-movements', 'spending-and-income']

const COMMAND =
  /\bquaestor (?:(?:account|category|tag|movement|group|rate) [a-z]+|report|backup)\b/g

function skill(name: string): string {
  return readFileSync(join(REPO_ROOT, '.claude', 'skills', name, 'SKILL.md'), 'utf8')
}

function commandsNamedBy(text: string): string[][] {
  const named = new Set([...text.matchAll(COMMAND)].map(([command]) => command))
  return [...named].map((command) => command.split(' ').slice(1))
}

describe.for(SKILLS)('the %s skill', (name) => {
  it(`every quaestor command the ${name} skill names exists`, async () => {
    const commands = commandsNamedBy(skill(name))

    expect(commands.length).toBeGreaterThan(0)
    for (const words of commands) {
      const { code, stdout } = await runCli([...words, '--help'])

      expect(code, words.join(' ')).toBe(0)
      expect(stdout, words.join(' ')).toContain(`Usage: quaestor ${words.join(' ')} `)
    }
  })

  it('the skill never calls pnpm quaestor', () => {
    expect(skill(name)).not.toMatch(/pnpm\s+quaestor/)
  })
})

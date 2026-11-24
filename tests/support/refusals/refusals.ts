import { encode } from '@toon-format/toon'

export function missingCommand(commands: string[]): string {
  const message = `missing command: use one of ${commands.join(', ')}`
  return `${encode({ error: { code: 'missing_command', commands, message } })}\n`
}

export function invalidInput(...issues: string[]): string {
  const message = issues.join('; ')
  return `${encode({ error: { code: 'invalid_input', issues, message } })}\n`
}

export function alreadyExists(kind: string, name: string): string {
  const message = `${kind} ${name} already exists`
  return `env: test\n${encode({ error: { code: 'already_exists', kind, name, message } })}\n`
}

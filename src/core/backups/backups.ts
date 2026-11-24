import {
  BACKUP_EXTENSION,
  COPIES_KEPT,
  ENV_SEPARATOR,
  INSTANT_PATTERN,
  SAFE_INSTANT_CHAR,
  UNSAFE_INSTANT_CHARS,
} from './backups.constants.ts'

export function backupFileName(env: string, instant: Date): string {
  const stamp = instant.toISOString().replace(UNSAFE_INSTANT_CHARS, SAFE_INSTANT_CHAR)
  return `${env}${ENV_SEPARATOR}${stamp}${BACKUP_EXTENSION}`
}

function copyPattern(env: string): RegExp {
  return new RegExp(
    `^${RegExp.escape(env)}${ENV_SEPARATOR}${INSTANT_PATTERN}${RegExp.escape(BACKUP_EXTENSION)}$`,
  )
}

export function copiesToRemove(env: string, names: string[], keep = COPIES_KEPT): string[] {
  const pattern = copyPattern(env)
  const copies = names.filter((name) => pattern.test(name)).toSorted()
  return copies.slice(0, Math.max(0, copies.length - keep))
}

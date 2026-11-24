import {
  BACKUP_EXTENSION,
  ENV_SEPARATOR,
  SAFE_INSTANT_CHAR,
  UNSAFE_INSTANT_CHARS,
} from './backups.constants.ts'

export function backupFileName(env: string, instant: Date): string {
  const stamp = instant.toISOString().replace(UNSAFE_INSTANT_CHARS, SAFE_INSTANT_CHAR)
  return `${env}${ENV_SEPARATOR}${stamp}${BACKUP_EXTENSION}`
}

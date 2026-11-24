import { mkdir, rename } from 'node:fs/promises'
import { join } from 'node:path'
import { backup } from 'node:sqlite'
import { backupFileName } from '#core/backups'
import { client } from '../database/database.ts'
import { BACKUPS_FOLDER, PARTIAL_SUFFIX } from './backups.constants.ts'
import type { BackupRequest, BackupResult } from './backups.types.ts'

export async function backupStore({ store, env, root, now }: BackupRequest): Promise<BackupResult> {
  const folder = join(root, BACKUPS_FOLDER)
  const path = join(folder, backupFileName(env, now))
  const partial = `${path}${PARTIAL_SUFFIX}`
  await mkdir(folder, { recursive: true })
  await backup(client(store), partial)
  await rename(partial, path)
  return { path, removed: [] }
}

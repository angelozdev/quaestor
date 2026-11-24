import { mkdir, readdir, rename, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { backup } from 'node:sqlite'
import { backupFileName, copiesToRemove } from '#core/backups'
import { database } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { BACKUPS_FOLDER, PARTIAL_SUFFIX } from './backups.constants.ts'
import { BackupNotWrittenError } from './backups.errors.ts'
import type { BackupRequest, BackupResult } from './backups.types.ts'

async function writeCopy(store: Store, folder: string, path: string): Promise<void> {
  const partial = `${path}${PARTIAL_SUFFIX}`
  try {
    await mkdir(folder, { recursive: true })
    await backup(database(store).$client, partial)
    await rename(partial, path)
  } catch (error) {
    await rm(partial, { force: true })
    if (!(error instanceof Error)) throw error
    throw new BackupNotWrittenError(folder, error)
  }
}

async function removeOldCopies(folder: string, env: string): Promise<string[]> {
  const removed = copiesToRemove(env, await readdir(folder)).map((name) => join(folder, name))
  await Promise.all(removed.map((path) => rm(path)))
  return removed
}

export async function backupStore({ store, env, root, now }: BackupRequest): Promise<BackupResult> {
  const folder = join(root, BACKUPS_FOLDER)
  const path = join(folder, backupFileName(env, now))
  await writeCopy(store, folder, path)
  return { path, removed: await removeOldCopies(folder, env) }
}

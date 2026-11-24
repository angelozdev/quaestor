import { link, mkdir, readdir, rm } from 'node:fs/promises'
import { basename, join } from 'node:path'
import { backup } from 'node:sqlite'
import { backupFileName, copiesToRemove } from '#core/backups'
import { database } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { BACKUPS_FOLDER, EXISTS_ERROR_CODE, PARTIAL_SUFFIX } from './backups.constants.ts'
import { BackupAlreadyExistsError, BackupNotWrittenError } from './backups.errors.ts'
import type { BackupRequest, BackupResult } from './backups.types.ts'

function alreadyExists(error: Error): boolean {
  return 'code' in error && error.code === EXISTS_ERROR_CODE
}

async function writeCopy(store: Store, folder: string, path: string): Promise<void> {
  const partial = `${path}.${process.pid}${PARTIAL_SUFFIX}`
  try {
    await mkdir(folder, { recursive: true })
    await backup(database(store).$client, partial)
    await link(partial, path)
  } catch (error) {
    if (!(error instanceof Error)) throw error
    throw alreadyExists(error)
      ? new BackupAlreadyExistsError(folder, basename(path))
      : new BackupNotWrittenError(folder, error.message)
  } finally {
    await rm(partial, { force: true })
  }
}

async function removeOldCopies(folder: string, env: string, kept: string): Promise<string[]> {
  const removed = copiesToRemove(env, await readdir(folder), kept).map((name) => join(folder, name))
  await Promise.all(removed.map((path) => rm(path, { force: true })))
  return removed
}

export async function backupStore({ store, env, root, now }: BackupRequest): Promise<BackupResult> {
  const folder = join(root, BACKUPS_FOLDER)
  const name = backupFileName(env, now)
  await writeCopy(store, folder, join(folder, name))
  return { path: join(folder, name), removed: await removeOldCopies(folder, env, name) }
}

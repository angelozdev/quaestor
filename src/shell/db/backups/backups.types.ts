import type { Store } from '../database/database.types.ts'

export type BackupRequest = { store: Store; env: string; root: string; now: Date }

export type BackupResult = { path: string; removed: string[] }

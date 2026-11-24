import { DatabaseSync } from 'node:sqlite'
import type { Client, Store } from './database.types.ts'

export function client(store: Store): Client {
  return store as unknown as Client
}

export async function openStore(path: string): Promise<Store> {
  return new DatabaseSync(path) as unknown as Store
}

export function closeStore(store: Store): void {
  client(store).close()
}

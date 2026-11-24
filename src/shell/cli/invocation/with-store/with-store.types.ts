import type { Store } from '#shell/db'
import type { Env } from '../env/env.types.ts'

export type StoreAction = (store: Store, env: Env) => Promise<unknown>

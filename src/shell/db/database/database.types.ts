import type { DatabaseSync } from 'node:sqlite'

declare const storeBrand: unique symbol

export type Store = { readonly [storeBrand]: true }

export type Client = DatabaseSync

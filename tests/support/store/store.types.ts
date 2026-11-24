import type { SQLOutputValue } from 'node:sqlite'

export type Row = Record<string, SQLOutputValue>

import { describe, expect, it } from 'vitest'
import { backupFileName } from './backups.ts'

describe('backup copies', () => {
  it('backupFileName names the copy <env>-<instant>.sqlite with the UTC instant made file-safe', () => {
    const instant = new Date('2026-11-23T21:04:05.123Z')

    expect(backupFileName('prod', instant)).toBe('prod-2026-11-23T21-04-05-123Z.sqlite')
  })
})

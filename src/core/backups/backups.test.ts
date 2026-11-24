import { describe, expect, it } from 'vitest'
import { backupFileName, copiesToRemove } from './backups.ts'

const prodCopies = [
  'prod-2026-11-01T10-00-00-000Z.sqlite',
  'prod-2026-11-02T10-00-00-000Z.sqlite',
  'prod-2026-11-03T10-00-00-000Z.sqlite',
  'prod-2026-11-04T10-00-00-000Z.sqlite',
  'prod-2026-11-05T10-00-00-000Z.sqlite',
  'prod-2026-11-06T10-00-00-000Z.sqlite',
]

const others = [
  'test-2026-10-01T10-00-00-000Z.sqlite',
  'test-2026-10-02T10-00-00-000Z.sqlite',
  'notes.txt',
  'prod-backup.sqlite',
  'prod-2026-10-01T10-00-00-000Z.sqlite.partial',
]

describe('backup copies', () => {
  it('backupFileName names the copy <env>-<instant>.sqlite with the UTC instant made file-safe', () => {
    const instant = new Date('2026-11-23T21:04:05.123Z')

    expect(backupFileName('prod', instant)).toBe('prod-2026-11-23T21-04-05-123Z.sqlite')
  })

  it('copiesToRemove keeps the newest 5 copies of the env', () => {
    const names = [...others, ...prodCopies.toReversed()]

    expect(copiesToRemove('prod', names)).toEqual(['prod-2026-11-01T10-00-00-000Z.sqlite'])
  })

  it('copiesToRemove does not count another env whose name starts the same', () => {
    expect(copiesToRemove('pro', [...prodCopies, ...others])).toEqual([])
  })

  it('copiesToRemove does not count another env whose name extends this one with a dash', () => {
    const names = prodCopies.map((name) => name.replace('prod-', 'prod-eu-'))

    expect(copiesToRemove('prod', [...names, ...prodCopies.slice(1)])).toEqual([])
  })

  it('copiesToRemove reads the env as literal text, not as a pattern', () => {
    const names = prodCopies.map((name) => name.replace('prod-', 'prXd-'))

    expect(copiesToRemove('pr.d', names)).toEqual([])
  })

  it('copiesToRemove removes nothing with five copies or fewer', () => {
    expect(copiesToRemove('prod', [...prodCopies.slice(1), ...others])).toEqual([])
  })
})

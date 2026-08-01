import type { Transaction } from "@/lib/api/types"

export function hasCounterpartLeg(tx: Transaction | null | undefined): boolean {
  return tx?.type === "transfer" && Boolean(tx.transfer_group_id)
}

export function findCounterpart(
  rows: Transaction[] | undefined,
  tx: Transaction,
): Transaction | undefined {
  if (!tx.transfer_group_id) return undefined
  return rows?.find((row) => row.transfer_group_id === tx.transfer_group_id && row.id !== tx.id)
}

export function counterpartsByTxId(rows: Transaction[] | undefined): Map<number, Transaction> {
  const legsByGroup = new Map<string, Transaction[]>()
  for (const row of rows ?? []) {
    if (!row.transfer_group_id) continue
    const legs = legsByGroup.get(row.transfer_group_id) ?? []
    legs.push(row)
    legsByGroup.set(row.transfer_group_id, legs)
  }
  const counterparts = new Map<number, Transaction>()
  for (const legs of legsByGroup.values()) {
    for (const leg of legs) {
      const other = legs.find((candidate) => candidate.id !== leg.id)
      if (other) counterparts.set(leg.id, other)
    }
  }
  return counterparts
}

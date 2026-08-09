/**
 * How a breakdown names a meta.
 *
 * The month a meta is cancelled is the last one that names it — it still
 * charged its instalment and handed back what it held — so the row says so.
 * Without that, a list of three metas gives no way to tell which one the owner
 * called off from the two still running.
 */
export function metaLabelOf(meta: { name: string; cancelled: boolean }): string {
  return meta.cancelled ? `Meta · ${meta.name} (la cancelaste)` : `Meta · ${meta.name}`
}

/** Why a meta handed money back: the owner called it off, or wanted less. */
export function gaveBackLabelOf(meta: { name: string; cancelled: boolean }): string {
  return meta.cancelled
    ? `Devuelto por ${meta.name} (la cancelaste)`
    : `Devuelto por ${meta.name} (le bajaste el monto)`
}

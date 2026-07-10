import { type Codec, p } from "./use-url-filters"

/**
 * Transaction list filters. URL param names match the API filter names 1:1
 * so the page maps values straight into TransactionFilters.
 */
export const TX_FILTER_SCHEMA = {
  date_from: p.str(),
  date_to: p.str(),
  account_id: p.int(),
  category_id: p.int(),
  tag: p.int(),
  type: p.enum(["expense", "income", "transfer"] as const),
  status: p.enum(["planned", "posted", "skipped"] as const),
} satisfies Record<string, Codec<unknown>>

/** Shared by the archive-toggle views (accounts, categories, category-groups). */
export const ARCHIVED_FILTER_SCHEMA = {
  archived: p.bool(false),
} satisfies Record<string, Codec<unknown>>

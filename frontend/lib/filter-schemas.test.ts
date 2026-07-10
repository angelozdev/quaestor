import { describe, expect, it } from "vitest"
import { ARCHIVED_FILTER_SCHEMA, TX_FILTER_SCHEMA } from "./filter-schemas"

describe("TX_FILTER_SCHEMA", () => {
  it("decodes each param to the right type", () => {
    expect(TX_FILTER_SCHEMA.account_id.decode("7")).toBe(7)
    expect(TX_FILTER_SCHEMA.type.decode("expense")).toBe("expense")
    expect(TX_FILTER_SCHEMA.status.decode("posted")).toBe("posted")
    expect(TX_FILTER_SCHEMA.type.decode("banana")).toBeNull()
    expect(TX_FILTER_SCHEMA.date_from.decode("2026-07-01")).toBe("2026-07-01")
  })
})

describe("ARCHIVED_FILTER_SCHEMA", () => {
  it("defaults archived to false and omits it when false", () => {
    expect(ARCHIVED_FILTER_SCHEMA.archived.decode(null)).toBe(false)
    expect(ARCHIVED_FILTER_SCHEMA.archived.encode(false)).toBeNull()
    expect(ARCHIVED_FILTER_SCHEMA.archived.encode(true)).toBe("true")
  })
})

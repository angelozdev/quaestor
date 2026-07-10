import { describe, expect, it } from "vitest"
import { p } from "./use-url-filters"

describe("codec: str", () => {
  const c = p.str()
  it("decodes a value and null", () => {
    expect(c.decode("2026-07-01")).toBe("2026-07-01")
    expect(c.decode(null)).toBeNull()
    expect(c.decode("")).toBeNull()
  })
  it("encodes non-empty and omits empty", () => {
    expect(c.encode("2026-07-01")).toBe("2026-07-01")
    expect(c.encode(null)).toBeNull()
    expect(c.encode("")).toBeNull()
  })
})

describe("codec: int", () => {
  const c = p.int()
  it("decodes valid ints, defaults on garbage", () => {
    expect(c.decode("3")).toBe(3)
    expect(c.decode("abc")).toBeNull()
    expect(c.decode("1.5")).toBeNull()
    expect(c.decode(null)).toBeNull()
  })
  it("encodes numbers, omits null", () => {
    expect(c.encode(3)).toBe("3")
    expect(c.encode(null)).toBeNull()
  })
})

describe("codec: enum", () => {
  const c = p.enum(["expense", "income", "transfer"] as const)
  it("decodes known values, defaults on unknown", () => {
    expect(c.decode("expense")).toBe("expense")
    expect(c.decode("banana")).toBeNull()
    expect(c.decode(null)).toBeNull()
  })
  it("encodes known values, omits null", () => {
    expect(c.encode("income")).toBe("income")
    expect(c.encode(null)).toBeNull()
  })
})

describe("codec: bool", () => {
  const c = p.bool(false)
  it("decodes true/false with default false", () => {
    expect(c.decode("true")).toBe(true)
    expect(c.decode("false")).toBe(false)
    expect(c.decode(null)).toBe(false)
  })
  it("omits the default, encodes the non-default", () => {
    expect(c.encode(false)).toBeNull()
    expect(c.encode(true)).toBe("true")
  })
})

import { renderHook } from "@testing-library/react"
import { beforeEach, vi } from "vitest"
import { useUrlFilters } from "./use-url-filters"

const replace = vi.fn()
let currentParams = new URLSearchParams("")

vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace }),
  usePathname: () => "/transactions",
}))

const SCHEMA = {
  type: p.enum(["expense", "income", "transfer"] as const),
  account_id: p.int(),
  archived: p.bool(false),
}

describe("useUrlFilters", () => {
  beforeEach(() => {
    replace.mockReset()
    currentParams = new URLSearchParams("")
  })

  it("derives typed values from the URL", () => {
    currentParams = new URLSearchParams("type=expense&account_id=3")
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    expect(result.current.values.type).toBe("expense")
    expect(result.current.values.account_id).toBe(3)
    expect(result.current.values.archived).toBe(false)
  })

  it("patch replaces the URL with the encoded param", () => {
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    result.current.patch({ type: "income" })
    expect(replace).toHaveBeenCalledWith("/transactions?type=income", { scroll: false })
  })

  it("patch to a default/null value omits the param", () => {
    currentParams = new URLSearchParams("type=expense")
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    result.current.patch({ type: null })
    expect(replace).toHaveBeenCalledWith("/transactions", { scroll: false })
  })

  it("clear removes only schema keys, preserving others", () => {
    currentParams = new URLSearchParams("type=expense&other=keep")
    const { result } = renderHook(() => useUrlFilters(SCHEMA))
    result.current.clear()
    expect(replace).toHaveBeenCalledWith("/transactions?other=keep", { scroll: false })
  })
})

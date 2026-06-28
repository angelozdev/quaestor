// @vitest-environment node
import { describe, expect, it } from "vitest"
import { buildTargetUrl } from "./build-target-url"

describe("buildTargetUrl", () => {
  it("joins path segments under /api", () => {
    const url = buildTargetUrl(["chat"], "")
    expect(url).toBe("http://localhost:8000/api/chat")
  })

  it("joins nested path segments", () => {
    const url = buildTargetUrl(["accounts", "42"], "")
    expect(url).toBe("http://localhost:8000/api/accounts/42")
  })

  it("appends search string verbatim", () => {
    const url = buildTargetUrl(["categories"], "?limit=10&offset=0")
    expect(url).toBe("http://localhost:8000/api/categories?limit=10&offset=0")
  })

  it("handles empty path (root)", () => {
    const url = buildTargetUrl([], "")
    expect(url).toBe("http://localhost:8000/api/")
  })

  it("respects a custom API_URL", () => {
    process.env.API_URL = "https://api.example.test"
    const url = buildTargetUrl(["chat"], "")
    expect(url).toBe("https://api.example.test/api/chat")
    process.env.API_URL = "http://localhost:8000"
  })
})

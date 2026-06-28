import { beforeEach, describe, expect, it, vi } from "vitest"
import { type InternalAxiosRequestConfig } from "axios"
import { http } from "./client"
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/lib/csrf"

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/`
}

describe("http client CSRF header injection (QUA-A01-01)", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("attaches X-CSRF-Token carrying the current cookie value", async () => {
    setCookie(CSRF_COOKIE_NAME, "csrf-abc")
    const adapter = vi.fn().mockResolvedValue({
      data: { ok: true },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    })
    http.defaults.adapter = adapter

    await http.get("/some/resource")

    const sent = adapter.mock.calls[0][0]
    expect(sent.headers[CSRF_HEADER_NAME]).toBe("csrf-abc")
  })

  it("uses the freshest cookie value across successive requests", async () => {
    setCookie(CSRF_COOKIE_NAME, "first")
    const adapter = vi.fn().mockResolvedValue({
      data: {},
      status: 200,
      statusText: "OK",
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    })
    http.defaults.adapter = adapter

    await http.post("/a", {})
    expect(adapter.mock.calls[0][0].headers[CSRF_HEADER_NAME]).toBe("first")

    setCookie(CSRF_COOKIE_NAME, "second")
    await http.post("/b", {})
    expect(adapter.mock.calls[1][0].headers[CSRF_HEADER_NAME]).toBe("second")
  })
})
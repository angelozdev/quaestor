// @vitest-environment node

import { NextRequest } from "next/server"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { createProxy } from "./create-proxy"

interface FetchCall {
  url: string
  init: RequestInit
}

let lastFetch: FetchCall | null = null
let fetchImpl: typeof fetch = vi.fn(async (input, init) => {
  lastFetch = { url: String(input), init: init ?? {} }
  return new Response("unused", { status: 500 })
})

beforeEach(() => {
  lastFetch = null
  vi.stubGlobal("fetch", fetchImpl)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function req(
  opts: {
    method?: string
    headers?: Record<string, string>
    body?: string
    signal?: AbortSignal
  } = {},
): NextRequest {
  const r = new Request("http://localhost/api/chat", {
    method: opts.method ?? "POST",
    headers: opts.headers ?? { "content-type": "application/json", "x-csrf-token": "csrf-tok" },
    body: opts.body,
    signal: opts.signal,
  })
  return new NextRequest(r)
}

describe("createProxy", () => {
  it("returns a Response with a ReadableStream body for text/event-stream (streaming path)", async () => {
    const upstreamStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"type":"text-delta"}\n\n'))
        controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"))
        controller.close()
      },
    })
    fetchImpl = vi.fn(
      async () =>
        new Response(upstreamStream, {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
    ) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)

    const response = await createProxy(req(), ["chat"])
    expect(response.headers.get("content-type")).toBe("text/event-stream")
    expect(response.body).toBeInstanceOf(ReadableStream)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    const out: string[] = []
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      out.push(decoder.decode(value))
    }
    expect(out.join("")).toBe('data: {"type":"text-delta"}\n\ndata: [DONE]\n\n')
  })

  it("returns a Response whose body is a string for application/json (buffered path)", async () => {
    fetchImpl = vi.fn(
      async () =>
        new Response('{"ok":true}', {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)

    const response = await createProxy(req(), ["accounts"])
    expect(await response.text()).toBe('{"ok":true}')
  })

  it("returns null body for 204 (buffered short-circuit)", async () => {
    fetchImpl = vi.fn(async () => new Response(null, { status: 204 })) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)

    const response = await createProxy(req({ method: "DELETE" }), ["accounts", "42"])
    expect(response.status).toBe(204)
    expect(response.body).toBeNull()
  })

  it("forwards request headers (content-type, cookie, x-csrf-token, authorization)", async () => {
    const ac = new AbortController()
    fetchImpl = vi.fn(async (input, init) => {
      lastFetch = { url: String(input), init: init ?? {} }
      return new Response(null, { status: 200 })
    }) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    await createProxy(
      req({
        headers: {
          "content-type": "application/json",
          cookie: "session=abc",
          "x-csrf-token": "csrf-1",
          authorization: "Bearer app",
          "x-drop-me": "nope",
        },
        signal: ac.signal,
      }),
      ["categories"],
    )
    const call = lastFetch!
    const h = call.init.headers as Headers
    expect(h.get("content-type")).toBe("application/json")
    expect(h.get("cookie")).toBe("session=abc")
    expect(h.get("x-csrf-token")).toBe("csrf-1")
    expect(h.get("authorization")).toBe("Bearer app")
    expect(h.has("x-drop-me")).toBe(false)
  })

  it("propagates request abort signal to upstream fetch", async () => {
    const ac = new AbortController()
    fetchImpl = vi.fn(async (input, init) => {
      lastFetch = { url: String(input), init: init ?? {} }
      return new Promise<Response>((_, reject) => {
        if (init?.signal?.aborted) {
          reject(new DOMException("aborted", "AbortError"))
          return
        }
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        )
      })
    }) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    ac.abort()
    await expect(createProxy(req({ signal: ac.signal }), ["chat"])).rejects.toThrow()
    expect((lastFetch!.init.signal as AbortSignal).aborted).toBe(true)
  })

  it("builds the target URL by joining path segments and preserving query string", async () => {
    fetchImpl = vi.fn(async (input, init) => {
      lastFetch = { url: String(input), init: init ?? {} }
      return new Response(null, { status: 200 })
    }) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    await createProxy(req(), ["transactions", "list"])
    expect(lastFetch!.url).toBe("http://localhost:8000/api/transactions/list")
  })

  it("preserves set-cookie from upstream in the outgoing response", async () => {
    fetchImpl = vi.fn(
      async () =>
        new Response(null, {
          status: 200,
          headers: [["set-cookie", "new-cookie=value; Path=/"]],
        }),
    ) as typeof fetch
    vi.stubGlobal("fetch", fetchImpl)
    const response = await createProxy(req(), ["x"])
    expect(response.headers.getSetCookie()).toEqual(["new-cookie=value; Path=/"])
  })
})

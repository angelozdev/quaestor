// @vitest-environment node
import { describe, expect, it } from "vitest"
import { StreamingResponsePolicy } from "./streaming-response-policy"

describe("StreamingResponsePolicy", () => {
  it("passes upstream.body through unchanged as a ReadableStream", async () => {
    const upstream = new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode("chunk-1\n"))
          controller.enqueue(new TextEncoder().encode("chunk-2\n"))
          controller.close()
        },
      }),
      {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      },
    )
    const policy = new StreamingResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(200)
    expect(out.headers.get("content-type")).toBe("text/event-stream")
    expect(out.body).toBeInstanceOf(ReadableStream)
    const reader = out.body!.getReader()
    const decoder = new TextDecoder()
    const parts: string[] = []
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      parts.push(decoder.decode(value))
    }
    expect(parts.join("")).toBe("chunk-1\nchunk-2\n")
  })

  it("handles upstream with null body (defensive)", async () => {
    const upstream = new Response(null, { status: 200 })
    const policy = new StreamingResponsePolicy()
    const out = await policy.build(upstream)
    expect(out.status).toBe(200)
    expect(out.body).toBeNull()
  })
})

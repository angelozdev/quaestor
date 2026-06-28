import type { NextRequest } from "next/server"
import { buildTargetUrl } from "./build-target-url"
import { forwardRequestHeaders } from "./forwarding/request-headers"
import { selectResponsePolicy } from "./policies/select-response-policy"

/**
 * Orchestrator for the Next.js → FastAPI rewrite. Builds the upstream URL,
 * forwards request headers, calls `fetch` with the request's AbortSignal so
 * client disconnects cancel the LLM call, then delegates response shaping
 * to the policy chosen by upstream content-type.
 *
 * Response policies (Strategy pattern):
 *  - text/* (SSE, plain text) → StreamingResponsePolicy: hands the
 *    upstream ReadableStream straight to the browser. Zero buffering.
 *  - everything else → BufferedResponsePolicy: awaits text, returns it.
 *
 * See docs/superpowers/specs/2026-06-28-chat-streaming-pass-through-design.md
 * for the design rationale.
 *
 * IMPORTANT: `await fetch(...)` resolves on response HEADERS, not body.
 * The body remains a `ReadableStream` and `StreamingResponsePolicy` hands
 * it to `new Response(stream, ...)` unchanged. Do NOT add
 * `await upstream.text()` here "for safety" — that re-introduces the
 * buffering bug this module was written to fix.
 */
export async function createProxy(req: NextRequest, path: string[]): Promise<Response> {
  const target = buildTargetUrl(path, req.nextUrl.search)
  const upstream = await fetch(target, {
    method: req.method,
    headers: forwardRequestHeaders(req),
    body: await readRequestBody(req),
    redirect: "manual",
    cache: "no-store",
    signal: req.signal,
  })
  const policy = selectResponsePolicy(upstream)
  return policy.build(upstream)
}

async function readRequestBody(req: NextRequest): Promise<BodyInit | undefined> {
  if (req.method === "GET" || req.method === "HEAD") return undefined
  return req.text()
}

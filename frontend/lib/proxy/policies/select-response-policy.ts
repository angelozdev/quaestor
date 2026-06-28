import { BufferedResponsePolicy } from "./buffered-response-policy"
import type { ResponsePolicy } from "./response-policy"
import { StreamingResponsePolicy } from "./streaming-response-policy"

/**
 * Pick a response-shaping policy from the upstream content-type. Any
 * `text/*` response (including SSE) goes through the streaming path;
 * everything else is buffered. Missing content-type falls back to
 * buffered (safe default — streaming endpoints always set the header).
 */
export function selectResponsePolicy(upstream: Response): ResponsePolicy {
  const contentType = upstream.headers.get("content-type") ?? ""
  if (contentType.toLowerCase().startsWith("text/")) {
    return new StreamingResponsePolicy()
  }
  return new BufferedResponsePolicy()
}

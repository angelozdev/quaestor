/**
 * Strategy for shaping the outgoing browser response from an upstream
 * backend response. Two implementations: streaming (SSE / text/*) and
 * buffered (JSON / 204 / 304). Selected by content-type at runtime.
 */
export interface ResponsePolicy {
  build(upstream: Response): Response | Promise<Response>
}

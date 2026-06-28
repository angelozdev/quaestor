/**
 * Compose the backend URL for the rewrite proxy.
 * Single source of truth for "how does /api/<x> map to upstream".
 */
export function buildTargetUrl(path: string[], search: string): string {
  const base = process.env.API_URL ?? "http://localhost:8000"
  return `${base}/api/${path.join("/")}${search}`
}

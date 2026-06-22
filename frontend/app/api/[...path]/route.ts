import { type NextRequest, NextResponse } from "next/server"

const API_URL = process.env.API_URL ?? "http://localhost:8000"

async function proxy(req: NextRequest, path: string[]) {
  const target = `${API_URL}/api/${path.join("/")}${req.nextUrl.search}`

  const headers: Record<string, string> = {}
  const contentType = req.headers.get("content-type")
  if (contentType) headers["content-type"] = contentType
  const cookie = req.headers.get("cookie")
  if (cookie) headers.cookie = cookie

  const hasBody = req.method !== "GET" && req.method !== "HEAD"
  const body = hasBody ? await req.text() : undefined

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store",
  })

  const noBody = upstream.status === 204 || upstream.status === 205 || upstream.status === 304
  const res = new NextResponse(noBody ? null : await upstream.text(), { status: upstream.status })
  const upstreamContentType = upstream.headers.get("content-type")
  if (upstreamContentType) res.headers.set("content-type", upstreamContentType)
  for (const c of upstream.headers.getSetCookie()) res.headers.append("set-cookie", c)
  return res
}

type Ctx = { params: Promise<{ path: string[] }> }

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}

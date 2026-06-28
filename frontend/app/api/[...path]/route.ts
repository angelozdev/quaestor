import type { NextRequest } from "next/server"
import { createProxy } from "@/lib/proxy/create-proxy"

type Ctx = { params: Promise<{ path: string[] }> }

const handler = async (req: NextRequest, ctx: Ctx) => createProxy(req, (await ctx.params).path)

export const GET = handler
export const POST = handler
export const PATCH = handler
export const DELETE = handler

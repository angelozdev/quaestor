import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cancelMeta,
  closeMeta,
  contribute,
  createMeta,
  listArchived,
  listContributions,
  listMetas,
  monthSplit,
  previewMeta,
  removeContribution,
  restoreMeta,
  setMeta,
} from "./metas"

/**
 * Every screen that talks about metas mocks this module, so until this file
 * ran, not one of its twelve functions was executed by any test. The screens
 * are covered and the router is covered; the joint between them — twelve
 * verbs, twelve paths, and the month that rides along on nine of them — was
 * asserted by nobody, and a `post` where a `patch` belongs would have left
 * every other test green.
 *
 * `qs` is deliberately left real: the month in the query string is half of
 * what a wrong call would get wrong, and a stubbed query builder would hide
 * exactly that.
 */
const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))

vi.mock("./client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./client")>()),
  get,
  post,
  patch,
  del,
}))

const MONTH = "2026-08"
const META_ID = 7

const A_META = {
  name: "Televisor",
  amount: 500_000_000,
  target_month: "2026-12",
  currency: "COP",
  stated_opening: null,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("reading metas", () => {
  it("asks for the metas of one month", () => {
    listMetas(MONTH)
    expect(get).toHaveBeenCalledWith(`/metas?month=${MONTH}`)
  })

  it("asks for the cancelled ones without naming a month", () => {
    listArchived()
    expect(get).toHaveBeenCalledWith("/metas/archived")
  })

  it("asks how one month splits", () => {
    monthSplit(MONTH)
    expect(get).toHaveBeenCalledWith(`/metas/split?month=${MONTH}`)
  })

  it("asks what one meta has been given by hand", () => {
    listContributions(META_ID)
    expect(get).toHaveBeenCalledWith(`/metas/${META_ID}/contributions`)
  })
})

describe("writing metas", () => {
  it("asks what a meta would cost before creating it", () => {
    previewMeta(MONTH, A_META)
    expect(post).toHaveBeenCalledWith(`/metas/preview?month=${MONTH}`, A_META)
  })

  it("creates a meta in the month the owner is looking at", () => {
    createMeta(MONTH, A_META)
    expect(post).toHaveBeenCalledWith(`/metas?month=${MONTH}`, A_META)
  })

  it("edits a meta with a patch, so untouched fields stay untouched", () => {
    setMeta(META_ID, MONTH, { amount: 600_000_000 })
    expect(patch).toHaveBeenCalledWith(`/metas/${META_ID}?month=${MONTH}`, { amount: 600_000_000 })
    expect(post).not.toHaveBeenCalled()
  })

  it("sets money aside against the month it was set aside in", () => {
    contribute(META_ID, MONTH, 25_000_000)
    expect(post).toHaveBeenCalledWith(`/metas/${META_ID}/contributions?month=${MONTH}`, {
      amount: 25_000_000,
    })
  })
})

describe("ending and reviving a meta", () => {
  it("cancels a meta by deleting it, naming the month the money is freed in", () => {
    cancelMeta(META_ID, MONTH)
    expect(del).toHaveBeenCalledWith(`/metas/${META_ID}?month=${MONTH}`)
  })

  it("closes a meta at its own address, which is not the cancel address", () => {
    closeMeta(META_ID, MONTH)
    expect(post).toHaveBeenCalledWith(`/metas/${META_ID}/close?month=${MONTH}`, {})
    expect(del).not.toHaveBeenCalled()
  })

  it("restores a meta at its own address", () => {
    restoreMeta(META_ID, MONTH)
    expect(post).toHaveBeenCalledWith(`/metas/${META_ID}/restore?month=${MONTH}`, {})
  })

  it("removes a contribution by its own id, not by the meta's", () => {
    removeContribution(31)
    expect(del).toHaveBeenCalledWith("/metas/contributions/31")
  })
})

describe("the month a screen is looking at", () => {
  it("rides on every call whose answer depends on it", () => {
    listMetas(MONTH)
    monthSplit(MONTH)
    previewMeta(MONTH, A_META)
    createMeta(MONTH, A_META)
    setMeta(META_ID, MONTH, {})
    contribute(META_ID, MONTH, 1)
    cancelMeta(META_ID, MONTH)
    closeMeta(META_ID, MONTH)
    restoreMeta(META_ID, MONTH)

    const urls = [
      ...get.mock.calls,
      ...post.mock.calls,
      ...patch.mock.calls,
      ...del.mock.calls,
    ].map(([url]) => url as string)
    expect(urls).toHaveLength(9)
    for (const url of urls) expect(url).toContain(`?month=${MONTH}`)
  })

  it("stays off the two calls that answer the same whenever they are asked", () => {
    listArchived()
    listContributions(META_ID)
    removeContribution(31)

    const urls = [...get.mock.calls, ...del.mock.calls].map(([url]) => url as string)
    for (const url of urls) expect(url).not.toContain("month")
  })
})

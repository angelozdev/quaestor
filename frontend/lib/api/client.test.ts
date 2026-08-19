import { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { afterEach, describe, expect, it, vi } from "vitest"
import { http } from "./client"
import { ApiError, setUnauthorizedHandler } from "./types"

describe("ApiError", () => {
  it("exposes fields when constructed with a fields map", () => {
    const err = new ApiError(422, "ValidationError", "invalid", {
      amount: "must be > 0",
    })
    expect(err.status).toBe(422)
    expect(err.code).toBe("ValidationError")
    expect(err.message).toBe("invalid")
    expect(err.fields).toEqual({ amount: "must be > 0" })
  })

  it("defaults fields to an empty object when omitted", () => {
    const err = new ApiError(500, "Internal", "boom")
    expect(err.fields).toEqual({})
  })

  it("matches the shape produced by the 422 backend response", () => {
    const err = new ApiError(
      422,
      "ValidationError",
      "amount: must be greater than 0; interval_count: must be greater than 0",
      {
        amount: "must be greater than 0",
        interval_count: "must be greater than 0",
      },
    )
    expect(err.fields.amount).toBe("must be greater than 0")
    expect(err.fields.interval_count).toBe("must be greater than 0")
  })
})

const BACKEND_401 = { error: "Unauthorized", detail: "credentials required or invalid" }

function refusingWith(status: number, data: unknown) {
  return vi.fn((config: InternalAxiosRequestConfig) =>
    Promise.reject(
      new AxiosError(`Request failed with status code ${status}`, "ERR_BAD_REQUEST", config, null, {
        data,
        status,
        statusText: "",
        headers: {},
        config,
      }),
    ),
  )
}

describe("http client on an expired session", () => {
  const original = http.defaults.adapter

  afterEach(() => {
    http.defaults.adapter = original
    setUnauthorizedHandler(null)
  })

  it("refuses the write instead of resolving it as a saved movement", async () => {
    http.defaults.adapter = refusingWith(401, BACKEND_401)

    await expect(http.patch("/transactions/1", { payee: "Exito" })).rejects.toBeInstanceOf(ApiError)
  })

  it("still hands the expired session to the handler that redirects", async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    http.defaults.adapter = refusingWith(401, BACKEND_401)

    await expect(http.post("/transactions/1/correction", { amount: 1 })).rejects.toThrow()
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it("says in Spanish that the session expired, never the backend's English", async () => {
    http.defaults.adapter = refusingWith(401, BACKEND_401)

    const refusal = await http.patch("/transactions/1", {}).catch((e: unknown) => e)

    expect(refusal).toBeInstanceOf(ApiError)
    expect((refusal as ApiError).status).toBe(401)
    expect((refusal as ApiError).message).toBe(
      "Tu sesión expiró. Vuelve a iniciar sesión e inténtalo de nuevo.",
    )
  })

  it("leaves a refused login to the login screen, with no redirect of its own", async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    http.defaults.adapter = refusingWith(401, { error: "Unauthorized", detail: "invalid password" })

    await expect(http.post("/auth/login", { password: "nope" })).rejects.toBeInstanceOf(ApiError)
    expect(handler).not.toHaveBeenCalled()
  })
})

describe("http client carries a coded refusal's data through the real interceptor", () => {
  const original = http.defaults.adapter

  afterEach(() => {
    http.defaults.adapter = original
  })

  it("puts the backend's data key onto ApiError.data, not just code and detail", async () => {
    http.defaults.adapter = refusingWith(422, {
      error: "category_duplicate_active",
      detail: "an expense category named 'Transporte' already exists",
      data: { name: "Transporte", direction: "expense" },
    })

    const refusal = await http.post("/categories", { name: "Transporte" }).catch((e: unknown) => e)

    expect(refusal).toBeInstanceOf(ApiError)
    expect((refusal as ApiError).code).toBe("category_duplicate_active")
    expect((refusal as ApiError).data).toEqual({ name: "Transporte", direction: "expense" })
  })

  it("defaults data to an empty object when the backend sends none", async () => {
    http.defaults.adapter = refusingWith(404, { error: "NotFound", detail: "account 9 not found" })

    const refusal = await http.get("/accounts/9").catch((e: unknown) => e)

    expect((refusal as ApiError).data).toEqual({})
  })
})

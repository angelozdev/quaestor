import { describe, expect, it } from "vitest"
import { ERROR_CATALOG, translateApiError } from "./error-catalog"
import { ApiError } from "./types"

describe("ERROR_CATALOG", () => {
  it("category_duplicate_active names an expense category by default", () => {
    expect(
      ERROR_CATALOG.category_duplicate_active({ name: "Transporte", direction: "expense" }),
    ).toBe("Ya existe una categoría de gasto llamada «Transporte»")
  })

  it("category_duplicate_active names an income category", () => {
    expect(ERROR_CATALOG.category_duplicate_active({ name: "Salario", direction: "income" })).toBe(
      "Ya existe una categoría de ingreso llamada «Salario»",
    )
  })

  it("category_duplicate_archived offers to restore instead of creating", () => {
    expect(
      ERROR_CATALOG.category_duplicate_archived({ name: "Transporte", direction: "expense" }),
    ).toBe(
      "Ya existe una categoría de gasto archivada llamada «Transporte». Restaurarla en vez de crear otra.",
    )
  })

  it("category_duplicate_archived names an archived income category", () => {
    expect(
      ERROR_CATALOG.category_duplicate_archived({ name: "Salario", direction: "income" }),
    ).toBe(
      "Ya existe una categoría de ingreso archivada llamada «Salario». Restaurarla en vez de crear otra.",
    )
  })

  it("amount_not_positive ignores its data", () => {
    expect(ERROR_CATALOG.amount_not_positive({})).toBe("El monto debe ser mayor que cero")
  })
})

describe("translateApiError", () => {
  it("translates a known code using its data", () => {
    const err = new ApiError(
      422,
      "category_duplicate_active",
      "Ya existe una categoría de gasto llamada «Transporte»",
      undefined,
      { name: "Transporte", direction: "expense" },
    )
    expect(translateApiError(err)).toBe("Ya existe una categoría de gasto llamada «Transporte»")
  })

  it("falls back to the raw message for an unknown code", () => {
    const err = new ApiError(409, "no_trm_set", "no TRM set — set the USD→COP rate (TRM) first")
    expect(translateApiError(err)).toBe("no TRM set — set the USD→COP rate (TRM) first")
  })
})

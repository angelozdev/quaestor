import { renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { useRetained } from "./use-retained"

describe("useRetained", () => {
  it("returns the live value while active", () => {
    const { result, rerender } = renderHook(({ v }) => useRetained(true, v), {
      initialProps: { v: "QA Motor" },
    })
    expect(result.current).toBe("QA Motor")
    rerender({ v: "Netflix" })
    expect(result.current).toBe("Netflix")
  })

  it("keeps the last active value once it goes inactive", () => {
    const { result, rerender } = renderHook(({ active, v }) => useRetained(active, v), {
      initialProps: { active: true, v: 'Se desactivará "QA Motor".' },
    })
    rerender({ active: false, v: 'Se desactivará "undefined".' })
    expect(result.current).toBe('Se desactivará "QA Motor".')
  })

  it("picks up the new value when it becomes active again", () => {
    const { result, rerender } = renderHook(({ active, v }) => useRetained(active, v), {
      initialProps: { active: true, v: "QA Motor" },
    })
    rerender({ active: false, v: "undefined" })
    rerender({ active: true, v: "Salario" })
    expect(result.current).toBe("Salario")
  })
})

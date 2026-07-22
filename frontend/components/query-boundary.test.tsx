import { act, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { QueryBoundary } from "./query-boundary"

const base = { isPending: false, isError: false, data: undefined, refetch: vi.fn() }

describe("QueryBoundary", () => {
  it("shows the skeleton immediately when delayMs is 0", () => {
    render(
      <QueryBoundary
        query={{ ...base, isPending: true }}
        skeleton={<div>loading…</div>}
        delayMs={0}
      >
        {() => <div>data</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("loading…")).toBeInTheDocument()
  })

  it("holds the skeleton back for delayMs, then shows it (anti-flash)", () => {
    vi.useFakeTimers()
    try {
      render(
        <QueryBoundary query={{ ...base, isPending: true }} skeleton={<div>loading…</div>}>
          {() => <div>data</div>}
        </QueryBoundary>,
      )
      expect(screen.queryByText("loading…")).not.toBeInTheDocument()
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(screen.getByText("loading…")).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it("shows the error state with a retry button when there is no data", () => {
    const refetch = vi.fn()
    render(
      <QueryBoundary
        query={{ ...base, isError: true, refetch }}
        skeleton={<div>loading…</div>}
        errorMessage="Falló"
      >
        {() => <div>data</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("Falló")).toBeInTheDocument()
    screen.getByRole("button", { name: /reintentar/i }).click()
    expect(refetch).toHaveBeenCalled()
  })

  it("keeps data visible when a background refetch fails", () => {
    const refetch = vi.fn()
    render(
      <QueryBoundary
        query={{ ...base, isError: true, data: 42, refetch }}
        skeleton={<div>loading…</div>}
      >
        {(n) => <div>value {n}</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("value 42")).toBeInTheDocument()
    expect(screen.getByRole("alert")).toBeInTheDocument()
    screen.getByRole("button", { name: /reintentar/i }).click()
    expect(refetch).toHaveBeenCalled()
  })

  it("shows the empty node when the empty predicate matches", () => {
    render(
      <QueryBoundary
        query={{ ...base, data: [] as number[] }}
        skeleton={<div>loading…</div>}
        empty={{ when: (d) => d.length === 0, node: <div>vacío</div> }}
      >
        {() => <div>data</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("vacío")).toBeInTheDocument()
  })

  it("renders children with data on success", () => {
    render(
      <QueryBoundary query={{ ...base, data: 42 }} skeleton={<div>loading…</div>}>
        {(n) => <div>value {n}</div>}
      </QueryBoundary>,
    )
    expect(screen.getByText("value 42")).toBeInTheDocument()
  })
})

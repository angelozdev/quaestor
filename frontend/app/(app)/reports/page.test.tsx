import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { MonthlyReport } from "@/lib/api/types"
import { openHelpPanel, queryWrapper } from "@/tests/factories"

const { report } = vi.hoisted(() => ({ report: vi.fn() }))
vi.mock("@/lib/api/reports", () => ({ report }))

import ReportsPage from "./page"

const RESTAURANTES_IS_A_CEILING: MonthlyReport = {
  month: "2026-08",
  income: 300_000_000,
  expense: 6_000_000,
  net: 294_000_000,
  funds_summary: { n_on_track: 1, n_behind: 0, set_aside: 0 },
  funds: [
    {
      category_name: "Restaurantes",
      asks: 10_000_000,
      holds: 0,
      spent: 6_000_000,
      on_track: true,
    },
  ],
  by_category: [],
  by_group: [],
  balances: [],
  drift_mom: null,
  usd_share: 0,
  pending: [],
  available: {
    year_month: "2026-08",
    income: 300_000_000,
    funds: [
      {
        fund_id: 1,
        category_id: 7,
        name: "Restaurantes",
        year_month: "2026-08",
        rule: "fixed",
        asks: 10_000_000,
        holds: 0,
        spent: 6_000_000,
        carries: 0,
        next_month_has: 10_000_000,
        accumulates: false,
        accumulation_is_implied: false,
        on_track: true,
        averaged_over: null,
        spreads_over: null,
        whole_by: null,
      },
    ],
    uncovered: 0,
    free: 290_000_000,
  },
  markdown: "",
}

beforeEach(() => {
  vi.clearAllMocks()
  report.mockResolvedValue(RESTAURANTES_IS_A_CEILING)
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("The Reportes breakdown calls a presupuesto a presupuesto", async () => {
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("Presupuesto · Restaurantes")).toBeInTheDocument()
    expect(screen.queryByText("Fondo · Restaurantes")).not.toBeInTheDocument()
  })
})

describe("AC-7 — every screen carries the same control", () => {
  it("Reportes offers to explain itself", async () => {
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(await openHelpPanel("Reportes")).toHaveTextContent(
      "Este reporte muestra a dónde se fue el gasto del mes",
    )
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Reportes screen teaches what it would show", async () => {
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(
      await screen.findByText(/Este reporte muestra a dónde se fue el gasto del mes/),
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Registrar un movimiento" })).toHaveAttribute(
      "href",
      "/transactions",
    )
  })
})

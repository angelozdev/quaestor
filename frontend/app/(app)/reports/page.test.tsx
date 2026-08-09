import { render, screen, within } from "@testing-library/react"
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
  metas: [{ meta_name: "Celular", currency: "COP", asks: 1_600_000, holds: 3_200_000 }],
  asked: 11_600_000,
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
    metas: [],
    contributed: 0,
    released: 0,
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

describe("AC-4 — the breakdown states what the metas ask", () => {
  const withMetas: MonthlyReport = {
    ...RESTAURANTES_IS_A_CEILING,
    available: {
      ...RESTAURANTES_IS_A_CEILING.available,
      income: 500_000_000,
      metas: [
        {
          meta_id: 1,
          name: "Celular",
          year_month: "2026-08",
          amount: 800_000_000,
          currency: "COP",
          target_month: "2026-12",
          asks: 160_000_000,
          asks_cop: 160_000_000,
          holds: 160_000_000,
          progress: 20,
          complete: false,
          closed: false,
          waiting: false,
          cancelled: true,
          released: 30_000_000,
        },
      ],
      contributed: 50_000_000,
      released: 30_000_000,
      uncovered: 0,
      free: 310_000_000,
    },
  }

  it("names each meta beside the funds, with what it asks", async () => {
    report.mockResolvedValue(withMetas)
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("Meta · Celular (la cancelaste)")).toBeInTheDocument()
    expect(screen.getByText("$ 1.600.000")).toBeInTheDocument()
  })

  it("names what was put by hand and what a cancelled meta gave back", async () => {
    report.mockResolvedValue(withMetas)
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("Puesto a mano en una meta")).toBeInTheDocument()
    expect(screen.getByText("$ 500.000")).toBeInTheDocument()
    expect(screen.getByText("Devuelto por Celular (la cancelaste)")).toBeInTheDocument()
    expect(screen.getByText("$ -300.000")).toBeInTheDocument()
  })

  it("says nothing about hands or cancellations in a month that had neither", async () => {
    report.mockResolvedValue(RESTAURANTES_IS_A_CEILING)
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("Presupuesto · Restaurantes")).toBeInTheDocument()
    expect(screen.queryByText("Puesto a mano en una meta")).not.toBeInTheDocument()
    expect(screen.queryByText(/Devuelto por/)).not.toBeInTheDocument()
  })
})

describe("AC-36 — the report lists the metas beside the funds, and totals both", () => {
  it("Every meta is named with what it asks and what it carries", async () => {
    report.mockResolvedValue(RESTAURANTES_IS_A_CEILING)
    render(<ReportsPage />, { wrapper: queryWrapper })

    const metas = (await screen.findByRole("heading", { name: "Metas" })).closest("div")
    expect(within(metas as HTMLElement).getByText("Celular")).toBeInTheDocument()
    expect(within(metas as HTMLElement).getByText("$ 16.000")).toBeInTheDocument()
    expect(within(metas as HTMLElement).getByText("$ 32.000")).toBeInTheDocument()
  })

  it("The month says what it asks between the two", async () => {
    report.mockResolvedValue(RESTAURANTES_IS_A_CEILING)
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(
      await screen.findByText(/Entre fondos y metas, el mes pide \$ 116\.000/),
    ).toBeInTheDocument()
  })

  it("A meta is never listed as a category", async () => {
    report.mockResolvedValue(RESTAURANTES_IS_A_CEILING)
    render(<ReportsPage />, { wrapper: queryWrapper })

    const funds = (await screen.findByRole("heading", { name: "Fondos y presupuestos" })).closest(
      "div",
    )
    expect(within(funds as HTMLElement).queryByText("Celular")).not.toBeInTheDocument()
  })

  it("A month with no metas says so and still totals the funds", async () => {
    report.mockResolvedValue({ ...RESTAURANTES_IS_A_CEILING, metas: [], asked: 10_000_000 })
    render(<ReportsPage />, { wrapper: queryWrapper })

    expect(await screen.findByText("Sin metas este mes")).toBeInTheDocument()
    expect(screen.getByText(/Entre fondos y metas, el mes pide \$ 100\.000/)).toBeInTheDocument()
  })
})

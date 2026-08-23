import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import type { MonthlyReport, Trend } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { queryWrapper } from "@/tests/factories"

const { report } = vi.hoisted(() => ({ report: vi.fn() }))
vi.mock("@/lib/api/reports", () => ({ report }))

import ReportsPage from "./page"

beforeAll(() => {
  Element.prototype.getBoundingClientRect = () =>
    ({
      width: 960,
      height: 320,
      top: 0,
      left: 0,
      right: 960,
      bottom: 320,
      x: 0,
      y: 0,
      toJSON() {},
    }) as DOMRect
})

const EMPTY_TREND: Trend = {
  window_start: "2025-09",
  window_end: "2026-08",
  months: [],
  categories: [],
}

const BASE_REPORT: MonthlyReport = {
  month: "2026-08",
  income: 0,
  expense: 0,
  net: 0,
  funds_summary: { n_on_track: 0, n_behind: 0, set_aside: 0 },
  funds: [],
  metas: [],
  asked: 0,
  by_category: [],
  by_group: [],
  balances: [],
  drift_mom: null,
  usd_share: 0,
  pending: [],
  available: {
    year_month: "2026-08",
    income: 0,
    funds: [],
    metas: [],
    contributed: 0,
    released: 0,
    uncovered: 0,
    free: 0,
  },
  trend: EMPTY_TREND,
  markdown: "",
}

async function openEvolucionTab() {
  const user = userEvent.setup()
  render(<ReportsPage />, { wrapper: queryWrapper })
  await user.click(await screen.findByRole("tab", { name: "Evolución" }))
  return user
}

describe("AC-4 — cada barra muestra su total en pesos, arriba", () => {
  const JUNE_TOTAL = 500_000_00
  const JULY_TOTAL = 650_000_00
  const AUGUST_TOTAL = 480_000_00

  const withThreeMonths: MonthlyReport = {
    ...BASE_REPORT,
    trend: {
      window_start: "2026-06",
      window_end: "2026-08",
      months: [
        {
          month: "2026-06",
          total: JUNE_TOTAL,
          by_group: { Comida: 300_000_00, Transporte: 200_000_00 },
        },
        {
          month: "2026-07",
          total: JULY_TOTAL,
          by_group: { Comida: 400_000_00, Transporte: 250_000_00 },
        },
        {
          month: "2026-08",
          total: AUGUST_TOTAL,
          by_group: { Comida: 280_000_00, Transporte: 200_000_00 },
        },
      ],
      categories: [
        {
          category: "Restaurantes",
          group: "Comida",
          total: 980_000_00,
          by_month: { "2026-06": 300_000_00, "2026-07": 400_000_00, "2026-08": 280_000_00 },
        },
        {
          category: "Gasolina",
          group: "Transporte",
          total: 650_000_00,
          by_month: { "2026-06": 200_000_00, "2026-07": 250_000_00, "2026-08": 200_000_00 },
        },
      ],
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    report.mockResolvedValue(withThreeMonths)
  })

  it("Each month's bar states its own total, in pesos, above the bar", async () => {
    await openEvolucionTab()

    expect(await screen.findByText(formatCents(JUNE_TOTAL, "COP"))).toBeInTheDocument()
    expect(screen.getByText(formatCents(JULY_TOTAL, "COP"))).toBeInTheDocument()
    expect(screen.getByText(formatCents(AUGUST_TOTAL, "COP"))).toBeInTheDocument()
  })

  it("lists the matrix table with one row per category and one column per month", async () => {
    await openEvolucionTab()

    const restaurantes = await screen.findByText("Restaurantes")
    const row = restaurantes.closest("tr")
    expect(row).not.toBeNull()
    expect(row).toHaveTextContent(formatCents(300_000_00, "COP"))
    expect(row).toHaveTextContent(formatCents(400_000_00, "COP"))
    expect(row).toHaveTextContent(formatCents(280_000_00, "COP"))
  })
})

describe('AC-10 — sin gastos, mismo estado vacío que "Mes"', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    report.mockResolvedValue(BASE_REPORT)
  })

  it('A fresh install with no expenses shows the same empty state as "Mes"', async () => {
    await openEvolucionTab()

    expect(await screen.findByText("Sin gastos este mes")).toBeInTheDocument()
  })
})

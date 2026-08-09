import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { HELP_LABEL } from "@/components/screen-help"
import { openHelpPanel } from "@/tests/factories"

const { moneyAvailable, moneyRates, report, listAccounts, toPay, monthSplit } = vi.hoisted(() => ({
  moneyAvailable: vi.fn(),
  monthSplit: vi.fn(),
  moneyRates: vi.fn(),
  report: vi.fn(),
  listAccounts: vi.fn(),
  toPay: vi.fn(),
}))

vi.mock("@/lib/api/funds", () => ({ moneyAvailable, moneyRates }))

/** The dashboard reads the month's terms out of the report payload — the same
 * MonthAvailable the /funds/available endpoint answers with, embedded. */
function showing(available: unknown) {
  report.mockResolvedValue({ income: 0, expense: 0, net: 0, available })
}
vi.mock("@/lib/api/metas", () => ({ monthSplit }))
vi.mock("@/lib/api/reports", () => ({ report }))
vi.mock("@/lib/api/accounts", () => ({ listAccounts }))
vi.mock("@/lib/api/planned", () => ({ toPay, confirmPayment: vi.fn() }))
vi.mock("@/components/chat/chat-section", () => ({ ChatSection: () => null }))

import DashboardPage from "./page"

const AVAILABLE = {
  year_month: "2026-11",
  income: 500_000_000,
  funds: [
    {
      fund_id: 1,
      category_id: 7,
      name: "Restaurantes",
      year_month: "2026-11",
      rule: "fixed",
      asks: 20_000_000,
      holds: 0,
      accumulates: true,
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
  uncovered: 15_000_000,
  free: 465_000_000,
}

const RATES = { year_month: "2026-11", earning: 600_000_000, cost: 35_000_000, margin: 565_000_000 }

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DashboardPage />
    </QueryClientProvider>,
  )
}

const hero = (container: HTMLElement) => container.querySelector('[data-slot="money-available"]')

beforeEach(() => {
  vi.clearAllMocks()
  showing(AVAILABLE)
  moneyRates.mockResolvedValue(RATES)
  listAccounts.mockResolvedValue([])
  toPay.mockResolvedValue({ overdue: [], upcoming: [], total_base: 0 })
  monthSplit.mockResolvedValue({
    year_month: "2026-11",
    income: 0,
    consumo: 0,
    ahorro: 0,
    libre: 0,
    ahorro_share: 0,
    set_aside: 0,
    set_aside_share: 0,
    released: 0,
    gave_back: [],
  })
})

describe("DashboardPage breakdown", () => {
  it("adds up: income minus every fund minus what no fund covers is the money available", async () => {
    const { container } = renderPage()
    await waitFor(() => expect(hero(container)).toHaveTextContent("$ 4.650.000"))

    const income = AVAILABLE.income
    const asked = AVAILABLE.funds.reduce((total, fund) => total + fund.asks, 0)
    expect(income - asked - AVAILABLE.uncovered).toBe(AVAILABLE.free)

    expect(screen.getByText("$ 5.000.000")).toBeInTheDocument()
    expect(screen.getByText("$ 200.000")).toBeInTheDocument()
    expect(screen.getByText("$ 150.000")).toBeInTheDocument()
    expect(screen.getAllByText("$ 4.650.000").length).toBeGreaterThan(0)
  })

  it("names each fund in the breakdown", async () => {
    renderPage()
    expect(await screen.findByText("Fondo · Restaurantes")).toBeInTheDocument()
  })
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("The Dashboard breakdown calls a presupuesto a presupuesto", async () => {
    showing({
      ...AVAILABLE,
      income: 300_000_000,
      funds: [{ ...AVAILABLE.funds[0], accumulates: false, asks: 10_000_000 }],
    })
    renderPage()

    expect(await screen.findByText("Presupuesto · Restaurantes")).toBeInTheDocument()
    expect(screen.queryByText("Fondo · Restaurantes")).not.toBeInTheDocument()
  })
})

const ASKING_TOO_MUCH = {
  ...AVAILABLE,
  income: 300_000_000,
  funds: [
    { ...AVAILABLE.funds[0], fund_id: 1, category_id: 10, name: "Mercado", asks: 1_000_000_000 },
    {
      ...AVAILABLE.funds[0],
      fund_id: 2,
      category_id: 7,
      name: "Restaurantes",
      asks: 8_900_000,
      accumulates: false,
    },
  ],
  uncovered: 0,
  free: -708_900_000,
}

const openHelp = () => openHelpPanel("Dashboard")

describe("AC-7 — every screen carries the same control", () => {
  it("The Dashboard offers to explain itself", async () => {
    renderPage()

    expect(await screen.findByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
    expect(await openHelp()).toHaveTextContent("Esta pantalla resume el mes")
  })
})

describe("AC-8 — the panel explains the screen using the owner's own figures", () => {
  beforeEach(() => {
    showing(ASKING_TOO_MUCH)
  })

  it("The panel states what came in and what each fund asked for", async () => {
    renderPage()
    const panel = await openHelp()

    expect(panel).toHaveTextContent("Este mes entran $ 3.000.000.")
    expect(panel).toHaveTextContent("Mercado (fondo) — pide $ 10.000.000")
    expect(panel).toHaveTextContent("Restaurantes (presupuesto) — pide $ 89.000")
  })

  it("The panel singles out the one fund asking more than the month brings in", async () => {
    renderPage()
    const panel = await openHelp()

    const flagged = within(panel)
      .getByRole("list", { name: "Pide más de lo que entra este mes" })
      .querySelectorAll("li")

    expect(flagged).toHaveLength(1)
    expect(flagged[0]).toHaveTextContent("Mercado")
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Dashboard teaches where its figures come from", async () => {
    report.mockResolvedValue({ income: 0, expense: 0, net: 0, available: AVAILABLE })
    renderPage()

    expect(
      await screen.findByText(/Las cifras de esta pantalla salen de los movimientos que registres/),
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Registrar el primero" })).toHaveAttribute(
      "href",
      "/transactions",
    )
  })
})

describe("DashboardPage keeps the money available and the rates apart", () => {
  it("labels them as different figures and shows both", async () => {
    const { container } = renderPage()
    await waitFor(() => expect(hero(container)).toHaveTextContent("$ 4.650.000"))

    expect(screen.getByText(/Disponible este mes ·/)).toBeInTheDocument()

    expect(await screen.findByText("Ganas al mes")).toBeInTheDocument()
    expect(screen.getByText("$ 6.000.000")).toBeInTheDocument()
    expect(screen.getByText("Cuestas al mes")).toBeInTheDocument()
    expect(screen.getByText("$ 350.000")).toBeInTheDocument()
    expect(screen.getByText("Margen")).toBeInTheDocument()
    expect(screen.getByText("$ 5.650.000")).toBeInTheDocument()

    expect(screen.getByText(/Una tasa no es el disponible/)).toBeInTheDocument()
  })
})

describe("AC-4 — the breakdown states what the metas ask", () => {
  it("names each meta, what was put by hand, and what a cancelled one gave back", async () => {
    showing({
      ...AVAILABLE,
      metas: [
        {
          meta_id: 1,
          name: "Celular",
          year_month: "2026-11",
          amount: 800_000_000,
          currency: "COP",
          target_month: "2026-12",
          asks: 160_000_000,
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
    })
    renderPage()

    expect(await screen.findByText("Meta · Celular (la cancelaste)")).toBeInTheDocument()
    expect(screen.getByText("$ 1.600.000")).toBeInTheDocument()
    expect(screen.getByText("Puesto a mano en una meta")).toBeInTheDocument()
    expect(screen.getByText("Devuelto por Celular (la cancelaste)")).toBeInTheDocument()
    expect(screen.getByText("$ -300.000")).toBeInTheDocument()
  })

  it("stays quiet about metas in a month that has none", async () => {
    renderPage()

    expect(await screen.findByText("Sin fondo que lo cubra")).toBeInTheDocument()
    expect(screen.queryByText("Puesto a mano en una meta")).not.toBeInTheDocument()
    expect(screen.queryByText(/Devuelto por/)).not.toBeInTheDocument()
  })
})

const CELULAR = {
  meta_id: 1,
  name: "Celular",
  year_month: "2026-11",
  amount: 800_000_000,
  currency: "COP",
  target_month: "2026-12",
  asks: 0,
  holds: 320_000_000,
  progress: 40,
  complete: false,
  closed: false,
  waiting: false,
  cancelled: true,
  released: 320_000_000,
}

describe("AC-37 — the month opens into consumo, ahorro and libre", () => {
  const SPLIT = {
    year_month: "2026-11",
    income: 500_000_000,
    consumo: 140_000_000,
    ahorro: 320_000_000,
    libre: 40_000_000,
    ahorro_share: 64,
    set_aside: 320_000_000,
    set_aside_share: 64,
    released: 0,
    gave_back: [],
  }

  it("says what share of the month was saved, and adds up to the income", async () => {
    monthSplit.mockResolvedValue(SPLIT)
    renderPage()

    expect(await screen.findByText("Ahorro · fondos y metas")).toBeInTheDocument()
    expect(screen.getByText("$ 3.200.000")).toBeInTheDocument()
    expect(screen.getByText("64%")).toBeInTheDocument()
    expect(screen.getByText("$ 1.400.000")).toBeInTheDocument()
    expect(screen.getByText("$ 400.000")).toBeInTheDocument()
    expect(SPLIT.consumo + SPLIT.ahorro + SPLIT.libre).toBe(SPLIT.income)
  })

  it("keeps what was set aside visible in a month a meta was also cancelled", async () => {
    const MIXED = {
      ...SPLIT,
      consumo: 0,
      ahorro: -220_000_000,
      libre: 720_000_000,
      ahorro_share: -44,
      set_aside: 100_000_000,
      set_aside_share: 20,
      released: 320_000_000,
      gave_back: [CELULAR],
    }
    monthSplit.mockResolvedValue(MIXED)
    renderPage()

    expect(await screen.findByText("$ 1.000.000")).toBeInTheDocument()
    expect(screen.getByText("20%")).toBeInTheDocument()
    expect(screen.getByText("Devuelto por Celular (la cancelaste)")).toBeInTheDocument()
    expect(screen.getByText("$ -3.200.000")).toBeInTheDocument()
    expect(MIXED.set_aside - MIXED.released).toBe(MIXED.ahorro)
    expect(MIXED.consumo + MIXED.ahorro + MIXED.libre).toBe(MIXED.income)
  })

  it("names a meta that gave money back because its amount was lowered", async () => {
    monthSplit.mockResolvedValue({
      ...SPLIT,
      gave_back: [{ ...CELULAR, cancelled: false, released: 50_000_000 }],
    })
    renderPage()

    expect(
      await screen.findByText("Devuelto por Celular (le bajaste el monto)"),
    ).toBeInTheDocument()
  })

  it("names no give-back in an ordinary month", async () => {
    monthSplit.mockResolvedValue(SPLIT)
    renderPage()

    expect(await screen.findByText("Ahorro · fondos y metas")).toBeInTheDocument()
    expect(screen.queryByText(/Devuelto por/)).not.toBeInTheDocument()
  })
})

describe("AC-19 — the month arrives with nothing bought, and the app says so", () => {
  const IS_WAITING = { ...CELULAR, waiting: true, cancelled: false, released: 0, asks: 0 }

  it("The meta whose month passed unbought is named on the dashboard", async () => {
    showing({ ...AVAILABLE, metas: [IS_WAITING] })
    renderPage()

    expect(await screen.findByText(/Celular está esperando/)).toBeInTheDocument()
    expect(screen.getByText(/su mes ya pasó y no le has enlazado la compra/)).toBeInTheDocument()
  })

  it("A meta still running is not named", async () => {
    showing({ ...AVAILABLE, metas: [{ ...IS_WAITING, waiting: false }] })
    renderPage()

    await screen.findByText("Sin fondo que lo cubra")
    expect(screen.queryByText(/está esperando/)).not.toBeInTheDocument()
  })

  it("A month with no metas says nothing about waiting", async () => {
    renderPage()

    await screen.findByText("Sin fondo que lo cubra")
    expect(screen.queryByText(/esperando/)).not.toBeInTheDocument()
  })
})

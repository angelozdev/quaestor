import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { FundCreate, FundRule, FundStatus, MonthAvailable } from "@/lib/api/types"

const { createFund, previewFund, moneyAvailable, deleteFund, listFunds, listCategories, toast } =
  vi.hoisted(() => ({
    createFund: vi.fn(),
    previewFund: vi.fn(),
    moneyAvailable: vi.fn(),
    deleteFund: vi.fn(),
    listFunds: vi.fn(),
    listCategories: vi.fn(),
    toast: { success: vi.fn(), error: vi.fn() },
  }))

vi.mock("@/lib/api/funds", () => ({
  createFund,
  previewFund,
  moneyAvailable,
  deleteFund,
  listFunds,
}))
vi.mock("@/lib/api/categories", () => ({ listCategories }))
vi.mock("sonner", () => ({ toast }))

import FundsPage from "./page"

const RESTAURANTES = { id: 7, name: "Restaurantes", is_income: false }
const TECNOLOGIA = { id: 8, name: "Tecnologia", is_income: false }
const SERVICIOS = { id: 9, name: "Servicios", is_income: false }
const MERCADO = { id: 10, name: "Mercado", is_income: false }
const CATEGORIES = [RESTAURANTES, TECNOLOGIA, SERVICIOS, MERCADO]

const THIS_MONTH = "2026-08"
const ALWAYS_ACCUMULATES: FundRule[] = ["from-recurring", "target-by-date"]

function fund(over: Partial<FundStatus> = {}): FundStatus {
  return {
    fund_id: 1,
    category_id: RESTAURANTES.id,
    name: RESTAURANTES.name,
    year_month: THIS_MONTH,
    rule: "fixed",
    asks: 10_000_000,
    holds: 0,
    spent: 0,
    carries: 10_000_000,
    next_month_has: 20_000_000,
    accumulates: true,
    accumulation_is_implied: false,
    on_track: true,
    averaged_over: null,
    spreads_over: null,
    whole_by: null,
    ...over,
  }
}

const presupuesto = (over: Partial<FundStatus> = {}) =>
  fund({ accumulates: false, carries: 0, next_month_has: 10_000_000, ...over })

const tecnologia = (over: Partial<FundStatus> = {}) =>
  fund({ fund_id: 2, category_id: TECNOLOGIA.id, name: TECNOLOGIA.name, ...over })

let month: MonthAvailable
let startMonths: Record<number, string>
let wouldAsk: Partial<Record<FundRule, number>>

function showing(funds: FundStatus[]) {
  month = { year_month: THIS_MONTH, income: 0, funds, uncovered: 0, free: 0 }
}

function fundLinesOf(funds: FundStatus[]) {
  return funds.map((f) => ({
    fund_id: f.fund_id,
    category_id: f.category_id,
    name: f.name,
    rule: f.rule,
    start_month: startMonths[f.fund_id] ?? "2026-01",
    accumulates: f.accumulates,
  }))
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <FundsPage />
    </QueryClientProvider>,
  )
}

const setup = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

async function startCreating(user: ReturnType<typeof setup>, shape: "fondo" | "presupuesto") {
  await user.click(screen.getByRole("button", { name: `+ Nuevo ${shape}` }))
}

async function chooseCategory(user: ReturnType<typeof setup>, name: string | RegExp) {
  await user.click(screen.getByRole("combobox", { name: "Categoría *" }))
  await user.click(await screen.findByRole("option", { name }))
}

async function chooseRule(user: ReturnType<typeof setup>, label: string) {
  await user.click(screen.getByRole("radio", { name: label }))
}

const under = async (heading: RegExp) => within(await screen.findByRole("table", { name: heading }))

const entriesUnder = (table: ReturnType<typeof within>) => table.getAllByRole("row").length - 1

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ["Date"] })
  vi.setSystemTime(new Date("2026-08-15T12:00:00"))
  startMonths = {}
  wouldAsk = {}
  showing([])
  moneyAvailable.mockImplementation(async () => month)
  listFunds.mockImplementation(async () => fundLinesOf(month.funds))
  listCategories.mockResolvedValue(CATEGORIES)
  previewFund.mockImplementation(async (body: FundCreate) => ({
    category_id: body.category_id,
    would_ask: wouldAsk[body.rule] ?? 0,
    warning: null,
  }))
  deleteFund.mockResolvedValue(undefined)
  createFund.mockImplementation(async (body: FundCreate) => {
    const category = CATEGORIES.find((c) => c.id === body.category_id)
    showing([
      ...month.funds,
      fund({
        fund_id: 50 + month.funds.length,
        category_id: body.category_id,
        name: category?.name ?? "",
        rule: body.rule,
        accumulates: ALWAYS_ACCUMULATES.includes(body.rule) ? true : Boolean(body.accumulates),
      }),
    ])
    return { id: 50 }
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe("AC-1 — the two shapes have two names", () => {
  it("The two shapes are told apart on one screen", async () => {
    showing([presupuesto(), tecnologia()])
    renderPage()

    expect((await under(/PRESUPUESTOS/)).getByText("Restaurantes")).toBeInTheDocument()
    expect((await under(/FONDOS/)).getByText("Tecnologia")).toBeInTheDocument()
  })
})

describe("AC-2 — each list says what its shape does", () => {
  it("The presupuestos heading states that leftover money is not kept", async () => {
    showing([presupuesto()])
    renderPage()

    expect(await screen.findByText("Lo que no gastes no se guarda.")).toBeInTheDocument()
  })

  it("The fondos heading states that leftover money is carried forward", async () => {
    showing([tecnologia()])
    renderPage()

    expect(await screen.findByText("Lo que sobre pasa al mes siguiente.")).toBeInTheDocument()
  })

  it("Both headings are shown with one shape under each", async () => {
    showing([presupuesto(), tecnologia()])
    renderPage()

    expect(entriesUnder(await under(/PRESUPUESTOS/))).toBe(1)
    expect(entriesUnder(await under(/FONDOS/))).toBe(1)
  })
})

describe("AC-3 — every row says what happens to leftover money next month", () => {
  it("A fondo's row states what is kept, with its figure", async () => {
    showing([tecnologia({ spent: 6_000_000, carries: 4_000_000, next_month_has: 14_000_000 })])
    renderPage()

    expect(await screen.findByText("Gastaste $ 60.000 · se guardan $ 40.000")).toBeInTheDocument()
  })

  it("A fondo's row states what next month will have to spend", async () => {
    showing([tecnologia({ spent: 6_000_000, carries: 4_000_000, next_month_has: 14_000_000 })])
    renderPage()

    expect(await screen.findByText("Septiembre tendrá $ 140.000 para gastar.")).toBeInTheDocument()
  })

  it("A presupuesto's row states that the leftover money is lost, with its figure", async () => {
    showing([presupuesto({ spent: 6_000_000, carries: 0, next_month_has: 10_000_000 })])
    renderPage()

    expect(
      await screen.findByText("Gastaste $ 60.000 · los $ 40.000 que sobran no se guardan"),
    ).toBeInTheDocument()
    expect(screen.getByText("Septiembre vuelve a $ 100.000.")).toBeInTheDocument()
  })

  it("A fondo in its first month says why it is holding nothing yet", async () => {
    showing([tecnologia({ spent: 6_000_000, holds: 0, carries: 4_000_000 })])
    startMonths = { 2: THIS_MONTH }
    renderPage()

    const row = (await screen.findByText("Tecnologia")).closest("tr") as HTMLElement
    expect(within(row).getByText("$ 0")).toBeInTheDocument()
    expect(await screen.findByText("Tiene $0 porque empezó este mes.")).toBeInTheDocument()
  })
})

describe("AC-4 — creating starts from the job", () => {
  it("The screen offers one way in for each shape", async () => {
    showing([tecnologia()])
    renderPage()

    expect(screen.getByRole("button", { name: "+ Nuevo presupuesto" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "+ Nuevo fondo" })).toBeInTheDocument()
  })

  it("The single old way in is gone", async () => {
    showing([tecnologia()])
    renderPage()
    await screen.findByText("Tecnologia")

    expect(screen.queryByRole("button", { name: "Nuevo fondo" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^(Nuev[oa]|Crear)/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: /^\+ Nuevo/ })).toHaveLength(2)
  })

  it("No rule is asked for until a shape has been chosen", async () => {
    showing([tecnologia()])
    renderPage()
    await screen.findByText("Tecnologia")

    expect(screen.getAllByRole("button", { name: /^\+ Nuevo (presupuesto|fondo)$/ })).toHaveLength(
      2,
    )
    expect(screen.queryAllByRole("radio")).toHaveLength(0)
    expect(screen.queryByLabelText("Monto mensual * (COP)")).not.toBeInTheDocument()
  })

  it("The form that opens already knows which shape it is making", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")

    expect(screen.getByText("Estás creando un presupuesto.")).toBeInTheDocument()
  })
})

describe("AC-5 — the rule picker names the job and carries a worked number", () => {
  it("Four rules are offered for a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    expect(screen.getAllByRole("radio")).toHaveLength(4)
  })

  it("Every rule offered says what it is for", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    for (const radio of screen.getAllByRole("radio")) {
      const described = radio.getAttribute("aria-describedby") as string
      expect(document.getElementById(described)?.textContent ?? "").not.toBe("")
    }
  })

  it("No rule is named after the arithmetic it runs", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    for (const name of [
      "Monto fijo",
      "Promedio de los últimos meses",
      "Lo que piden sus obligaciones",
      "Meta con fecha",
    ]) {
      expect(screen.queryByRole("radio", { name })).not.toBeInTheDocument()
    }
  })

  it("The subscription rule says what it does with a real charge", async () => {
    wouldAsk = { "from-recurring": 10_000_000 }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Servicios")

    expect(
      await screen.findByText(/Aparto \$ 100\.000 al mes, y cuando se paga empieza sola/),
    ).toBeInTheDocument()
  })

  it("The subscription rule says that it starts again on its own", async () => {
    wouldAsk = { "from-recurring": 10_000_000 }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Servicios")

    expect(
      await screen.findByText(/cuando se paga empieza sola para el año siguiente/),
    ).toBeInTheDocument()
  })

  it("The averaging rule works its figure from what the category cost", async () => {
    wouldAsk = { average: 8_900_000 }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Restaurantes")

    expect(
      await screen.findByText(
        "Los últimos 3 meses gastaste $ 89.000 al mes en Restaurantes. Aparto eso, y lo que sobre se queda.",
      ),
    ).toBeInTheDocument()
  })

  it("The rule that saves toward a date works its figure from the date", async () => {
    wouldAsk = { "target-by-date": 10_000_000 }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Mercado")
    await chooseRule(user, "Junto una cantidad para una fecha")
    await user.type(screen.getByLabelText("Objetivo * (COP)"), "600000")
    await user.type(screen.getByLabelText("Mes objetivo *"), "2027-02")

    expect(
      await screen.findByText(
        "Aparto $ 100.000 al mes. Reparto lo que falta entre los meses que quedan.",
      ),
    ).toBeInTheDocument()
  })

  it("The subscription rule says so when the category has none", async () => {
    wouldAsk = { "from-recurring": 0 }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Servicios")

    expect(
      await screen.findByText("Servicios no tiene cobros registrados: pediría $ 0 al mes."),
    ).toBeInTheDocument()
  })

  it("A category with no recurring charges is offered the way to register one", async () => {
    wouldAsk = { "from-recurring": 0 }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Servicios")

    expect(
      await screen.findByRole("link", { name: "Registrar un cobro recurrente" }),
    ).toHaveAttribute("href", "/recurring")
  })
})

describe("AC-6 — the accumulate checkbox disappears", () => {
  it("Making a presupuesto never asks whether money accumulates", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/[Aa]cumula/)
  })

  it("Making a fondo never asks whether money accumulates", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/[Aa]cumula/)
  })

  it("A presupuesto with a fixed amount is filed as a presupuesto", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await chooseCategory(user, "Restaurantes")
    await user.type(screen.getByLabelText("Monto mensual * (COP)"), "100000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({ rule: "fixed", accumulates: false, amount: 10_000_000 }),
      ),
    )
    expect((await under(/PRESUPUESTOS/)).getByText("Restaurantes")).toBeInTheDocument()
  })

  it("A fondo with a fixed amount is filed as a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Tecnologia")
    await user.type(screen.getByLabelText("Monto mensual * (COP)"), "100000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({ rule: "fixed", accumulates: true }),
      ),
    )
    expect((await under(/FONDOS/)).getByText("Tecnologia")).toBeInTheDocument()
  })

  it("A presupuesto from the category average is filed as a presupuesto", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await chooseCategory(user, "Restaurantes")
    await chooseRule(user, "El tope sale de lo que ya gastabas")
    await user.clear(screen.getByLabelText("Meses a promediar *"))
    await user.type(screen.getByLabelText("Meses a promediar *"), "1")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({ rule: "average", window_months: 1, accumulates: false }),
      ),
    )
    expect((await under(/PRESUPUESTOS/)).getByText("Restaurantes")).toBeInTheDocument()
  })

  it("A fondo from the category average is filed as a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Mercado")
    await chooseRule(user, "Aparto lo que suelo gastar")
    await user.clear(screen.getByLabelText("Meses a promediar *"))
    await user.type(screen.getByLabelText("Meses a promediar *"), "1")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({ rule: "average", window_months: 1, accumulates: true }),
      ),
    )
    expect((await under(/FONDOS/)).getByText("Mercado")).toBeInTheDocument()
  })

  it("A fondo that reads recurring charges is filed as a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Servicios")
    await chooseRule(user, "Pago mis suscripciones mes a mes")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({ rule: "from-recurring", accumulates: true }),
      ),
    )
    expect((await under(/FONDOS/)).getByText("Servicios")).toBeInTheDocument()
  })

  it("A fondo saving toward a date is filed as a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Mercado")
    await chooseRule(user, "Junto una cantidad para una fecha")
    await user.type(screen.getByLabelText("Objetivo * (COP)"), "600000")
    await user.type(screen.getByLabelText("Mes objetivo *"), "2027-02")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() =>
      expect(createFund).toHaveBeenCalledWith(
        expect.objectContaining({
          rule: "target-by-date",
          target_amount: 60_000_000,
          target_month: "2027-02",
        }),
      ),
    )
    expect((await under(/FONDOS/)).getByText("Mercado")).toBeInTheDocument()
  })
})

describe("AC-10 — an empty screen teaches and offers the way in", () => {
  it("An empty Fondos screen says what a fondo is for", async () => {
    renderPage()

    await screen.findByText("Todavía no tienes fondos ni presupuestos.")
    expect(document.body.textContent).toContain("aparta plata cada mes y guarda lo que sobra")
  })

  it("An empty Fondos screen says what a presupuesto is for", async () => {
    renderPage()

    await screen.findByText("Todavía no tienes fondos ni presupuestos.")
    expect(document.body.textContent).toContain("es un tope: lo que no gastes no se guarda")
  })

  it("An empty Fondos screen offers to create the first one", async () => {
    const user = setup()
    renderPage()

    const start = await screen.findByRole("button", { name: "Crear el primero" })
    await user.click(start)
    expect(screen.getByText("Estás creando un fondo.")).toBeInTheDocument()
  })
})

describe("AC-12 — a shape that must carry money forward is never a presupuesto", () => {
  it("Exactly two rules are offered for a presupuesto", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")

    expect(screen.getAllByRole("radio")).toHaveLength(2)
  })

  it("The rule that reads recurring charges is not offered for a presupuesto", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")

    expect(
      screen.queryByRole("radio", { name: "Pago mis suscripciones mes a mes" }),
    ).not.toBeInTheDocument()
  })

  it("The rule that saves toward a date is not offered for a presupuesto", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")

    expect(
      screen.queryByRole("radio", { name: "Junto una cantidad para una fecha" }),
    ).not.toBeInTheDocument()
  })

  it("Both rules are offered for a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    expect(
      screen.getByRole("radio", { name: "Pago mis suscripciones mes a mes" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("radio", { name: "Junto una cantidad para una fecha" }),
    ).toBeInTheDocument()
  })

  it("Switching to a presupuesto leaves a rule a presupuesto can use", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseRule(user, "Junto una cantidad para una fecha")
    await startCreating(user, "presupuesto")

    expect(
      screen.queryByRole("radio", { name: "Junto una cantidad para una fecha" }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "Yo pongo el tope" })).toBeChecked()
  })
})

describe("AC-13 — everything created before the split keeps working", () => {
  it("A pre-split fund that does not carry money forward reads as a presupuesto", async () => {
    showing([presupuesto()])
    renderPage()

    expect((await under(/PRESUPUESTOS/)).getByText("Restaurantes")).toBeInTheDocument()
  })

  it("A pre-split fund that carries money forward reads as a fondo", async () => {
    showing([tecnologia()])
    renderPage()

    expect((await under(/FONDOS/)).getByText("Tecnologia")).toBeInTheDocument()
  })

  it("Nothing created before the split is asked about, and it still shows", async () => {
    showing([presupuesto({ asks: 10_000_000 })])
    renderPage()

    const row = (await screen.findByText("Restaurantes")).closest("tr") as HTMLElement
    expect(within(row).getByText("$ 100.000")).toBeInTheDocument()
    expect(within(row).queryAllByRole("radio")).toHaveLength(0)
    expect(within(row).queryAllByRole("combobox")).toHaveLength(0)
    expect(within(row).queryAllByRole("checkbox")).toHaveLength(0)
  })
})

describe("AC-15 — a category still holds exactly one of these", () => {
  it("A category that already holds one says so in the list, before it is chosen", async () => {
    showing([tecnologia()])
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await user.click(screen.getByRole("combobox", { name: "Categoría *" }))

    expect(
      await screen.findByRole("option", { name: "Tecnologia — ya tiene un fondo" }),
    ).toBeInTheDocument()
  })

  it("A category holding nothing can be chosen and used", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await chooseCategory(user, "Restaurantes")
    await user.type(screen.getByLabelText("Monto mensual * (COP)"), "100000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(createFund).toHaveBeenCalledTimes(1))
    expect((await under(/PRESUPUESTOS/)).getByText("Restaurantes")).toBeInTheDocument()
  })
})

describe("AC-17 — a refusal is stated in the new vocabulary", () => {
  it("Refusing a second one on the same category uses the noun of the one already there", async () => {
    showing([tecnologia()])
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await chooseCategory(user, "Tecnologia — ya tiene un fondo")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Tecnologia ya tiene un fondo. Cámbialo en vez de crear otro.",
    )
    expect(createFund).not.toHaveBeenCalled()
  })

  it("A presupuesto with no amount is refused in the words the screen uses", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await chooseCategory(user, "Restaurantes")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El presupuesto necesita su monto mensual.",
    )
    expect(createFund).not.toHaveBeenCalled()
  })

  it("The refusal that the vanished checkbox existed for is gone", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, "Mercado")
    await chooseRule(user, "Junto una cantidad para una fecha")

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/acumul/i)
  })
})

describe("AC-20 — every control that decides the shape is named out loud", () => {
  it("A screen reader hears which shape each way in makes", async () => {
    showing([tecnologia()])
    renderPage()

    expect(screen.getByRole("button", { name: "+ Nuevo presupuesto" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "+ Nuevo fondo" })).toBeInTheDocument()
  })

  it("A screen reader hears every rule by the job it does", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    const heard = screen.getAllByRole("radio").map((r) => r.getAttribute("id"))
    expect(heard).toHaveLength(4)
    for (const label of [
      "Aparto un monto fijo cada mes",
      "Aparto lo que suelo gastar",
      "Pago mis suscripciones mes a mes",
      "Junto una cantidad para una fecha",
    ]) {
      expect(screen.getByRole("radio", { name: label })).toBeInTheDocument()
    }
  })

  it("A screen reader hears the two ways in and nothing unnamed beside them", async () => {
    showing([tecnologia()])
    renderPage()
    await screen.findByText("Tecnologia")

    const ways = screen.getAllByRole("button", { name: /^\+ Nuevo (presupuesto|fondo)$/ })
    expect(ways).toHaveLength(2)
    expect(ways.map((w) => w.textContent)).toEqual(["+ Nuevo presupuesto", "+ Nuevo fondo"])
  })
})

describe("AC-21 — one vocabulary, everywhere", () => {
  it("A presupuesto's own row never calls it a fondo", async () => {
    showing([presupuesto()])
    renderPage()

    const row = (await screen.findByText("Restaurantes")).closest("tr") as HTMLElement
    expect(row.textContent).not.toMatch(/fondo/i)
    expect(
      within(row).getByLabelText("Eliminar el presupuesto de Restaurantes"),
    ).toBeInTheDocument()
  })

  it("The empty screen uses the same two words", async () => {
    renderPage()

    await screen.findByText("Todavía no tienes fondos ni presupuestos.")
    expect(document.body.textContent).toMatch(/\bfondo\b/)
    expect(document.body.textContent).toMatch(/\bpresupuesto\b/)
  })

  it("The two ways in use the same two words", async () => {
    showing([tecnologia()])
    renderPage()

    expect(screen.getByRole("button", { name: "+ Nuevo presupuesto" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "+ Nuevo fondo" })).toBeInTheDocument()
  })

  it("Creating a presupuesto is confirmed as a presupuesto", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")
    await chooseCategory(user, "Restaurantes")
    await user.type(screen.getByLabelText("Monto mensual * (COP)"), "100000")
    await user.click(screen.getByRole("button", { name: "Crear" }))

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Presupuesto creado"))
  })

  it("Deleting a presupuesto is asked about and confirmed as a presupuesto", async () => {
    showing([presupuesto()])
    const user = setup()
    renderPage()

    await user.click(
      await screen.findByRole("button", { name: "Eliminar el presupuesto de Restaurantes" }),
    )
    expect(await screen.findByText("Eliminar presupuesto")).toBeInTheDocument()
    expect(screen.getByText(/Se elimina el presupuesto de "Restaurantes"/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Eliminar" }))
    await waitFor(() => expect(deleteFund).toHaveBeenCalledWith(1))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Presupuesto eliminado"))
  })
})

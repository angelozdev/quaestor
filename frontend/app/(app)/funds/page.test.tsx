import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { HELP_LABEL } from "@/components/screen-help"
import type { FundCharge, FundCreate, FundRule, FundStatus, MonthAvailable } from "@/lib/api/types"
import { openHelpPanel } from "@/tests/factories"

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
const ALWAYS_ACCUMULATES: FundRule[] = ["from-recurring"]

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
    charges: [],
    has_repeating_charges: false,
    averaged_over: null,
    spreads_over: null,
    whole_by: null,
    recurring_id: null,
    currency: "COP",
    asks_cop: over.asks ?? 10_000_000,
    holds_cop: over.holds ?? 0,
    ...over,
  }
}

function charge(over: Partial<FundCharge> = {}): FundCharge {
  return {
    name: "Internet",
    costs: 8_000_000,
    charge_month: THIS_MONTH,
    asks: 8_000_000,
    can_be_spread: false,
    ...over,
  }
}

const INTERNET = charge()

const DOMINIO = charge({
  name: "Dominio",
  costs: 120_000_000,
  charge_month: "2027-08",
  asks: 10_000_000,
  can_be_spread: true,
})

const fillingFor = (charges: FundCharge[]) =>
  fund({
    fund_id: 3,
    category_id: SERVICIOS.id,
    name: SERVICIOS.name,
    rule: "from-recurring",
    asks: charges.reduce((total, line) => total + line.asks, 0),
    charges,
    has_repeating_charges: true,
  })

const presupuesto = (over: Partial<FundStatus> = {}) =>
  fund({ accumulates: false, carries: 0, next_month_has: 10_000_000, ...over })

const tecnologia = (over: Partial<FundStatus> = {}) =>
  fund({ fund_id: 2, category_id: TECNOLOGIA.id, name: TECNOLOGIA.name, ...over })

let month: MonthAvailable
let startMonths: Record<number, string>
let wouldAsk: Partial<Record<FundRule, number>>
let spreadable: Record<number, boolean>
let crowded: FundCharge[]

function showing(funds: FundStatus[]) {
  month = {
    year_month: THIS_MONTH,
    income: 0,
    funds,
    metas: [],
    contributed: 0,
    released: 0,
    uncovered: 0,
    free: 0,
  }
}

function fundLinesOf(funds: FundStatus[]) {
  return funds.map((f) => ({
    fund_id: f.fund_id,
    category_id: f.category_id,
    name: f.name,
    rule: f.rule,
    start_month: startMonths[f.fund_id] ?? "2026-01",
    accumulates: f.accumulates,
    recurring_id: f.recurring_id,
    currency: f.currency,
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

/** The pesos in a rendered figure: "$ 180.000" → 180000. */
function pesosIn(text: string): number {
  return Number((text.match(/[\d.]+/)?.[0] ?? "").replace(/\./g, ""))
}

/** What one breakdown line contributes, which is the first figure after its dash. */
function shareIn(line: string): number {
  return pesosIn(line.split("\u00b7")[1] ?? "")
}

const rowFor = (table: ReturnType<typeof within>, name: string) =>
  table
    .getAllByRole("row")
    .find((row: HTMLElement) => within(row).queryByText(name) !== null) as HTMLElement

/** What the row says the entry asks, which is its third cell. */
const asked = (row: HTMLElement) => within(row).getAllByRole("cell")[2].textContent ?? ""

const entriesUnder = (table: ReturnType<typeof within>) => table.getAllByRole("row").length - 1

const THIS_SCREEN = "Fondos y presupuestos"

const panel = () => screen.getByRole("dialog", { name: `¿Cómo funciona ${THIS_SCREEN}?` })

const openHelp = (user: ReturnType<typeof setup>) => openHelpPanel(THIS_SCREEN, user)

const overlay = () => document.querySelector('[data-slot="screen-help-backdrop"]') as HTMLElement

/** Whatever follows a "$" in the panel, so a blank one can be told from a figure. */
function figuresIn(open: HTMLElement): string[] {
  return [...(open.textContent ?? "").matchAll(/\$\s*(\S*)/g)].map((hit) => hit[1])
}

async function reachHelpWithKeyboard(user: ReturnType<typeof setup>) {
  const help = screen.getByRole("button", { name: HELP_LABEL })
  for (let step = 0; step < 20 && document.activeElement !== help; step += 1) {
    await user.tab()
  }
  expect(help).toHaveFocus()
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ["Date"] })
  vi.setSystemTime(new Date("2026-08-15T12:00:00"))
  startMonths = {}
  wouldAsk = {}
  spreadable = {}
  crowded = []
  showing([])
  moneyAvailable.mockImplementation(async () => month)
  listFunds.mockImplementation(async () => fundLinesOf(month.funds))
  listCategories.mockResolvedValue(CATEGORIES)
  previewFund.mockImplementation(async (body: FundCreate) => ({
    category_id: body.category_id,
    would_ask: wouldAsk[body.rule] ?? 0,
    warning: null,
    crowded,
    has_something_to_spread: spreadable[body.category_id] ?? false,
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

    expect((await under(/Presupuestos/)).getByText("Restaurantes")).toBeInTheDocument()
    expect((await under(/Fondos/)).getByText("Tecnologia")).toBeInTheDocument()
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

    expect(entriesUnder(await under(/Presupuestos/))).toBe(1)
    expect(entriesUnder(await under(/Fondos/))).toBe(1)
  })

  it("shows both headings even when one shape has nothing under it", async () => {
    showing([presupuesto()])
    renderPage()

    expect(entriesUnder(await under(/Presupuestos/))).toBe(1)
    expect(screen.getByRole("heading", { name: /Fondos —/ })).toBeInTheDocument()
    expect(
      screen.getByText(
        "Todavía no tienes fondos. Un fondo aparta plata cada mes y guarda lo que sobra.",
      ),
    ).toBeInTheDocument()
  })

  it("teaches what a presupuesto is when no presupuesto exists yet", async () => {
    showing([tecnologia()])
    renderPage()

    expect(entriesUnder(await under(/Fondos/))).toBe(1)
    expect(screen.getByRole("heading", { name: /Presupuestos —/ })).toBeInTheDocument()
    expect(
      screen.getByText(
        "Todavía no tienes presupuestos. Un presupuesto es un tope: lo que no gastes no se guarda.",
      ),
    ).toBeInTheDocument()
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
  it("Three rules are offered for a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    expect(screen.getAllByRole("radio")).toHaveLength(3)
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
    spreadable = { [SERVICIOS.id]: true }
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
    spreadable = { [SERVICIOS.id]: true }
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
    expect((await under(/Presupuestos/)).getByText("Restaurantes")).toBeInTheDocument()
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
    expect((await under(/Fondos/)).getByText("Tecnologia")).toBeInTheDocument()
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
    expect((await under(/Presupuestos/)).getByText("Restaurantes")).toBeInTheDocument()
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
    expect((await under(/Fondos/)).getByText("Mercado")).toBeInTheDocument()
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
    expect((await under(/Fondos/)).getByText("Servicios")).toBeInTheDocument()
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

    await user.click(await screen.findByRole("button", { name: "Crear mi primer presupuesto" }))
    expect(screen.getByText("Estás creando un presupuesto.")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "+ Nuevo fondo" }))
    expect(screen.getByText("Estás creando un fondo.")).toBeInTheDocument()
  })

  it("offers the first one of each shape, so the choice is made after reading what each is", async () => {
    const user = setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Crear mi primer fondo" }))
    expect(screen.getByText("Estás creando un fondo.")).toBeInTheDocument()
  })

  it("names a shape in every way in it offers, and adds no third word", async () => {
    renderPage()

    await screen.findByText("Todavía no tienes fondos ni presupuestos.")
    expect(screen.queryByRole("button", { name: "Crear el primero" })).not.toBeInTheDocument()
    const waysIn = screen.getAllByRole("button").filter((b) => b.textContent !== HELP_LABEL)
    expect(waysIn.length).toBeGreaterThan(0)
    for (const button of waysIn) {
      expect(button.textContent).toMatch(/presupuesto|fondo/i)
    }
  })
})

const AVERAGED = () => presupuesto({ rule: "average", asks: 8_900_000, averaged_over: 1, spent: 0 })

describe("AC-7 — every screen carries the same control", () => {
  it("Fondos y presupuestos offers to explain itself", async () => {
    showing([presupuesto()])
    const user = setup()
    renderPage()

    expect(screen.getByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
    expect(await openHelp(user)).toHaveTextContent(
      "Un fondo aparta plata cada mes y guarda lo que sobra.",
    )
  })
})

describe("AC-8 — the panel explains the screen using the owner's own figures", () => {
  it("The panel names what is on the screen", async () => {
    showing([AVERAGED()])
    const user = setup()
    renderPage()
    await screen.findByText("Restaurantes")
    const open = await openHelp(user)

    expect(open).toHaveTextContent("Lo que tienes en esta pantalla:")
    expect(within(open).getByRole("list")).toHaveTextContent("Restaurantes")
    expect(open).not.toHaveTextContent("son de un ejemplo")
  })

  it("The panel states the figure the screen is showing", async () => {
    showing([AVERAGED()])
    const user = setup()
    renderPage()
    await screen.findByText("Restaurantes")

    expect(await openHelp(user)).toHaveTextContent("pide $ 89.000 este mes")
  })

  it("The panel states why the figure is that figure", async () => {
    showing([AVERAGED()])
    const user = setup()
    renderPage()
    await screen.findByText("Restaurantes")

    expect(await openHelp(user)).toHaveTextContent("porque es el promedio de lo que gastaste antes")
  })
})

describe("AC-9 — the panel never opens by itself", () => {
  it("The control is offered and nothing is open until it is used", async () => {
    showing([presupuesto()])
    renderPage()
    await screen.findByText("Restaurantes")

    expect(screen.getByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("Clicking outside the panel closes it", async () => {
    const user = setup()
    renderPage()
    await openHelp(user)

    await user.click(overlay())

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: HELP_LABEL })).toHaveFocus()
  })

  it("Selecting text in the panel and releasing outside does not close it", async () => {
    showing([presupuesto()])
    const user = setup()
    renderPage()
    await screen.findByText("Restaurantes")
    const open = await openHelp(user)

    fireEvent.mouseDown(within(open).getByText("Lo que tienes en esta pantalla:"))
    fireEvent.mouseUp(overlay())

    expect(panel()).toHaveTextContent("Un fondo aparta plata cada mes y guarda lo que sobra.")
  })

  it("Closing the panel closes it and leaves the way back", async () => {
    const user = setup()
    renderPage()
    const open = await openHelp(user)

    await user.click(within(open).getByRole("button", { name: "Cerrar" }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
  })
})

describe("AC-11 — with nothing of his own to quote, the panel works an example", () => {
  it("The panel still says what a fondo is when the screen holds nothing", async () => {
    const user = setup()
    renderPage()

    expect(await openHelp(user)).toHaveTextContent(
      "Un fondo aparta plata cada mes y guarda lo que sobra.",
    )
  })

  it("The panel still says what a presupuesto is when the screen holds nothing", async () => {
    const user = setup()
    renderPage()

    expect(await openHelp(user)).toHaveTextContent(
      "Un presupuesto es un tope: lo que no gastes no se guarda.",
    )
  })

  it("The panel works an example with figures and says they are an example", async () => {
    const user = setup()
    renderPage()
    const open = await openHelp(user)

    expect(figuresIn(open).length).toBeGreaterThanOrEqual(1)
    expect(open).toHaveTextContent("Las cifras de abajo son de un ejemplo, no tuyas.")
  })
})

describe("AC-16 — the panel opens even when the screen's figures never arrive", () => {
  it("The panel opens when the month's figures never arrive", async () => {
    moneyAvailable.mockRejectedValue(new Error("boom"))
    const user = setup()
    renderPage()
    await screen.findByText("No se pudieron cargar los fondos y presupuestos")

    expect(await openHelp(user)).toHaveTextContent("Un fondo aparta plata cada mes")
  })

  it("The panel still says what both shapes are when the figures never arrive", async () => {
    moneyAvailable.mockRejectedValue(new Error("boom"))
    const user = setup()
    renderPage()
    await screen.findByText("No se pudieron cargar los fondos y presupuestos")
    const open = await openHelp(user)

    expect(open).toHaveTextContent("Un fondo aparta plata cada mes y guarda lo que sobra.")
    expect(open).toHaveTextContent("Un presupuesto es un tope: lo que no gastes no se guarda.")
  })

  it("A panel with no figures to quote shows worked examples, not blanks", async () => {
    moneyAvailable.mockRejectedValue(new Error("boom"))
    const user = setup()
    renderPage()
    await screen.findByText("No se pudieron cargar los fondos y presupuestos")
    const open = await openHelp(user)

    const figures = figuresIn(open)
    expect(figures.length).toBeGreaterThanOrEqual(1)
    for (const figure of figures) expect(figure).toMatch(/^\d/)
    expect(open).toHaveTextContent("Las cifras de abajo son de un ejemplo, no tuyas.")
  })
})

describe("AC-19 — the panel can be opened, read and closed with the keyboard alone", () => {
  it("The panel opens without a mouse", async () => {
    const user = setup()
    renderPage()

    await reachHelpWithKeyboard(user)
    await user.keyboard("{Enter}")

    expect(panel()).toHaveTextContent("Un fondo aparta plata cada mes")
  })

  it("The keyboard stays inside the panel while it is open", async () => {
    showing([presupuesto()])
    const user = setup()
    renderPage()
    await screen.findByText("Restaurantes")
    await reachHelpWithKeyboard(user)
    await user.keyboard("{Enter}")

    const open = panel()
    const visited: Element[] = []
    for (let step = 0; step < 6; step += 1) {
      await user.tab()
      expect(open).toContainElement(document.activeElement as HTMLElement)
      visited.push(document.activeElement as Element)
    }

    expect(visited).toContain(within(open).getByRole("button", { name: "Cerrar" }))
  })

  it("Escape closes the panel and gives the reader back their place", async () => {
    const user = setup()
    renderPage()
    await reachHelpWithKeyboard(user)
    await user.keyboard("{Enter}")
    expect(panel()).toBeInTheDocument()

    await user.keyboard("{Escape}")

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: HELP_LABEL })).toHaveFocus()
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

  it("Every rule offered to a presupuesto is one it can use", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "presupuesto")

    expect(
      screen.queryByRole("radio", { name: "Pago mis suscripciones mes a mes" }),
    ).not.toBeInTheDocument()
  })

  it("The rule that must carry money forward is offered for a fondo", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    expect(
      screen.getByRole("radio", { name: "Pago mis suscripciones mes a mes" }),
    ).toBeInTheDocument()
  })

  it("Switching to a presupuesto leaves a rule a presupuesto can use", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseRule(user, "Pago mis suscripciones mes a mes")
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

    expect((await under(/Presupuestos/)).getByText("Restaurantes")).toBeInTheDocument()
  })

  it("A pre-split fund that carries money forward reads as a fondo", async () => {
    showing([tecnologia()])
    renderPage()

    expect((await under(/Fondos/)).getByText("Tecnologia")).toBeInTheDocument()
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
    expect((await under(/Presupuestos/)).getByText("Restaurantes")).toBeInTheDocument()
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
    await chooseRule(user, "Pago mis suscripciones mes a mes")

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
    expect(heard).toHaveLength(3)
    for (const label of [
      "Aparto un monto fijo cada mes",
      "Aparto lo que suelo gastar",
      "Pago mis suscripciones mes a mes",
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

  it("The panel uses the same two words the rows use", async () => {
    showing([presupuesto(), tecnologia()])
    const user = setup()
    renderPage()
    await screen.findByText("Restaurantes")
    const open = await openHelp(user)

    expect(open).toHaveTextContent("Restaurantes es un presupuesto")
    expect(open).toHaveTextContent("Tecnologia es un fondo")
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

describe("AC-40 — the fund no longer saves toward a date", () => {
  it("The create form offers three ways, not four", async () => {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")

    const offered = screen.getAllByRole("radio").map((radio) => radio.getAttribute("aria-label"))
    expect(offered).toHaveLength(3)
    expect(offered).not.toContain("Junto una cantidad para una fecha")
    expect(screen.queryByLabelText("Objetivo * (COP)")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Mes objetivo *")).not.toBeInTheDocument()
  })
})

describe("014 AC-1, AC-2, AC-4 — the figure opens into the charges that produced it", () => {
  it("The row carries a line for every charge behind its figure", async () => {
    showing([fillingFor([INTERNET, DOMINIO])])
    renderPage()

    const table = await under(/Fondos/)
    expect(table.getByText("$ 180.000")).toBeInTheDocument()
    expect(table.getByText(/Internet —.*\$ 80\.000/)).toBeInTheDocument()
    expect(table.getByText(/Dominio —.*\$ 100\.000/)).toBeInTheDocument()
  })

  it("A line says what the charge costs and when it lands", async () => {
    showing([fillingFor([DOMINIO])])
    renderPage()

    const line = (await under(/Fondos/)).getByText(/^Dominio —/)
    expect(line).toHaveTextContent("$ 1.200.000")
    expect(line).toHaveTextContent("agosto de 2027")
  })

  it("The lines add up to what the row reads", async () => {
    showing([fillingFor([INTERNET, DOMINIO])])
    renderPage()

    const table = await under(/Fondos/)
    const shares = table.getAllByRole("listitem").map((line) => shareIn(line.textContent ?? ""))
    expect(shares.reduce((total, share) => total + share, 0)).toBe(180_000)
    expect(pesosIn(asked(rowFor(table, SERVICIOS.name)))).toBe(180_000)
  })
})

describe("014 AC-3 — what is due now reads differently from what is being saved", () => {
  it("The row separates what leaves this month from what stays", async () => {
    showing([fillingFor([INTERNET, DOMINIO])])
    renderPage()

    const table = await under(/Fondos/)
    expect(table.getByText(/^Internet —/)).toHaveTextContent("vence este mes")
    expect(table.getByText(/^Dominio —/)).toHaveTextContent("se guarda para agosto de 2027")
  })
})

describe("014 AC-8, AC-9 — a fund asking nothing says why", () => {
  it("A fund with every charge skipped explains the empty month", async () => {
    showing([fillingFor([])])
    renderPage()

    const table = await under(/Fondos/)
    expect(pesosIn(asked(rowFor(table, SERVICIOS.name)))).toBe(0)
    expect(table.getByText(/no hay nada que apartar/)).toBeInTheDocument()
  })

  it("A fund left with no obligations at all says the category has none", async () => {
    showing([fund({ ...fillingFor([]), has_repeating_charges: false })])
    renderPage()

    expect((await under(/Fondos/)).getByText(/ya no tiene cobros recurrentes/)).toBeInTheDocument()
  })
})

describe("014 AC-14 — the rule is not offered where nothing can be spread", () => {
  const THE_RULE = "Pago mis suscripciones mes a mes"

  it("A category holding only monthly charges is not offered the rule", async () => {
    wouldAsk = { "from-recurring": 25_000_000 }
    spreadable = { [SERVICIOS.id]: false }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, SERVICIOS.name)

    await waitFor(() =>
      expect(screen.queryByRole("radio", { name: THE_RULE })).not.toBeInTheDocument(),
    )
  })

  it("A category holding a charge that can be spread is offered the rule", async () => {
    wouldAsk = { "from-recurring": 10_000_000 }
    spreadable = { [SERVICIOS.id]: true }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, SERVICIOS.name)

    expect(await screen.findByRole("radio", { name: THE_RULE })).toBeInTheDocument()
  })
})

describe("014 AC-11, AC-12 — the announcement is about the charge that cannot be spread", () => {
  const SEGURO = charge({
    name: "Seguro",
    costs: 600_000_000,
    charge_month: "2026-09",
    asks: 600_000_000,
    can_be_spread: true,
  })

  async function startAFundOn(category: { id: number; name: string }) {
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, category.name)
    await chooseRule(user, "Pago mis suscripciones mes a mes")
    await user.click(screen.getByRole("button", { name: "Crear" }))
    return user
  }

  it("names the charge and quotes its own figure, not the fund's", async () => {
    wouldAsk = { "from-recurring": 605_000_000 }
    spreadable = { [SERVICIOS.id]: true }
    crowded = [SEGURO]
    await startAFundOn(SERVICIOS)

    const said = await screen.findByRole("alert")
    expect(said).toHaveTextContent("Seguro")
    expect(said).toHaveTextContent("$ 6.000.000")
    expect(said).not.toHaveTextContent("$ 6.050.000")
    expect(said).toHaveTextContent("septiembre de 2026")
  })

  it("lets the owner go ahead anyway", async () => {
    wouldAsk = { "from-recurring": 605_000_000 }
    spreadable = { [SERVICIOS.id]: true }
    crowded = [SEGURO]
    const user = await startAFundOn(SERVICIOS)

    await user.click(await screen.findByRole("button", { name: "Crear de todos modos" }))
    await waitFor(() => expect(createFund).toHaveBeenCalled())
  })

  it("says nothing when every charge has months to spread over", async () => {
    wouldAsk = { "from-recurring": 10_000_000 }
    spreadable = { [SERVICIOS.id]: true }
    await startAFundOn(SERVICIOS)

    await waitFor(() => expect(createFund).toHaveBeenCalled())
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})

describe("014 AC-14 — the rule withdrawn under the owner's feet", () => {
  const THE_RULE = "Pago mis suscripciones mes a mes"

  it("falls back to a rule that is still offered", async () => {
    wouldAsk = { "from-recurring": 10_000_000 }
    spreadable = { [SERVICIOS.id]: true, [MERCADO.id]: false }
    const user = setup()
    renderPage()
    await startCreating(user, "fondo")
    await chooseCategory(user, SERVICIOS.name)
    await chooseRule(user, THE_RULE)
    expect(screen.getByRole("radio", { name: THE_RULE })).toBeChecked()

    wouldAsk = { "from-recurring": 25_000_000 }
    await chooseCategory(user, MERCADO.name)

    await waitFor(() =>
      expect(screen.queryByRole("radio", { name: THE_RULE })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole("radio", { name: "Aparto un monto fijo cada mes" })).toBeChecked()
  })
})

describe("014 AC-4 — the lines add up to the figure above them", () => {
  it("The lines add up to the figure above them, in whole pesos", async () => {
    const third = charge({
      name: "Uno",
      costs: 100_000_000,
      charge_month: "2026-11",
      asks: 33_333_334,
    })
    showing([fillingFor([third, charge({ ...third, name: "Dos" })])])
    renderPage()

    const table = await under(/Fondos/)
    const row = pesosIn(asked(rowFor(table, SERVICIOS.name)))
    const lines = table.getAllByRole("listitem").map((line) => shareIn(line.textContent ?? ""))
    expect(row).toBe(666_667)
    expect(lines.reduce((total, share) => total + share, 0)).toBe(row)
  })
})

describe("015 — a fund may hang off the charge it fills", () => {
  const seguro = (over: Partial<FundStatus> = {}) =>
    fund({
      fund_id: 11,
      category_id: RESTAURANTES.id,
      recurring_id: 42,
      name: "Seguro",
      rule: "from-recurring",
      asks: 10_000_000,
      asks_cop: 10_000_000,
      holds: 0,
      holds_cop: 0,
      has_repeating_charges: true,
      charges: [
        charge({
          name: "Seguro",
          costs: 110_000_000,
          charge_month: "2027-07",
          asks: 10_000_000,
          can_be_spread: true,
        }),
      ],
      ...over,
    })

  const opal = () =>
    seguro({
      fund_id: 12,
      recurring_id: 43,
      name: "Opal",
      currency: "USD",
      asks: 5_000,
      asks_cop: 20_000_000,
      holds: 15_000,
      holds_cop: 60_000_000,
      charges: [
        charge({
          name: "Opal",
          costs: 60_000,
          charge_month: "2027-08",
          asks: 5_000,
          can_be_spread: true,
        }),
      ],
    })

  it("A marked charge is its own row among the funds, under its own name", async () => {
    showing([seguro()])
    renderPage()

    const table = await under(/Fondos/)
    const row = rowFor(table, "Seguro")

    expect(row).toBeInTheDocument()
    expect(asked(row)).toBe("$ 100.000")
    expect(table.queryByText(RESTAURANTES.name)).toBeNull()
  })

  it("The row carries all three terms, not just the figure", async () => {
    showing([seguro()])
    renderPage()

    const table = await under(/Fondos/)
    const said = `${rowFor(table, "Seguro").textContent} ${table.getByText(/Seguro —/).textContent}`

    expect(said).toContain("$ 100.000")
    expect(said).toContain("$ 1.100.000")
    expect(said).toContain("julio de 2027")
  })

  it("The unmarked charge leaves the funds", async () => {
    showing([seguro()])
    const user = setup()
    deleteFund.mockResolvedValue(undefined)
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Dejar de juntar para Seguro" }))
    await user.click(await screen.findByRole("button", { name: "Dejar de juntar" }))

    await waitFor(() => expect(deleteFund).toHaveBeenCalledWith(11))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Dejaste de juntar para Seguro"))
  })

  it("The row of a dollar charge reads entirely in dollars", async () => {
    showing([opal()])
    renderPage()

    const table = await under(/Fondos/)
    const row = rowFor(table, "Opal")
    const said = `${row.textContent} ${table.getByText(/Opal —/).textContent}`

    expect(asked(row)).toBe("US$ 50.00")
    expect(said).toContain("US$ 150.00")
    expect(said).toContain("US$ 600.00")
    expect(said).not.toMatch(/\$\s*20\.000\.000|\$\s*200\.000/)
  })
})

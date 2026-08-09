import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { HELP_LABEL } from "@/components/screen-help"
import type { MetaStatus } from "@/lib/api/types"
import { openHelpPanel } from "@/tests/factories"

const {
  listMetas,
  createMeta,
  previewMeta,
  listArchived,
  restoreMeta,
  closeMeta,
  setMeta,
  contribute,
  cancelMeta,
  toast,
} = vi.hoisted(() => ({
  listMetas: vi.fn(),
  createMeta: vi.fn(),
  previewMeta: vi.fn(),
  listArchived: vi.fn(),
  restoreMeta: vi.fn(),
  closeMeta: vi.fn(),
  setMeta: vi.fn(),
  contribute: vi.fn(),
  cancelMeta: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/api/metas", () => ({
  listMetas,
  createMeta,
  previewMeta,
  listArchived,
  restoreMeta,
  closeMeta,
  setMeta,
  contribute,
  cancelMeta,
}))
vi.mock("sonner", () => ({ toast }))

import { GROUPS } from "@/components/app-shell"

import MetasPage from "./page"

const THIS_MONTH = new Date().toISOString().slice(0, 7)

function meta(over: Partial<MetaStatus> = {}): MetaStatus {
  return {
    meta_id: 1,
    name: "Celular",
    year_month: "2026-08",
    amount: 800_000_000,
    currency: "COP",
    target_month: "2026-12",
    asks: 160_000_000,
    holds: 480_000_000,
    contributed: 0,
    progress: 60,
    complete: false,
    closed: false,
    waiting: false,
    cancelled: false,
    released: 0,
    ...over,
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MetasPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  listMetas.mockResolvedValue([meta()])
  previewMeta.mockResolvedValue({ asks: 160_000_000, months_left: 5, over_the_month: false })
  createMeta.mockResolvedValue(meta())
  listArchived.mockResolvedValue([])
  restoreMeta.mockResolvedValue(undefined)
  closeMeta.mockResolvedValue(undefined)
  setMeta.mockResolvedValue(undefined)
  contribute.mockResolvedValue(undefined)
  cancelMeta.mockResolvedValue(undefined)
})

describe("AC-5 — the metas have their own screen", () => {
  it("The metas screen states each meta's amount, month, holdings, ask and progress", async () => {
    renderPage()
    expect(await screen.findByText("Celular")).toBeInTheDocument()
    expect(screen.getByText(/8\.000\.000/)).toBeInTheDocument()
    expect(screen.getByText(/diciembre/i)).toBeInTheDocument()
    expect(screen.getByText(/4\.800\.000/)).toBeInTheDocument()
    expect(screen.getByText(/1\.600\.000/)).toBeInTheDocument()
    expect(screen.getByText(/60%/)).toBeInTheDocument()
  })

  it("The funds screen never lists a meta", async () => {
    renderPage()
    await screen.findByText("Celular")
    expect(screen.queryByText(/Fondos y presupuestos/)).not.toBeInTheDocument()
  })
})

describe("AC-8 — completing offers three things to do next", () => {
  it("Completing offers three things to do next", async () => {
    listMetas.mockResolvedValue([meta({ complete: true, closed: false })])
    renderPage()
    expect(await screen.findByRole("button", { name: /Cerrar Celular/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /otro monto/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /otro mes/ })).toBeInTheDocument()
  })
})

describe("AC-30 — the metas screen says what a meta is", () => {
  it("The screen carries the same explaining panel every screen carries", async () => {
    renderPage()
    await screen.findByText("Celular")
    expect(screen.getByRole("button", { name: HELP_LABEL })).toBeInTheDocument()
  })

  it("The panel separates the three words", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Celular")
    const panel = await openHelpPanel("las metas", user)
    expect(within(panel).getByText(/no vive en ninguna categoría/)).toBeInTheDocument()
    expect(within(panel).getByText(/va juntando lo que le sobra/)).toBeInTheDocument()
    expect(within(panel).getByText(/lo que no gastes no se guarda/i)).toBeInTheDocument()
  })

  it("The empty screen says what a meta is and starts one", async () => {
    listMetas.mockResolvedValue([])
    renderPage()
    expect(await screen.findByText(/una cosa con nombre y con final/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Crear mi primera meta" })).toBeInTheDocument()
  })
})

describe("AC-44 — the metas list puts what needs an answer first", () => {
  it("The ones waiting on an answer come first", async () => {
    listMetas.mockResolvedValue([
      meta({ meta_id: 1, name: "Celular", complete: true }),
      meta({ meta_id: 2, name: "Viaje", waiting: true, target_month: "2026-11" }),
      meta({ meta_id: 3, name: "Televisor", target_month: "2027-12" }),
      meta({ meta_id: 4, name: "Camara", target_month: "2028-03" }),
    ])
    renderPage()
    await screen.findByText("Celular")
    const names = screen.getAllByRole("listitem").map((row) => row.textContent ?? "")
    expect(names[0]).toContain("Celular")
    expect(names[1]).toContain("Viaje")
    expect(names[2]).toContain("Televisor")
    expect(names[3]).toContain("Camara")
  })

  it("Archived metas are not in the list", async () => {
    listMetas.mockResolvedValue([meta({ name: "Celular" })])
    renderPage()
    expect(await screen.findByText("Celular")).toBeInTheDocument()
    expect(screen.queryByText("Moto")).not.toBeInTheDocument()
  })

  it("The list reads on a phone without scrolling sideways", async () => {
    renderPage()
    await screen.findByText("Celular")
    const row = screen.getAllByRole("listitem")[0]
    expect(row.querySelector("table")).toBeNull()
    expect(screen.getByText(/4\.800\.000/)).toBeInTheDocument()
    expect(screen.getByText(/1\.600\.000/)).toBeInTheDocument()
  })
})

describe("AC-45 — the form says what the meta will ask before it is created", () => {
  it("The create button says what it is about to do", async () => {
    previewMeta.mockResolvedValue({ asks: 4_000_000_000, months_left: 1, over_the_month: true })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Celular")
    await user.click(screen.getByRole("button", { name: "Nueva meta" }))
    await user.type(screen.getByLabelText("Nombre *"), "Casa")
    await user.type(screen.getByLabelText("Cuánto * (COP)"), "80000000")
    await user.type(screen.getByLabelText("Cuándo *"), "2026-09")

    await waitFor(() => expect(screen.getByText(/40\.000\.000 al mes/)).toBeInTheDocument())
    expect(screen.getByRole("alert")).toHaveTextContent(/más de lo que tu mes tiene/)
    expect(screen.getByRole("button", { name: "Crear de todos modos" })).toBeInTheDocument()
  })
})

describe("AC-5 — the navigation offers Metas", () => {
  it("The navigation offers Metas beside Fondos y presupuestos", () => {
    const planning = GROUPS.find((group) => group.title === "Planeación")
    expect(planning?.items.map((item) => item.label)).toEqual(["Fondos y presupuestos", "Metas"])
    expect(planning?.items.map((item) => item.href)).toContain("/metas")
  })
})

const CANCELLED = {
  id: 9,
  name: "Nevera",
  amount: 200_000_000,
  currency: "COP",
  start_month: "2026-08",
  target_month: "2026-11",
  closed: false,
  archived: true,
}

describe("AC-8 — the three answers actually answer", () => {
  it("closing a completed meta closes it", async () => {
    listMetas.mockResolvedValue([meta({ complete: true })])
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: /Cerrar Celular/ }))
    await waitFor(() => expect(closeMeta).toHaveBeenCalledWith(1))
  })

  it("carrying on with another amount asks for it and sends it", async () => {
    listMetas.mockResolvedValue([meta({ complete: true })])
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: /otro monto/ }))
    await user.type(screen.getByLabelText("Nuevo monto (COP)"), "12000000")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(setMeta).toHaveBeenCalledTimes(1))
    expect(setMeta.mock.calls[0][2]).toEqual({ amount: 1_200_000_000 })
  })

  it("carrying on with another month asks for it and sends it", async () => {
    listMetas.mockResolvedValue([meta({ complete: true })])
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: /otro mes/ }))
    await user.type(screen.getByLabelText("Nuevo mes"), "2027-06")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() => expect(setMeta).toHaveBeenCalledTimes(1))
    expect(setMeta.mock.calls[0][2]).toEqual({ target_month: "2027-06" })
  })
})

describe("AC-34 — money can be put in by hand", () => {
  it("putting money in sends what was typed", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Ponerle plata" }))
    await user.type(screen.getByLabelText("Cuánto le pones (COP)"), "500000")
    await user.click(screen.getByRole("button", { name: "Ponerla" }))
    await waitFor(() => expect(contribute).toHaveBeenCalledTimes(1))
    expect(contribute.mock.calls[0][2]).toBe(50_000_000)
  })

  it("a meta waiting on an answer is not asked for money, it is asked to be answered", async () => {
    listMetas.mockResolvedValue([meta({ complete: true })])
    renderPage()
    expect(await screen.findByRole("button", { name: /Cerrar Celular/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Ponerle plata" })).toBeNull()
  })
})

describe("AC-29 — a meta is archived and restored, never destroyed", () => {
  it("cancelling a meta cancels it", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: /Cancelar Celular/ }))
    await waitFor(() => expect(cancelMeta).toHaveBeenCalledWith(1, THIS_MONTH))
  })

  it("a cancelled meta is listed apart, with the way back", async () => {
    listArchived.mockResolvedValue([CANCELLED])
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText("Canceladas")).toBeInTheDocument()
    expect(screen.getByText(/empieza otra vez desde cero/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Traer Nevera de vuelta" }))
    await waitFor(() => expect(restoreMeta).toHaveBeenCalledWith(9, THIS_MONTH))
  })

  it("says nothing about cancelled metas when there are none", async () => {
    renderPage()
    await screen.findByText("Celular")
    expect(screen.queryByText("Canceladas")).toBeNull()
  })
})

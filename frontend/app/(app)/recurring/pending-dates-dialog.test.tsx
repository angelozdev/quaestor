import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { queryWrapper } from "@/tests/factories"
import { PendingDatesDialog } from "./pending-dates-dialog"

const pendingDates = vi.fn()
const acceptPendingDates = vi.fn()
const declinePendingDates = vi.fn()

vi.mock("@/lib/api/recurring", () => ({
  pendingDates: (...a: unknown[]) => pendingDates(...a),
  acceptPendingDates: (...a: unknown[]) => acceptPendingDates(...a),
  declinePendingDates: (...a: unknown[]) => declinePendingDates(...a),
}))

const OFFERED = ["2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22"]

const open = () =>
  render(
    <PendingDatesDialog
      recurring={{ id: 7, name: "Netflix", amount: 2_590_000, currency: "COP" }}
      onOpenChange={vi.fn()}
    />,
    { wrapper: queryWrapper },
  )

describe("PendingDatesDialog", () => {
  beforeEach(() => {
    pendingDates.mockReset().mockResolvedValue(OFFERED)
    acceptPendingDates.mockReset().mockResolvedValue([])
    declinePendingDates.mockReset().mockResolvedValue([])
  })

  it("shows every date that is waiting for an answer", async () => {
    open()
    const dialog = await screen.findByRole("dialog")
    const boxes = await within(dialog).findAllByRole("checkbox")
    expect(boxes).toHaveLength(OFFERED.length)
  })

  it("records only the dates the user ticked", async () => {
    const user = userEvent.setup()
    open()
    const dialog = await screen.findByRole("dialog")
    const boxes = await within(dialog).findAllByRole("checkbox")
    await user.click(boxes[0])
    await user.click(boxes[2])
    await user.click(within(dialog).getByRole("button", { name: /registrar/i }))

    await waitFor(() =>
      expect(acceptPendingDates).toHaveBeenCalledWith(7, ["2026-01-01", "2026-01-15"]),
    )
  })

  it("cannot record when nothing is ticked", async () => {
    open()
    const dialog = await screen.findByRole("dialog")
    await screen.findAllByRole("checkbox")
    expect(within(dialog).getByRole("button", { name: /registrar/i })).toBeDisabled()
  })

  it("declines every offered date at once", async () => {
    const user = userEvent.setup()
    open()
    const dialog = await screen.findByRole("dialog")
    await within(dialog).findAllByRole("checkbox")
    await user.click(within(dialog).getByRole("button", { name: /descartar todas/i }))

    await waitFor(() => expect(declinePendingDates).toHaveBeenCalledWith(7, OFFERED))
  })

  it("says so when nothing is waiting", async () => {
    pendingDates.mockResolvedValue([])
    open()
    const dialog = await screen.findByRole("dialog")
    expect(await within(dialog).findByText(/no hay fechas pendientes/i)).toBeInTheDocument()
  })
})

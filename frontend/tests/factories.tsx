import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { HELP_LABEL } from "@/components/screen-help"
import type { Transaction } from "@/lib/api/types"

/**
 * Open a screen's "¿Cómo funciona esto?" panel and hand back the panel.
 *
 * Ten screens carry the same control, so ten tests would otherwise write the
 * same three lines. `user` is passed in only where the test drives fake timers.
 */
export async function openHelpPanel(screenName: string, user = userEvent.setup()) {
  await user.click(await screen.findByRole("button", { name: HELP_LABEL }))
  return screen.getByRole("dialog", { name: `¿Cómo funciona ${screenName}?` })
}

/**
 * The control under a label that names it in text only.
 *
 * Several dialogs carry a `Label` with no `htmlFor` over a `MoneyInput` or an
 * `EntitySelect` with no `id`, so `getByLabelText` cannot reach them; the
 * surrounding field is the nearest thing a test can name without asserting on
 * class names.
 */
export function fieldUnder(label: string | RegExp) {
  const field = screen.getByText(label).parentElement
  if (!field) throw new Error(`the label "${label}" stands outside a field`)
  return field
}

const CATEGORY_ID = 3

/** A movement as the API returns it. Expenses and incomes carry a category and
 * transfers carry none (ADR-0042), so the default follows `type` unless the
 * caller overrides it. */
export function makeTransaction(overrides: Partial<Transaction> = {}): Transaction {
  const type = overrides.type ?? "expense"
  return {
    id: 1,
    date: "2026-07-10",
    payee: "Exito",
    notes: null,
    type: "expense",
    status: "posted",
    amount: 5_000_000,
    currency: "COP",
    cop_equivalent: 5_000_000,
    account_id: 1,
    category_id: type === "transfer" ? null : CATEGORY_ID,
    meta_id: null,
    transfer_group_id: null,
    transfer_direction: null,
    source: "manual",
    created_at: "2026-07-10T00:00:00Z",
    tags: [],
    ...overrides,
  }
}

export function queryWrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

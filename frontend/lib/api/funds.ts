import { del, get, post, qs } from "./client"
import type {
  ChargeMark,
  ChargeUnlink,
  Fund,
  FundCreate,
  FundLine,
  FundPreview,
  MonthAvailable,
  MonthRates,
} from "./types"

export const listFunds = () => get<FundLine[]>("/funds")
export const createFund = (body: FundCreate) => post<Fund>("/funds", body)
export const previewFund = (body: FundCreate) => post<FundPreview>("/funds/preview", body)
export const deleteFund = (id: number) => del<void>(`/funds/${id}`)
export const moneyAvailable = (month: string) =>
  get<MonthAvailable>(`/funds/available${qs({ month })}`)
export const moneyRates = (month: string) => get<MonthRates>(`/funds/rates${qs({ month })}`)

export const chargeMarks = (month: string) => get<ChargeMark[]>(`/funds/charges${qs({ month })}`)

/** The turns of one charge nobody has settled yet, soonest first (ISO dates). */
export const openTurns = (recurringId: number) =>
  get<string[]>(`/funds/charges/${recurringId}/turns`)
export const markCharge = (recurringId: number, month: string) =>
  post<Fund>(`/funds/charges/${recurringId}${qs({ month })}`, {})
export const unmarkCharge = (recurringId: number) => del<void>(`/funds/charges/${recurringId}`)
/**
 * What saving an edit would cost the charge's fund, asked before it is saved.
 *
 * Every field that can leave the charge with no turn to save for, or no month
 * to save in, has to travel — asking about the cadence alone let an end date
 * delete a fund in silence.
 */
export const chargeEditCost = (
  recurringId: number,
  body: {
    month: string
    interval_unit?: string
    interval_count?: number
    start_date?: string
    end_date?: string | null
  },
) => post<{ would_lose_its_fund: boolean }>(`/funds/charges/${recurringId}/edit-cost`, body)

/** What a payment stops settling if it is filed under another category (AC-5). */
export const paymentRefileCost = (txId: number, categoryId: number | null) =>
  post<ChargeUnlink | null>(`/funds/payments/${txId}/refile-cost`, { category_id: categoryId })

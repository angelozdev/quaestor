import { del, get, post, qs } from "./client"
import type {
  ChargeMark,
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
export const chargeEditCost = (
  recurringId: number,
  body: { month: string; interval_unit?: string; interval_count?: number },
) => post<{ would_lose_its_fund: boolean }>(`/funds/charges/${recurringId}/edit-cost`, body)

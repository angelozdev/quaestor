import { del, get, patch, post, qs } from "./client"
import type {
  Fund,
  FundCreate,
  FundLine,
  FundPreview,
  FundUpdate,
  MonthAvailable,
  MonthRates,
} from "./types"

export const listFunds = () => get<FundLine[]>("/funds")
export const createFund = (body: FundCreate) => post<Fund>("/funds", body)
export const previewFund = (body: FundCreate) => post<FundPreview>("/funds/preview", body)
export const setFund = (id: number, body: FundUpdate) => patch<Fund>(`/funds/${id}`, body)
export const deleteFund = (id: number) => del<void>(`/funds/${id}`)
export const moneyAvailable = (month: string) =>
  get<MonthAvailable>(`/funds/available${qs({ month })}`)
export const moneyRates = (month: string) => get<MonthRates>(`/funds/rates${qs({ month })}`)

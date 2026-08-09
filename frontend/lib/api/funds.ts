import { del, get, post, qs } from "./client"
import type { Fund, FundCreate, FundLine, FundPreview, MonthAvailable, MonthRates } from "./types"

export const listFunds = () => get<FundLine[]>("/funds")
export const createFund = (body: FundCreate) => post<Fund>("/funds", body)
export const previewFund = (body: FundCreate) => post<FundPreview>("/funds/preview", body)
export const deleteFund = (id: number) => del<void>(`/funds/${id}`)
export const moneyAvailable = (month: string) =>
  get<MonthAvailable>(`/funds/available${qs({ month })}`)
export const moneyRates = (month: string) => get<MonthRates>(`/funds/rates${qs({ month })}`)

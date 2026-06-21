import { get, qs } from "./client"
import type { MonthlyReport } from "./types"

export const report = (month: string) => get<MonthlyReport>(`/reports${qs({ month })}`)

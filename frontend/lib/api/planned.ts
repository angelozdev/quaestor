import { get, post, qs } from "./client"
import type { ConfirmPaymentBody, PlanPaymentCreate, ToPay, Transaction } from "./types"

export const toPay = (since: string, until: string) =>
  get<ToPay>(`/planned/to-pay${qs({ since, until })}`)

export const planPayment = (body: PlanPaymentCreate) => post<Transaction>("/planned", body)

export const confirmPayment = (id: number, body: ConfirmPaymentBody = {}) =>
  post<Transaction>(`/planned/${id}/confirm`, body)

export const skipPlanned = (id: number) => post<Transaction>(`/planned/${id}/skip`, {})

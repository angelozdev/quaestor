import { del, get, patch, post, qs } from "./client"
import type {
  Transaction,
  TransactionCreate,
  TransactionFilters,
  TransactionUpdate,
  TransferCreate,
  TransferOut,
} from "./types"

export const listTransactions = (filters: TransactionFilters = {}) =>
  get<Transaction[]>(
    `/transactions${qs(filters as Record<string, string | number | boolean | undefined>)}`,
  )

export const createTransaction = (body: TransactionCreate) =>
  post<Transaction>("/transactions", body)

export const createTransfer = (body: TransferCreate) =>
  post<TransferOut>("/transactions/transfer", body)

export const updateTransaction = (id: number, body: TransactionUpdate) =>
  patch<Transaction>(`/transactions/${id}`, body)

export const deleteTransaction = (id: number) => del<void>(`/transactions/${id}`)

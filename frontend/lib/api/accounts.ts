import { del, get, patch, post, qs } from "./client"
import type { Account, AccountCreate, AccountUpdate } from "./types"

export const listAccounts = (archived = false) => get<Account[]>(`/accounts${qs({ archived })}`)

export const createAccount = (body: AccountCreate) => post<Account>("/accounts", body)

export const updateAccount = (id: number, body: AccountUpdate) =>
  patch<Account>(`/accounts/${id}`, body)

export const archiveAccount = (id: number) => del<void>(`/accounts/${id}`)

export const restoreAccount = (id: number) => post<Account>(`/accounts/${id}/restore`, {})

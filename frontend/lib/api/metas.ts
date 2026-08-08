import { del, get, patch, post, qs } from "./client"
import type { MetaContribution, MetaCreate, MetaPreview, MetaStatus, MonthSplit } from "./types"

export const listMetas = (month: string) => get<MetaStatus[]>(`/metas${qs({ month })}`)
export const monthSplit = (month: string) => get<MonthSplit>(`/metas/split${qs({ month })}`)
export const previewMeta = (month: string, body: MetaCreate) =>
  post<MetaPreview>(`/metas/preview${qs({ month })}`, body)
export const createMeta = (month: string, body: MetaCreate) =>
  post<MetaStatus>(`/metas${qs({ month })}`, body)
export const setMeta = (id: number, month: string, body: Partial<MetaCreate>) =>
  patch<MetaStatus>(`/metas/${id}${qs({ month })}`, body)
export const contribute = (id: number, month: string, amount: number) =>
  post<MetaContribution>(`/metas/${id}/contributions${qs({ month })}`, { amount })
export const listContributions = (id: number) =>
  get<MetaContribution[]>(`/metas/${id}/contributions`)
export const removeContribution = (id: number) => del<void>(`/metas/contributions/${id}`)
export const cancelMeta = (id: number, month: string) => del<void>(`/metas/${id}${qs({ month })}`)
export const closeMeta = (id: number) => post<MetaStatus>(`/metas/${id}/close`, {})
export const restoreMeta = (id: number, month: string) =>
  post<MetaStatus>(`/metas/${id}/restore${qs({ month })}`, {})

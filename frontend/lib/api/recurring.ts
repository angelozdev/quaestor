import { get, post, patch, del, qs } from "./client";
import type { Recurring, RecurringCreate, RecurringUpdate, Occurrence } from "./types";

export const listRecurring = (active?: boolean) =>
  get<Recurring[]>(`/recurring${qs({ active })}`);

export const createRecurring = (body: RecurringCreate) =>
  post<Recurring>("/recurring", body);

export const skipRecurring = (id: number, due_date: string) =>
  post<Occurrence>(`/recurring/${id}/skip`, { due_date });

export const updateRecurring = (id: number, body: RecurringUpdate) =>
  patch<Recurring>(`/recurring/${id}`, body);

export const deleteRecurring = (id: number) => del<void>(`/recurring/${id}`);

export const restoreRecurring = (id: number) =>
  post<Recurring>(`/recurring/${id}/restore`, {});

import { get, post, patch, del, qs } from "./client";
import type { Category, CategoryCreate, CategoryUpdate } from "./types";

export const listCategories = (archived = false) =>
  get<Category[]>(`/categories${qs({ archived })}`);

export const createCategory = (body: CategoryCreate) =>
  post<Category>("/categories", body);

export const updateCategory = (id: number, body: CategoryUpdate) =>
  patch<Category>(`/categories/${id}`, body);

export const archiveCategory = (id: number) => del<void>(`/categories/${id}`);

export const restoreCategory = (id: number) =>
  post<Category>(`/categories/${id}/restore`, {});

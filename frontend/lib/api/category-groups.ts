import { get, post, patch, del, qs } from "./client";
import type { CategoryGroup, CategoryGroupCreate, CategoryGroupUpdate } from "./types";

export const listCategoryGroups = (archived = false) =>
  get<CategoryGroup[]>(`/category-groups${qs({ archived })}`);

export const createCategoryGroup = (body: CategoryGroupCreate) =>
  post<CategoryGroup>("/category-groups", body);

export const updateCategoryGroup = (id: number, body: CategoryGroupUpdate) =>
  patch<CategoryGroup>(`/category-groups/${id}`, body);

export const archiveCategoryGroup = (id: number) =>
  del<void>(`/category-groups/${id}`);

export const restoreCategoryGroup = (id: number) =>
  post<CategoryGroup>(`/category-groups/${id}/restore`, {});

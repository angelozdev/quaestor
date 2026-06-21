import { get, post, patch, del } from "./client";
import type { Tag, TagCreate, TagUpdate } from "./types";

export const listTags    = ()                  => get<Tag[]>("/tags");
export const createTag   = (body: TagCreate)   => post<Tag>("/tags", body);
export const updateTag   = (id: number, body: TagUpdate) => patch<Tag>(`/tags/${id}`, body);
export const deleteTag   = (id: number)        => del<void>(`/tags/${id}`);

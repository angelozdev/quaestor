import { get, post, qs } from "./client";
import type { Fx, FxCreate } from "./types";

export const getFx = (date?: string) => get<Fx>(`/fx${qs({ date })}`);
export const setFx = (body: FxCreate) => post<Fx>("/fx", body);

import { get, post } from "./client"
import type { Fx, FxCreate } from "./types"

export const getFx = () => get<Fx>("/fx")
export const setFx = (body: FxCreate) => post<Fx>("/fx", body)

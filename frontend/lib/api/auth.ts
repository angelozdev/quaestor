import { post } from "./client"

export const login = (password: string) => post<{ ok: boolean }>("/auth/login", { password })
export const logout = () => post<{ ok: boolean }>("/auth/logout")

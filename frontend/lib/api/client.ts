import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios"
import { csrfHeaders } from "@/lib/csrf"
import { ApiError, onUnauthorized } from "./types"

export const http = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  Object.assign(config.headers, csrfHeaders())
  return config
})

const SESSION_EXPIRED_MESSAGE = "Tu sesión expiró. Vuelve a iniciar sesión e inténtalo de nuevo."

http.interceptors.response.use(
  (res) => (res.status === 204 ? undefined : res.data),
  (err: AxiosError) => {
    const status = err.response?.status ?? 0
    const url = err.config?.url ?? ""
    if (status === 401 && !url.startsWith("/auth")) {
      onUnauthorized?.()
      throw new ApiError(status, "Unauthorized", SESSION_EXPIRED_MESSAGE)
    }
    const data = err.response?.data as {
      error?: string
      detail?: string
      fields?: Record<string, string>
    } | null
    throw new ApiError(
      status,
      data?.error ?? "Error",
      data?.detail ?? `Request failed (${status})`,
      data?.fields,
    )
  },
)

export const get = <T>(url: string) => http.get<T>(url) as unknown as Promise<T>
export const post = <T>(url: string, data?: unknown) =>
  http.post<T>(url, data) as unknown as Promise<T>
export const patch = <T>(url: string, data?: unknown) =>
  http.patch<T>(url, data) as unknown as Promise<T>
export const del = <T>(url: string) => http.delete<T>(url) as unknown as Promise<T>

export function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ""
}

"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"
import { toast } from "sonner"
import { login } from "@/lib/api/auth"
import { ApiError } from "@/lib/api/types"

export default function LoginPage() {
  const router = useRouter()
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await login(password)
      router.replace("/")
      router.refresh()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo iniciar sesión")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main
      className="grid min-h-screen place-items-center p-6"
      style={{ background: "var(--muted)" }}
    >
      <div className="w-full max-w-sm animate-fade-up">
        <div
          className="rounded-xl p-8 space-y-6"
          style={{
            background: "var(--card)",
            boxShadow: "var(--shadow-pop)",
          }}
        >
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">Quaestor</h1>
            <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
              Ingresa tu contraseña para continuar
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="password" className="block text-sm font-medium">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                // biome-ignore lint/a11y/noAutofocus: login form UX — focus password field on mount so users can start typing immediately
                autoFocus
                required
                placeholder="••••••••"
                className="w-full rounded-md px-3 py-2 text-sm outline-none transition-colors"
                style={{
                  background: "var(--input)",
                  border: "1px solid var(--border)",
                  color: "var(--foreground)",
                }}
                onFocus={(e) => (e.target.style.borderColor = "var(--foreground)")}
                onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-md py-2 text-sm font-medium transition-opacity disabled:opacity-50"
              style={{
                background: "var(--primary)",
                color: "var(--primary-foreground)",
              }}
            >
              {loading ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </div>
      </div>
    </main>
  )
}

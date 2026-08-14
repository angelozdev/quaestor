"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { ThemeProvider } from "next-themes"
import { useEffect, useState } from "react"
import { ApiError, setUnauthorizedHandler } from "@/lib/api"
import { Toaster } from "@/ui"

const RETRIED_ANYWAY = [408, 429]

/**
 * Whether a failed read is worth asking again for.
 *
 * A 4xx is the server's answer, not a hiccup: asking twice returns the same
 * refusal a second later, and until it lands the screen has nothing to show —
 * which is how a meta's create form came to swallow the message that says why
 * it cannot be created. A timeout and a rate limit are the exceptions; those
 * do get better on their own.
 */
export function worthAskingAgain(failureCount: number, error: Error): boolean {
  const refused =
    error instanceof ApiError &&
    error.status >= 400 &&
    error.status < 500 &&
    !RETRIED_ANYWAY.includes(error.status)
  return refused ? false : failureCount < 1
}

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: worthAskingAgain } },
      }),
  )

  useEffect(() => {
    setUnauthorizedHandler(() => {
      client.clear()
      router.replace("/login")
      router.refresh()
    })
    return () => setUnauthorizedHandler(null)
  }, [client, router])

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      <QueryClientProvider client={client}>
        {children}
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ThemeProvider>
  )
}

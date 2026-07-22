"use client"

import { type ReactNode, useEffect, useState } from "react"
import { ErrorState } from "@/components/error-state"

type QueryLike<T> = {
  isPending: boolean
  isError: boolean
  data: T | undefined
  refetch: () => void
}

export function QueryBoundary<T>({
  query,
  skeleton,
  empty,
  errorMessage = "No se pudo cargar",
  delayMs = 150,
  children,
}: {
  query: QueryLike<T>
  skeleton: ReactNode
  empty?: { when: (data: T) => boolean; node: ReactNode }
  errorMessage?: string
  delayMs?: number
  children: (data: T) => ReactNode
}) {
  const [showSkeleton, setShowSkeleton] = useState(delayMs === 0)
  useEffect(() => {
    if (!query.isPending) {
      setShowSkeleton(false)
      return
    }
    if (delayMs === 0) {
      setShowSkeleton(true)
      return
    }
    const t = setTimeout(() => setShowSkeleton(true), delayMs)
    return () => clearTimeout(t)
  }, [query.isPending, delayMs])

  // Data-first: loaded data stays visible even if a background refetch fails.
  if (query.data !== undefined) {
    return (
      <>
        {query.isError ? (
          <p role="alert" className="text-xs" style={{ color: "var(--expense)" }}>
            No se pudo actualizar.{" "}
            <button type="button" className="underline" onClick={query.refetch}>
              Reintentar
            </button>
          </p>
        ) : null}
        {empty?.when(query.data) ? empty.node : children(query.data)}
      </>
    )
  }
  if (query.isError) {
    return <ErrorState message={errorMessage} onRetry={query.refetch} />
  }
  return showSkeleton ? skeleton : null
}

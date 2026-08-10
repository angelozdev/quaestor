"use client"

import { X } from "lucide-react"
import { useEffect, useState } from "react"
import { translateChatError } from "@/lib/chat-errors"
import { Button } from "@/ui"

type Props = {
  error: Error
  onRetry?: () => void
}

export function ChatErrorBanner({ error, onRetry }: Props) {
  const [dismissed, setDismissed] = useState(false)
  const message = translateChatError(error)

  // Reset dismissed when a new error arrives.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally re-fire on prop change
  useEffect(() => {
    setDismissed(false)
  }, [error])

  if (dismissed) return null

  return (
    <div
      role="alert"
      className="mx-1 mb-1 flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-xs"
      style={{
        borderColor: "var(--destructive)",
        color: "var(--destructive)",
        background: "color-mix(in oklch, var(--destructive) 6%, transparent)",
      }}
    >
      <span>{message}</span>
      <div className="flex items-center gap-2">
        {onRetry && (
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={onRetry}
            className="border-destructive bg-transparent text-destructive"
          >
            Reintentar
          </Button>
        )}
        <Button
          type="button"
          size="icon-xs"
          variant="ghost"
          onClick={() => setDismissed(true)}
          aria-label="Cerrar mensaje de error"
          className="text-destructive"
        >
          <X className="size-3" />
        </Button>
      </div>
    </div>
  )
}

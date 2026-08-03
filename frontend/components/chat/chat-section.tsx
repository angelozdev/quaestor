"use client"

import { useChat } from "@ai-sdk/react"
import { useQueryClient } from "@tanstack/react-query"
import { useMemo } from "react"
import { createChatTransport } from "@/lib/chat-transport"
import { invalidate } from "@/lib/query"
import { ChatEmptyState } from "./chat-empty-state"
import { ChatErrorBanner } from "./chat-error-banner"
import { ChatInput } from "./chat-input"
import { ChatThread } from "./chat-thread"

export function ChatSection() {
  const qc = useQueryClient()

  const transport = useMemo(() => createChatTransport(), [])

  const { messages, sendMessage, stop, status, error, regenerate } = useChat({
    transport,
    onFinish: () => {
      // Scoped invalidation: only the entity roots the 52 MCP tools may have
      // mutated. NEVER call qc.invalidateQueries() with no args — that wipes
      // settings/preferences/categories the chat cannot touch, deviates from
      // the codebase pattern (to-pay-widget.tsx, every mutation hook), and
      // forces unrelated cards to refetch on every assistant turn.
      invalidate(qc, "chatAssistantTurn")
    },
  })

  return (
    <section aria-label="Asistente financiero" className="space-y-4">
      <header className="space-y-0.5">
        <p
          className="font-display text-xl font-semibold tracking-tight"
          style={{ color: "var(--foreground)" }}
        >
          Asistente
        </p>
        <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
          Pregunta en lenguaje natural sobre tus finanzas.
        </p>
      </header>

      <div
        className="rounded-lg border"
        style={{
          background: "var(--card)",
          borderColor: "var(--border)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        {messages.length === 0 && status === "ready" ? (
          <ChatEmptyState onPick={(text) => sendMessage({ text })} />
        ) : (
          <ChatThread messages={messages} status={status} />
        )}

        {status === "error" && error && <ChatErrorBanner error={error} onRetry={regenerate} />}

        <ChatInput status={status} onSend={(text) => sendMessage({ text })} onStop={stop} />
      </div>
    </section>
  )
}

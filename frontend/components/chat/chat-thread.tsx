"use client"

import { useEffect, useRef } from "react"
import type { UIMessage } from "./chat.types"
import { ChatMessage } from "./chat-message"

type Props = {
  messages: UIMessage[]
  status: "submitted" | "streaming" | "ready" | "error"
}

const USER_SCROLL_THRESHOLD_PX = 40

export function ChatThread({ messages, status }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const prevLenRef = useRef(0)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    // Only auto-scroll when messages grew (not on unrelated re-renders).
    if (messages.length > prevLenRef.current) {
      const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight)
      if (distanceFromBottom <= USER_SCROLL_THRESHOLD_PX) {
        el.scrollTop = el.scrollHeight
      }
    }
    prevLenRef.current = messages.length
  }, [messages.length])

  // Also scroll when the streaming text grows the trailing message height.
  // biome-ignore lint/correctness/useExhaustiveDependencies: trigger on every messages mutation during streaming
  useEffect(() => {
    if (status !== "streaming") return
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight)
    if (distanceFromBottom <= USER_SCROLL_THRESHOLD_PX) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, status])

  const last = messages[messages.length - 1]
  const showCursorOnLast =
    status === "streaming" && last?.role === "assistant"

  return (
    <section
      aria-live="polite"
      aria-label="Conversación con asistente"
      className="flex w-full flex-col gap-3 px-1 py-3"
    >
      <div
        ref={scrollRef}
        data-testid="chat-scroll"
        className="flex flex-col gap-2 px-1"
        style={{
          maxHeight: "min(420px, 60vh)",
          overflowY: "auto",
        }}
      >
        {messages.map((m, idx) => (
          <ChatMessage
            key={m.id}
            message={m}
            showCursor={showCursorOnLast && idx === messages.length - 1}
          />
        ))}
      </div>
    </section>
  )
}

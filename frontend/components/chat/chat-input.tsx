"use client"

import { Send, Square } from "lucide-react"
import { useEffect, useLayoutEffect, useRef, useState } from "react"

type Props = {
  status: "submitted" | "streaming" | "ready" | "error"
  onSend: (text: string) => void
  onStop: () => void
  autoFocus?: boolean
  maxLength?: number
  cooldownMs?: number
}

const MAX_LINES = 6
const LINE_HEIGHT_PX = 22 // matches text-base leading; tweak if global typography changes.
const DEFAULT_MAX_LENGTH = 32000 // mirrors backend 32 KB cap (ADR-0014).
const DEFAULT_COOLDOWN_MS = 600 // UX guard against double-submit; NOT a rate limit.

function autoGrow(el: HTMLTextAreaElement | null) {
  if (!el) return
  el.style.height = "auto"
  const max = MAX_LINES * LINE_HEIGHT_PX
  el.style.height = `${Math.min(el.scrollHeight, max)}px`
  el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden"
}

// useLayoutEffect warns on SSR; alias to useEffect on the server.
const useIsoLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect

export function ChatInput({
  status,
  onSend,
  onStop,
  autoFocus = true,
  maxLength = DEFAULT_MAX_LENGTH,
  cooldownMs = DEFAULT_COOLDOWN_MS,
}: Props) {
  const [text, setText] = useState("")
  const [cooldown, setCooldown] = useState(false)
  const ref = useRef<HTMLTextAreaElement | null>(null)

  useIsoLayoutEffect(() => {
    autoGrow(ref.current)
  }, [text])

  // Focus on mount when ready.
  useEffect(() => {
    if (autoFocus && status === "ready" && ref.current) {
      ref.current.focus()
    }
  }, [autoFocus, status])

  const busy = status === "submitted" || status === "streaming"
  const blocked = busy || cooldown

  // Esc-to-stop must work even when textarea is disabled (busy). Hook at
  // document level so the user does not need to focus the textarea first.
  useEffect(() => {
    if (!busy) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault()
        onStop()
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [busy, onStop])

  function fireSend() {
    onSend(text)
    setText("")
    if (cooldownMs > 0) {
      setCooldown(true)
      setTimeout(() => setCooldown(false), cooldownMs)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (!blocked && text.trim().length > 0) {
        fireSend()
      }
      return
    }
  }

  function handleClickAction() {
    if (busy) {
      onStop()
    } else if (!cooldown && text.trim().length > 0) {
      fireSend()
    }
  }

  return (
    <div
      className="chat-input-underline flex items-end gap-2 border-t px-1 pt-3 pb-2"
      style={{ borderColor: "var(--border)" }}
    >
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={busy}
        maxLength={maxLength}
        rows={1}
        aria-label="Mensaje para el asistente"
        placeholder={busy ? "Pensando…" : "Pregúntale algo a tu asistente…"}
        className="flex-1 resize-none rounded-md border bg-transparent px-3 py-2 text-sm outline-none transition-colors focus:ring-0"
        style={{
          borderColor: "var(--input)",
          color: "var(--foreground)",
          minHeight: `${LINE_HEIGHT_PX + 16}px`,
        }}
      />
      <button
        type="button"
        onClick={handleClickAction}
        aria-label={busy ? "Detener respuesta" : "Enviar mensaje"}
        className="grid size-9 place-items-center rounded-md transition-opacity disabled:opacity-40"
        style={{
          background: "var(--primary)",
          color: "var(--primary-foreground)",
        }}
        disabled={!busy && (cooldown || text.trim().length === 0)}
      >
        {busy ? <Square className="size-4" /> : <Send className="size-4" />}
      </button>
    </div>
  )
}

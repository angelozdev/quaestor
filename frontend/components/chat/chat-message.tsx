"use client"

import { memo } from "react"
import type { UIMessage } from "./chat.types"
import { isAnyToolPart, isTextPart } from "./chat.types"
import { ChatBlinkingCursor } from "./chat-blinking-cursor"
import { ChatToolChip } from "./chat-tool-chip"

type Props = {
  message: UIMessage
  showCursor: boolean
}

function ChatMessageImpl({ message, showCursor }: Props) {
  if (message.role === "system") return null

  const isUser = message.role === "user"

  // Locate the last text part index for cursor placement.
  const lastTextIndex = message.parts
    .map((p, i) => (isTextPart(p) ? i : -1))
    .reduce((max, i) => (i > max ? i : max), -1)

  const wrapperStyle: React.CSSProperties = isUser
    ? {
        backgroundColor: "var(--secondary)",
        color: "var(--secondary-foreground)",
        padding: "8px 12px",
        borderRadius: "12px",
        maxWidth: "85%",
      }
    : {
        color: "var(--foreground)",
        maxWidth: "100%",
      }

  const wrapperClass = isUser ? "self-end" : "self-start"

  return (
    <div
      data-message-id={message.id}
      className={`${wrapperClass} flex w-fit max-w-full flex-col gap-1.5 text-sm leading-relaxed`}
      style={wrapperStyle}
    >
      {message.parts.map((part, idx) => {
        if (isTextPart(part)) {
          const showTailCursor = showCursor && idx === lastTextIndex && isUser === false
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: parts don't reorder within a message
            <p key={`${message.id}-t-${idx}`} className="whitespace-pre-wrap">
              {part.text}
              {showTailCursor && <ChatBlinkingCursor />}
            </p>
          )
        }
        if (isAnyToolPart(part)) {
          // biome-ignore lint/suspicious/noArrayIndexKey: parts don't reorder within a message
          return <ChatToolChip key={`${message.id}-tl-${idx}`} part={part} />
        }
        // Other part kinds (source-url, reasoning, file, data) are out of scope
        // for v1; skip silently. The LLM does not emit them through our backend.
        return null
      })}
      {/* Cursor also appears when the message has NO text part but is the live tail. */}
      {showCursor &&
        isUser === false &&
        lastTextIndex === -1 && <ChatBlinkingCursor />}
    </div>
  )
}

export const ChatMessage = memo(ChatMessageImpl)

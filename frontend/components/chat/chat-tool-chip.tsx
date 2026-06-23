"use client"

import { getToolName } from "ai"
import { useState } from "react"
import type { AnyToolPart } from "./chat.types"

type Props = {
  part: AnyToolPart
}

function nameOf(part: AnyToolPart): string {
  try {
    return getToolName(part)
  } catch {
    // Defensive: if `ai`'s helper chokes on a malformed part, fall back.
    if (part.type === "dynamic-tool") return part.toolName
    if (part.type.startsWith("tool-")) return part.type.slice("tool-".length)
    return "tool"
  }
}

function isRunning(state: AnyToolPart["state"]): boolean {
  return state === "input-streaming" || state === "input-available"
}

function isError(state: AnyToolPart["state"]): boolean {
  return state === "output-error"
}

function isExpandable(state: AnyToolPart["state"]): boolean {
  return state === "output-available" || state === "output-error"
}

export function ChatToolChip({ part }: Props) {
  const [open, setOpen] = useState(false)
  const toolName = nameOf(part)
  const toggleId = `chat-tool-${part.type === "dynamic-tool" ? part.toolCallId : toolName}`
  const regionId = `${toggleId}-output`
  const running = isRunning(part.state)
  const errored = isError(part.state)
  const expandable = isExpandable(part.state)
  // Auto-expand on error so the failure detail is visible without a click.
  const displayOpen = open || errored

  const dotColor = errored
    ? "var(--destructive)"
    : running
      ? "var(--primary)"
      : "color-mix(in oklch, var(--primary) 60%, transparent)"

  // Prefer JSON.stringify with 2-space indent for both input and output.
  const inputJson =
    part.input !== undefined && part.input !== null
      ? JSON.stringify(part.input, null, 2)
      : null
  const outputText =
    part.state === "output-error"
      ? (part as { errorText?: string }).errorText ?? ""
      : part.state === "output-available"
        ? String((part as { output?: unknown }).output ?? "")
        : ""

  return (
    <div className="my-1.5 inline-block max-w-full">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => expandable && setOpen((v) => !v)}
        disabled={!expandable}
        className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1 font-mono text-xs transition-opacity"
        style={{
          background: "var(--muted)",
          borderColor: "var(--border)",
          color: "var(--foreground)",
          opacity: expandable ? 1 : 0.85,
        }}
      >
        <span
          data-testid="chat-tool-dot"
          aria-hidden
          className={running ? "chat-tool-pulse" : ""}
          style={{
            display: "inline-block",
            width: "8px",
            height: "8px",
            borderRadius: "9999px",
            backgroundColor: dotColor,
          }}
        />
        <span>{toolName}</span>
        {expandable && (
          <span aria-hidden style={{ color: "var(--muted-foreground)" }}>
            {displayOpen ? "▾" : "▸"}
          </span>
        )}
      </button>

      {expandable && displayOpen && (
        <div
          id={regionId}
          role="region"
          aria-label={`${toolName} input and output`}
          className="chat-tool-body mt-1.5 max-w-full overflow-hidden rounded-md border"
          style={{
            background: "var(--popover)",
            borderColor: errored ? "var(--destructive)" : "var(--border)",
            borderLeftWidth: errored ? "3px" : "1px",
          }}
        >
          {inputJson !== null && (
            <div className="border-b px-3 py-2" style={{ borderColor: "var(--border)" }}>
              <p
                className="mb-1 text-[10px] uppercase tracking-wider"
                style={{ color: "var(--muted-foreground)" }}
              >
                Input
              </p>
              <pre
                data-sensitive="true"
                className="overflow-auto font-mono text-xs leading-relaxed"
                style={{ maxHeight: "160px", color: "var(--foreground)" }}
              >
                {inputJson}
              </pre>
            </div>
          )}
          <div className="px-3 py-2">
            <p
              className="mb-1 text-[10px] uppercase tracking-wider"
              style={{ color: "var(--muted-foreground)" }}
            >
              {errored ? "Error" : "Output"}
            </p>
            <pre
              data-sensitive="true"
              className="overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed"
              style={{ maxHeight: "160px", color: "var(--foreground)" }}
            >
              {outputText}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

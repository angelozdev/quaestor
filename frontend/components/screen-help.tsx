"use client"

import { CircleHelp, X } from "lucide-react"
import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ")

export const HELP_LABEL = "¿Cómo funciona esto?"

function focusablesIn(panel: HTMLElement | null): HTMLElement[] {
  return panel === null ? [] : Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE))
}

/**
 * The "¿Cómo funciona esto?" control and the panel it opens.
 *
 * Mechanics only — the trigger, the sheet, opening and closing, the focus trap
 * and giving the reader their place back. It renders whatever content the
 * screen hands it and knows nothing about any screen.
 *
 * The close control, Escape and a press on the backdrop all go through `close`,
 * so the keyboard's place comes back whichever one the reader used.
 *
 * The backdrop dismisses only when the press both began and ended on it, so
 * selecting text in the panel and releasing outside does not throw away what is
 * being read. It listens on the document rather than carrying handlers of its
 * own: the backdrop is not a control, so it stays `aria-hidden`, out of the tab
 * order and free of anything that would announce it as one. Escape and the
 * close control are the keyboard paths.
 *
 * It is deliberately placed outside `QueryBoundary` (ADR-0029): the panel has
 * to open and explain even when the screen's figures never arrive.
 *
 * While it is open the rest of the page is `inert`, so a screen reader cannot
 * browse behind it. `aria-modal` alone does not stop that, which is why the
 * panel is rendered into `body` — from inside the page it could not mark its
 * own ancestors hidden without hiding itself.
 */
export function ScreenHelp({ screen, children }: { screen: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const backdrop = useRef<HTMLDivElement>(null)
  const pressBeganOnBackdrop = useRef(false)
  const titleId = useId()
  const [host, setHost] = useState<HTMLElement | null>(null)

  useEffect(() => {
    const node = document.createElement("div")
    document.body.append(node)
    setHost(node)
    return () => node.remove()
  }, [])

  useEffect(() => {
    if (!open || host === null) return
    const behind = Array.from(document.body.children).filter((el) => el !== host)
    for (const el of behind) el.setAttribute("inert", "")
    return () => {
      for (const el of behind) el.removeAttribute("inert")
    }
  }, [open, host])

  useEffect(() => {
    if (open) focusablesIn(panel.current)[0]?.focus()
  }, [open])

  const close = useCallback(() => {
    setOpen(false)
    trigger.current?.focus()
  }, [])

  useEffect(() => {
    if (!open) return
    const began = (event: MouseEvent) => {
      pressBeganOnBackdrop.current = event.target === backdrop.current
    }
    const ended = (event: MouseEvent) => {
      const dismissed = pressBeganOnBackdrop.current && event.target === backdrop.current
      pressBeganOnBackdrop.current = false
      if (dismissed) close()
    }
    document.addEventListener("mousedown", began)
    document.addEventListener("mouseup", ended)
    return () => {
      document.removeEventListener("mousedown", began)
      document.removeEventListener("mouseup", ended)
    }
  }, [open, close])

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault()
      close()
      return
    }
    if (event.key !== "Tab") return
    const inside = focusablesIn(panel.current)
    if (inside.length === 0) return
    event.preventDefault()
    const at = inside.indexOf(document.activeElement as HTMLElement)
    const step = event.shiftKey ? -1 : 1
    inside[(at + step + inside.length) % inside.length]?.focus()
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors"
        style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}
      >
        <CircleHelp aria-hidden className="size-3.5" />
        {HELP_LABEL}
      </button>

      {open &&
        host !== null &&
        createPortal(
          <div className="fixed inset-0 z-50 flex justify-end">
            <div
              ref={backdrop}
              aria-hidden
              data-slot="screen-help-backdrop"
              className="absolute inset-0 bg-black/40"
            />
            <section
              ref={panel}
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              onKeyDown={onKeyDown}
              className="relative flex h-full w-full max-w-full flex-col overflow-y-auto border-l shadow-xl sm:w-[26rem]"
              style={{ background: "var(--card)", borderColor: "var(--border)" }}
            >
              <header
                className="flex items-start justify-between gap-3 border-b px-4 py-3"
                style={{ borderColor: "var(--border)" }}
              >
                <h2 id={titleId} className="font-display text-base font-semibold tracking-tight">
                  ¿Cómo funciona {screen}?
                </h2>
                <button
                  type="button"
                  onClick={close}
                  aria-label="Cerrar"
                  className="shrink-0 rounded-md p-1"
                  style={{ color: "var(--muted-foreground)" }}
                >
                  <X aria-hidden className="size-4" />
                </button>
              </header>

              <div className="flex-1 space-y-3 break-words px-4 py-4 text-sm leading-relaxed">
                {children}
              </div>

              <footer className="border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
                <button
                  type="button"
                  onClick={close}
                  className="w-full rounded-md border px-3 py-1.5 text-xs transition-colors"
                  style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
                >
                  Entendido
                </button>
              </footer>
            </section>
          </div>,
          host,
        )}
    </>
  )
}

const AN_EXAMPLE = "Las cifras de abajo son de un ejemplo, no tuyas."

/**
 * A claim the panel makes and the entries it quotes to back it.
 *
 * Every panel that quotes anything is this shape, so the shape is written here
 * and only the sentences differ per screen. `label` names the list to a screen
 * reader where the claim is about the list itself rather than the panel.
 */
export function HelpSection({
  lead,
  label,
  children,
}: {
  lead: string
  label?: string
  children: ReactNode
}) {
  return (
    <>
      <p>{lead}</p>
      <ul
        aria-label={label}
        className="space-y-1.5 pl-4"
        style={{ color: "var(--muted-foreground)", listStyleType: "disc" }}
      >
        {children}
      </ul>
    </>
  )
}

/**
 * The same shape, for a screen with nothing of its own to quote.
 *
 * The panel never shows a blank where a figure would go: it works an example
 * and says in words that the figures are an example (AC-11, AC-16). That
 * sentence is written once, here, because every screen owes it.
 */
export function HelpExample({ children }: { children: ReactNode }) {
  return <HelpSection lead={AN_EXAMPLE}>{children}</HelpSection>
}

/**
 * Decorative blinking cursor that marks the live tail of a streaming
 * assistant message. Pure CSS animation (defined in `app/globals.css` keyframe
 * `blink-cursor`); the `@media (prefers-reduced-motion: reduce)` block in
 * globals.css disables the animation and falls back to a static glyph.
 */
export function ChatBlinkingCursor() {
  return (
    <span
      aria-hidden="true"
      data-testid="chat-cursor"
      className="chat-blinking-cursor"
      style={{
        fontFamily: "var(--font-heading)",
        color: "var(--primary)",
        fontSize: "1.2em",
        lineHeight: 1,
        marginLeft: "2px",
      }}
    >
      _
    </span>
  )
}

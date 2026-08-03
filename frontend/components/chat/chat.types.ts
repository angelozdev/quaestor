import type {
  DynamicToolUIPart,
  TextUIPart,
  ToolUIPart,
  UIDataTypes,
  UIMessage,
  UIMessagePart,
  UITools,
} from "ai"
import { isTextUIPart as aiIsTextUIPart, isToolUIPart as aiIsToolUIPart } from "ai"

/**
 * Re-exports + helpers for the chat component layer.
 *
 * `UIMessage` is the canonical message type from `ai`; we narrow it locally
 * with type guards rather than redefining shapes.
 */
export type { DynamicToolUIPart, TextUIPart, ToolUIPart, UIMessage, UIMessagePart }

/**
 * Any tool part the assistant can emit, whether typed (server declared the
 * tool) or dynamic (server did not). The backend in this project does NOT
 * declare tools to the client, so dynamic parts are the norm.
 */
export type AnyToolPart = ToolUIPart | DynamicToolUIPart

/**
 * Re-export of `ai`'s text-part guard. Aliased so component code reads
 * uniformly with the local `isAnyToolPart` helper below.
 */
export const isTextPart = aiIsTextUIPart

/**
 * Narrows any `UIMessagePart` to a tool part (typed OR dynamic).
 * Use this anywhere a component needs the tool name, input, output, or state.
 */
export function isAnyToolPart(part: UIMessagePart<UIDataTypes, UITools>): part is AnyToolPart {
  return aiIsToolUIPart(part)
}

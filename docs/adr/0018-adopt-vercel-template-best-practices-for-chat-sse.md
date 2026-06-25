# 0018. Adopt Vercel template best practices for chat SSE

- **Status:** proposed
- **Date:** 2026-06-24
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context

ADR-0014 shipped the chat endpoint by reverse-engineering the Vercel UI
Message Stream protocol from `ai-sdk.dev/docs`. Three divergences from
the Vercel-owned reference template
(`vercel-labs/ai-sdk-preview-python-streaming`) went unnoticed:

1. `message_id` came from `chunk.id` with a `msg_unknown` fallback.
   Anthropic-native chunks don't carry `.id`, so any future
   `AnthropicNativeProvider` would emit `msg_unknown` to the frontend.
2. `text-start` / `text-delta` / `text-end` events reused `message_id`
   as their `id`. The spec requires a per-part content id (e.g.
   `text-1`) so the frontend can match deltas to parts.
3. `finish` events never carried `messageMetadata.usage`, so the
   frontend can't show token counts and ops can't reconcile billing
   per request.

Full analysis lives in
`docs/superpowers/specs/2026-06-23-vercel-template-best-practices-design.md`.

## Decision

Adopt three patterns from the template. Keep our typed-error discipline
and `provider.py → service.py → events.py` separation. Skip the rich
input adapter (no vision / attachments on the roadmap), the
`protocol=data` query param (closed on `ui-message-stream`), and the
single-turn dispatch refactor (we have an agentic loop per ADR-0014).

## Consequences

- One new field on `LLMEvent`: `usage: dict[str, int] | None = None`.
- Wire format gains one optional field (`messageMetadata.usage`) and
  corrects one field (`text-*.id`). Both forward-compatible.
- Zero new deps, zero new env vars, zero frontend code changes.
- Three new tests, no deletions.
- Future `AnthropicNativeProvider` inherits the message-id strategy
  for free.

## Related

- ADR-0014 — chat endpoint base.
- ADR-0015 — frontend wire-format adapter.
- ADR-0016 — tool-error recovery (isError).
- ADR-0017 — system prompt injection.
- Spec: `docs/superpowers/specs/2026-06-23-vercel-template-best-practices-design.md`.
- Plan: `docs/superpowers/plans/2026-06-24-adopt-vercel-best-practices.md`.

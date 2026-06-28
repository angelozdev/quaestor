# 0020. Security hardening: CSRF, tool tier policy, and tool-output sanitization

- **Status:** accepted
- **Date:** 2026-06-28
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The OWASP review of 2026-06-28 (`docs/security/owasp-review-2026-06-28.md`)
identified four `Critical` findings that need code-level fixes:

- **QUA-A02-01** — `SESSION_SECRET` falls back to the public string
  `"dev-insecure-secret"`, allowing trivial cookie forgery.
- **QUA-A01-01** — cookie-authenticated state-changing endpoints have no CSRF
  defense; `SameSite=Lax` mitigates most cases but not all.
- **QUA-LLM06-01** — the LLM has direct access to all 52 MCP tools,
  including 27 destructive ones (`transfer`, `delete_transaction`,
  `archive_*`, `update_settings`, `delete_tag`).
- **QUA-LLM01-01 / QUA-API10-01** — tool outputs are appended verbatim to
  the LLM conversation, so an attacker who plants text in `payee` or
  `notes` can run an indirect prompt injection that the LLM obeys.

All four are pre-conditions for safe deployment and cannot wait for
multi-user or audit-log work to start.

## Decision drivers

- **Reversibility cost is high**: a cookie forgery or a successful
  destructive-tool prompt injection can move money or delete history
  before the operator notices.
- **Single-user, single-process**: the fix must not introduce a second
  authentication surface or a separate secret manager; everything must
  keep working with the existing `.env`-driven deploy.
- **Defense in depth**: each control must reduce blast radius even if
  one of the others fails.
- **SOLID, no over-engineering**: we want clear, testable primitives,
  not a full RBAC or prompt-firewall stack.

## Considered options

1. **Per-finding single ADR** (4 separate ADRs).
2. **One umbrella ADR for the four findings** (chosen).
3. **Wait for the larger security rework** (MFA, secret manager, rate
   limiting) and bundle the fixes in.

## Decision outcome

Chosen option: **option 2 — one umbrella ADR**, because the four findings
share a single context (OWASP review), share a deploy window, and the
per-fix code changes are small enough that four separate files would
produce four trivial ADRs.

### Pros and cons of the options

**Option 1 — per-finding single ADR**
- Good: granular history; each finding is independently reversible.
- Bad: 4× template overhead; the OWASP context would be duplicated.

**Option 2 — one umbrella ADR**
- Good: matches the source review document; small code, single decision.
- Bad: a future reversal of just one of the four needs to either edit
  this ADR or supersede it.

**Option 3 — wait for larger rework**
- Good: avoids partial state where some findings are closed and others
  are open.
- Bad: leaves four known-critical issues live while we design a much
  larger change; the larger rework keeps slipping because new features
  take priority.

### Detail: each fix

#### SESSION_SECRET hardening (QUA-A02-01)
Remove the `"dev-insecure-secret"` fallback in
`api/__init__.py:_configure_middleware`. Resolve the secret through
`_resolve_session_secret()` which raises `RuntimeError` if the env var is
missing or shorter than 32 bytes (the OWASP-recommended minimum for HMAC
keys, and the natural length of `secrets.token_urlsafe(32)`).

#### CSRF defense (QUA-A01-01) — double-submit cookie pattern
A new `api/csrf.py` provides `CSRFMiddleware` and `issue_csrf_cookie()`.
The middleware sits OUTSIDE CORS (last `add_middleware` call → outermost),
so cross-origin state-changing requests are rejected before they reach the
route. `api/auth.py` issues a fresh CSRF cookie on every `login` and `me`
response; the frontend mirrors the cookie value into the `X-CSRF-Token`
header on every POST/PATCH/PUT/DELETE. Login itself is exempt (no cookie
yet to forge against). All other state-changing routes are protected.

The CORS `allow_headers` list is tightened from `["*"]` to an explicit
`["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID"]`.

#### MCP tool tier policy (QUA-LLM06-01)
Add a `ToolTier` enum (`READ`, `WRITE_SAFE`, `WRITE_DESTRUCTIVE`) in
`mcp/registry.py`, classified for every registered tool. A new
`LLM_ALLOWED_TOOLS = READ | WRITE_SAFE` set is the single source of truth
that drives `chat/mcp/schema.py:filter_for_llm()`, called by
`chat/service.py` before the tool list is passed to the provider.
Destructive tools remain registered on the MCP server so the frontend
HTTP UI and curl/MCP-direct callers can still use them — they just don't
appear in the LLM's tool list, so a prompt injection cannot directly
invoke them. Unknown tool names default to `WRITE_DESTRUCTIVE` (deny by
default).

#### Tool-output sanitization (QUA-LLM01-01 / QUA-API10-01)
A new `chat/sanitize.py` wraps every tool output in
`<<UNTRUSTED_TOOL_OUTPUT: tool_name>>…<<END_UNTRUSTED_TOOL_OUTPUT>>`
delimiters, strips lines whose first non-whitespace token is a role-like
prefix (`SYSTEM:`, `USER:`, `ASSISTANT:`, `INSTRUCTION:`,
`<<INSTRUCT>>`, etc.), and truncates to a configurable ceiling (default
4000 chars). `chat/service.py` sanitizes both the value sent on the SSE
event and the value appended to the in-request `conversation` list, so
the next LLM iteration sees the sanitized form. The system prompt is
extended with one paragraph stating the rule explicitly.

## Consequences

- Good: four `Critical` findings closed without changing the single-user
  product surface or the deploy story.
- Good: the chat agent can no longer reach destructive tools directly,
  regardless of prompt content. The user still has the UI for those.
- Good: indirect prompt injection through `payee` / `notes` / tool
  outputs is contained by the marker wrapper and role-prefix stripping.
- Good: cookie forgery is no longer possible from a known secret.
- Bad / follow-up: cross-surface token separation (`APP_API_TOKEN`,
  `APP_MCP_TOKEN`, `APP_HEALTHCHECK_TOKEN`), MFA, rate limiting, and the
  Caddyfile security headers are still open — they were deliberately
  left out of this ADR because each is a non-trivial change on its own.
- Bad / follow-up: the chat system prompt grows by one paragraph. If the
  prompt becomes too long, revisit the per-turn recompute cost.

## Confirmation

- `tests/api/test_session_secret.py` — five tests cover the missing,
  short, whitespace, exactly-32, and long-secret cases.
- `tests/api/test_csrf.py` — eight tests cover missing header, mismatched
  header, matched header (passes CSRF, hits auth), login exempt, GET
  exempt, OPTIONS exempt, cookie issued on login, cookie rotated on `me`.
- `tests/mcp/test_tool_tiers.py` (new) — every registered tool is in
  exactly one tier; `LLM_ALLOWED_TOOLS` excludes every
  `WRITE_DESTRUCTIVE` name; unknown names default to destructive.
- `tests/chat/test_sanitize.py` (new) — delimiters wrap the output,
  role-prefix lines are stripped, long outputs are truncated, the SSE
  event and the conversation payload both carry the sanitized form.
- Full `pytest` suite stays green (104+ tests in `tests/api`, plus the
  new modules).

## Related

- `docs/security/owasp-review-2026-06-28.md` — source review.
- ADR-0011 (MCP over Tailscale) — `/mcp` defense-in-depth companion.
- ADR-0017 (system-prompt injection) — extended by this ADR's tool-output
  sanitization paragraph.

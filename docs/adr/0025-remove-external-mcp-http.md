# 0025 — Remove External MCP HTTP Exposure (chat-only MCP)

- **Status:** accepted
- **Date:** 2026-07-03
- **Supersedes:** 0011

## Context

Quaestor is single-user. The MCP surface had two consumers: an HTTP streamable-MCP server (`mcp` service on `:9000`, published over Tailscale by the `tailscale` sidecar) for external clients like Claude Code, and an in-process bridge inside the `api` service used by the chat endpoint. The user does not use any external MCP client; the chat covers every interaction they actually have with the tools. The HTTP server + Tailscale sidecar = extra service, extra dependency, extra attack surface, zero user value.

## Decision

Remove the HTTP MCP server and the `tailscale` sidecar. The in-process MCP bridge used by the chat endpoint is the only remaining MCP consumer. Code structure:

- `backend/src/quaestor/mcp/builder.py` (NEW) — `build_mcp()` factory function, single responsibility (Factory pattern, SRP).
- `backend/src/quaestor/mcp/{server,__main__,auth}.py` — DELETED. No commented-out branches, no "remote path" scaffolding. If external MCP access is ever reintroduced, it's a new module + a new ADR.
- `backend/src/quaestor/mcp/{registry,format,tools/*}.py` — unchanged. Tools continue to be invoked in-process by the chat.
- `docker-compose.yml`, `docker-compose.override.yml` — drop `mcp` and `tailscale` services + `tailscale-state` volume.
- `ts-serve.json` — DELETED.
- `.env.example`, `.envrc` — drop `TS_AUTHKEY` and `TS_HOSTNAME`.

## Consequences

- External MCP clients (Claude Code over Tailscale) lose access. If the user wants this back, it's a new ADR.
- One fewer service in the prod stack. One fewer dependency (Tailscale).
- Smaller attack surface: no externally reachable MCP listener, no bearer auth middleware.
- Chat endpoint auth posture unchanged: still requires `Authorization: Bearer $APP_TOKEN`. Defense in depth remains.
- `build_mcp()` lives in a clean module (Factory pattern) — chat depends on an abstraction, not on concrete tool implementations.

## Related

- Spec: `docs/superpowers/specs/2026-07-03-mcp-http-removal-design.md`.
- ADR-0014 — chat endpoint with LiteLLM and in-memory MCP bridge (kept; this ADR confirms it as the only MCP path).
- ADR-0011 (superseded) — original MCP-only-over-Tailscale decision.

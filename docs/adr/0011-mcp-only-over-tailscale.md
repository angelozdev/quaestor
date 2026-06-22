# 0011 — MCP Endpoint Lives Only on the Tailnet

- **Status:** accepted
- **Date:** 2026-06-22

## Context
The MCP server lets agents (Claude Code, others) drive every backend action —
recording expenses, editing categories, moving money. Exposing `/mcp` on the
public internet with only a bearer token is too thin a defense: a leaked
`APP_TOKEN` would be enough to compromise the whole account.

## Decision
`/mcp` is served exclusively by the Tailscale sidecar on the user's private
network. The `mcp` Docker service has NO `ports:` mapping. The Tailscale
sidecar runs `tailscale serve` on its tailnet IP, proxying HTTPS to the `mcp`
container's internal `:9000`. The Caddyfile does NOT route `/mcp`. The public
domain responds 404 on `/mcp`.

This is defense-in-depth: the endpoint doesn't even exist outside the tailnet
(no attack surface), and the bearer token is a second layer for tailnet
members.

## Consequences
- Cloud MCP clients (claude.ai web) cannot reach the endpoint. The spec
  acknowledges this trade-off; revisit only if a real need arises.
- The user's machines must be on the tailnet to use Claude Code against Quaestor.
- If Tailscale is down, `/mcp` is unreachable — fails closed, not open.

## Related
- ADR-0010 (deployment posture), ADR-0006 (HTTP/MCP parity).
- Spec: `docs/superpowers/specs/2026-06-16-P7-deployment-design.md` §HTTPS and
  network, §Auth, §Connect Claude Code.

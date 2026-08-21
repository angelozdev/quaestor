---
skill: browser-verify (CHARTER §6)
agent_id: main-session
feature: fund-opening-balance
started: 2026-08-21T12:45
ended: 2026-08-21T13:00
checkpoint: null
artifacts: []
findings_summary: >
  Live Chrome MCP pass against the real dev stack (just dev-local, real
  production data, current month August 2026). Created a fund on "Home
  Maintenance" (a real category with no prior fund, chosen to avoid
  disturbing any existing fund) via the create-fund form: fixed rule,
  150.000 COP/month, started August 2026 (current month), declaring an
  opening balance of 500.000 COP through the new field — the MoneyInput
  thousand-separator formatting (feature 018) applied live to the new field
  as typed. Fund created successfully ("Fondo creado" toast). The Funds
  table's "Tiene" column read $360.050 for Home Maintenance, and the
  category's own real August spending shown alongside ("Gastaste $139.950")
  makes this exactly right: 500.000 (declared) − 139.950 (real spending
  already posted this month) = 360.050 — confirmed by hand arithmetic
  against the screen, not just glanced at. This is the live, real-browser
  confirmation of both AC-1 (the new form field reaches the wire correctly)
  and AC-2 (the create-time-declared balance correctly participates in the
  current month's figure) — plan.md's Test strategy named exactly these two
  as the browser pass's scope, since AC-3/AC-4/AC-5 (the assistant-dated
  path) have no UI surface to click through and are proven by the
  acceptance suite + mutation instead. Deleted the test fund afterward
  (Eliminar → confirmed via modal → "Fondo eliminado" toast → reloaded the
  page and re-searched for it, confirming it is genuinely gone server-side,
  not just removed from client cache) to leave dev data clean.
human_action_needed: no
recommended_next: mark feature done, update roadmap
tracker_update: local (no-op driver)
exit_criteria:
  - criterion: a screen that writes money is driven in a browser, against real data (CHARTER §6)
    verified_by: human
    met: true
    evidence: "Create-fund form driven live via Chrome MCP against the real dev stack (just dev-local); screenshots captured showing the new opening-balance field, its thousand-separator formatting, and the resulting Funds-table figure"
  - criterion: the value actually computed matches what was declared, not just what the screen glanced at
    verified_by: human
    met: true
    evidence: "Zoomed screenshot confirms Pide $150.000 / Tiene $360.050; hand-checked against the screen's own real spending figure ($139.950 already spent this month): 500.000 declared − 139.950 spent = 360.050, exact"
  - criterion: dev data left clean after the manual pass
    verified_by: human
    met: true
    evidence: "Test fund deleted via the UI, confirmed by toast, then confirmed absent after a full page reload (server round-trip, not client cache)"
status: complete
---

## Summary

CHARTER §6's manual browser check is done, against the real (not mocked)
dev stack. The new opening-balance field works end to end — typed with
thousand-separator formatting, submitted, and correctly folded into the
current month's figure alongside real pre-existing spending in that
category. No defect found. Feature 019 is ready to be marked done.

## Two follow-ups surfaced during CP7/CP8, explicitly out of this feature's scope

Neither blocks this feature; both are worth their own future ticket:

1. **`CreateFundForm` (frontend/app/(app)/funds/create-form.tsx) crosses the
   CRAP threshold (34.01)** — pre-existing complexity (rule-conditional
   fields, preview logic, warnings) this feature's one new unconditional
   field merely brushed against by touching a line inside it. CP7 proposed
   (not applied) extracting a `RuleFieldset` + `RuleSpecificFields` pair.
2. **8 unit tests in `backend/tests/services/test_funds.py` /
   `test_funds.py` (mcp) call `set_fund(..., balance=...)` without pinning
   `today=`** — they pass today only because their fixtures' `start_month`
   is still in the future relative to the real sandbox clock (2026-08-21).
   They have a genuine, dated expiration: roughly November 2026 / January
   2027, when the sandbox clock crosses those fixtures' `start_month`, is
   when they'll start failing for real. Worth a small follow-up pinning
   `today=` on all 8, on its own ticket rather than expanding this feature's
   diff.

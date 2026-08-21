---
skill: refine
agent_id: main-session + one fresh review subagent
feature: thousand-separator-number-inputs
started: 2026-08-20T19:30
ended: 2026-08-20T19:35
checkpoint: 6
artifacts:
  - frontend/lib/money.ts
  - frontend/components/money-input.tsx
  - frontend/lib/money.test.ts
findings_summary: >
  Re-ran refine against the react-number-format migration (the prior CP6 pass
  reviewed hand-rolled code that no longer exists after ADR-0060). Scaled the
  review to the new surface's size (one fresh subagent covering all three
  lenses in one pass, rather than three parallel subagents, since the new
  code is ~40 lines of library configuration rather than a hand-rolled
  algorithm). The subagent independently re-ran the full suite (confirmed
  green before making any change) and the spec.md scenario traceability, then
  found one real, small gap: decimalSeparator was a hardcoded per-currency
  ternary living in money-input.tsx, even though ADR-0060 calls
  thousandsSeparatorFor "the single source of truth" for currency-locale
  formatting shared with formatCents — decimalSeparator wasn't actually
  sourced the same way. Fixed by adding decimalSeparatorFor to lib/money.ts,
  refactoring the shared Intl.NumberFormat.formatToParts lookup into one
  numberPartFor(locale, type) helper reused by both the group and decimal
  separator functions, with 2 new unit tests. Also independently confirmed
  (not trusted from the implement handoff) that MoneyInput's cents in/out
  contract is byte-identical to before this feature for all 10 consumers, and
  that the onValueChange source==="event" guard correctly matches
  react-number-format's actual SourceType, verified against the library's own
  types rather than assumed.
human_action_needed: no
recommended_next: crap-analyzer for Light Verify (re-run against the new implementation)
tracker_update: local (no-op driver)
exit_criteria:
  - criterion: fresh reviewer distinct from the implementer covered all three lenses
    verified_by: tool
    met: true
    evidence: one fresh Agent-tool subagent dispatch, distinct from main-session's implement pass, covering reuse+quality+efficiency
  - criterion: full suite independently re-run green before and after any change
    verified_by: tool
    met: true
    evidence: "subagent's own run — 617/617 (615 baseline + 2 new decimalSeparatorFor tests); main-session's independent re-run afterward — Test Files 60 passed (60), Tests 617 passed (617)"
  - criterion: spec_coverage still 8/8 bound
    verified_by: tool
    met: true
    evidence: "python3 acceptance/spec_coverage.py features/018-thousand-separator-number-inputs frontend — scenarios 8, bound 8, unbound 0"
  - criterion: lint/format/typecheck clean
    verified_by: tool
    met: true
    evidence: "pnpm lint — 4 pre-existing unrelated warnings; pnpm format:check — clean; npx tsc --noEmit — clean"
status: complete
---

## Summary

CP6 re-run against the final (library-based) implementation, proportionally
scoped to its much smaller surface. One real, small finding fixed
(decimalSeparator sourcing) — everything else confirmed clean. Independently
re-verified by main-session, not taken on the subagent's word alone.

---
slug: "2026-08-11-expired-session-reports-a-saved-movement"
title: "An expired session makes every write report success — including the ones that move money"
severity: medium
blocks_user: false
workaround: "log in again and re-read the movement; nothing was saved, so redo the edit"
status: investigating

source:
  kind: internal
  ref: "features/012-movement-corrections/handoffs/2026-08-11T0900-verify.md"

repro: |
  1. Sign in and leave the app open until the session cookie expires
     (or expire it by hand in the browser's storage).
  2. Open any movement, change its account or its amount, and save.
  3. Read the toast and the dialog.

expected: "The app says the write failed and keeps the dialog open, exactly as it does for any other refusal. Nothing may claim a balance moved when no balance moved."
actual: "`toast.success(\"Transacción actualizada\")` fires and the dialog closes. Nothing was written and no balance moved. A redirect to /login follows, but the Toaster lives above the router outlet in `app/providers.tsx`, so the false claim survives the navigation and is what the owner reads on the login screen."

feature_refs:
  - "features/012-movement-corrections"

investigation:
  match_mode: manual
  candidates_considered: 1
  root_cause: |
    `frontend/lib/api/client.ts:18-23` — the response *error* interceptor
    returns `undefined` on a 401 instead of throwing:

        if (err.response?.status === 401 && !url.startsWith("/auth")) {
          onUnauthorized?.()
          return undefined as unknown
        }

    Returning from an axios error interceptor RESOLVES the promise. Every
    caller therefore receives `undefined` as a successful result, and every
    TanStack mutation runs its `onSuccess`. The one throw below it — the
    `ApiError` wrap — is never reached for a 401.

    Pre-existing and app-wide: `client.ts` is untouched by the
    `movement-corrections` branch (`git diff --merge-base main` is empty for
    it), and every mutation in the app goes through this interceptor.

    Feature 012 is why it is being filed now rather than later: it is the
    first feature where the false success sits over a write that moves an
    account balance, not over a balance-safe edit. `transaction-edit-dialog`
    fires two writes behind one button; both resolve `undefined`, both are
    read as success.

  found_by: "CP7 Light Verify, feature 012 — the independent reviewer of `EditTransactionForm`, while working out why the total-failure path was uncovered. CRAP never ranked it: the branch is in a shared client module, outside the feature's diff."

gap_analysis:
  - category: inadequate_verification
    phase: verify
    finding: "No test in the frontend suite mocks a 401 on a mutation. The suite pins what the app does when a write is refused with a 4xx that throws, and never what it does when the session simply expired — so a resolve-instead-of-throw has been invisible to it since the interceptor was written."
    followup_kind: add_verification

followups:
  - category: inadequate_verification
    action: "Pin the behaviour with a red test before fixing: a mutation whose request 401s must reject, must not call toast.success, and must not close its dialog."
    status: open
---

# An expired session reports a saved movement — notes

Filed out of feature 012's CP7, deliberately **not** fixed inside it: the
defect predates the feature, lives in a module the branch never touched, and
belongs to every screen that writes. Folding it into 012 would hide an
app-wide bug inside one feature's history.

The redirect is not the fix and should not be mistaken for one. `client.clear()`
plus `router.replace("/login")` moves the owner off the screen; it does not stop
the promise from resolving, so the mutation's success path has already run by
the time the navigation starts.

Resume at Step 3 (Pin): write the red test above, confirm it fails on current
code, then make the 401 branch throw like every other status does — keeping the
`onUnauthorized?.()` call, which is what actually redirects.

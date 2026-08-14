---
slug: "2026-08-13-the-create-form-never-shows-the-refusal-the-server-gave-it"
title: "The create form's refusal message never reaches the screen, and its Crear button stays enabled"
severity: medium
blocks_user: false
workaround: "press Crear anyway — the refusal arrives as a toast, in English"
status: closed

source:
  kind: internal
  ref: "found in Chrome while driving fix 2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget (CHARTER §6)"

repro: |
  Sandbox at localhost:3000, `just dev-local`, on 2026-08-13.

  1. Metas → Nueva meta.
  2. Nombre `VERIFY techo`, Cuánto `1000000`, Ya tenía guardado `2000000`,
     Cuándo `December 2026`.
  3. Wait. Then change Cuánto to `1200000` and wait again.

expected: |
  `create-form.tsx` since commit eeadec1:

      const refused = preview.isError
      {refused && (<p role="alert" …>Con esos números no se puede crear la meta.</p>)}
      <Button type="submit" disabled={body === null || pending || refused}>

  So: the red line appears and `Crear` goes disabled.
actual: |
  Neither happens, ever. Sixteen seconds after the last keystroke, with the
  server having refused SEVEN times:

    read_network_requests, urlPattern "preview" → 7 POSTs, statusCode 422
    document.querySelectorAll('[role="alert"]')  → []
    button[type=submit].disabled                 → false

  Pressing `Crear` submits, and the refusal arrives as a toast reading
  `a meta cannot already hold more than it costs` — the server's English
  string, which is the project-wide language hole already filed.

  Ruled out by inspection rather than assumed:
    - the container IS serving the code — `docker exec quaestor-frontend-1
      grep -n refused '/app/app/(app)/metas/create-form.tsx'` finds all three
      lines (92, 101, 111).
    - the query key DOES separate the two questions — `whatThePreviewReads`
      carries `stated_opening`, so the answer is not served from an earlier
      success's cache.
    - the client DOES throw — `http.interceptors.response` raises `ApiError`
      on every non-2xx, and the same helper's throw is what makes the create
      POST's toast appear.
    - retries are not hiding it — `providers.tsx` sets `retry: 1`, and the
      observation stands 16 s later.

  ROOT CAUSE, read from the live query cache rather than guessed. A temporary
  `window.__qc = client` probe in `providers.tsx` (reverted) showed the query
  for the completed body:

      target_month "2026-12"   status=pending   fetchStatus=PAUSED   observers=1
      failureCount undefined   errorUpdateCount 0   dataUpdateCount 0

  The 422 arrives, `retry: 1` schedules a second attempt, and the retryer
  **pauses** it — `networkMode` defaults to `'online'`, so a scheduled retry
  waits on the online manager. It never resumes. The query therefore never
  reaches `error`, `preview.isError` stays false, and the component has neither
  data nor an error to render. `q.fetch()` on it hangs.

  So the message was not swallowed by the component. It was never given
  anything to swallow.

  ALSO SEEN, and NOT reproduced: one preview POST returned 500 rather than 422
  on a body typed mid-keystroke. Seven boundary bodies driven straight at
  `metas.preview_meta` — a one-centavo amount with a 3.000.000 opening, a zero
  amount, an empty / malformed / month-13 target, a negative opening — all
  answer 422 cleanly. The most likely explanation is the Next proxy answering
  500 while the API container was restarting, which it had been minutes
  earlier. Recorded as unexplained rather than claimed as a defect.

  ALSO SEEN, cosmetic: the form fires a preview for every partial year the
  owner types — `0002-12`, `0020-12`, `0202-12` before `2026-12`. Three wasted
  round-trips, each a 422, per meta created. It is what made the network log
  confusing. Not fixed here; it is a debouncing question, not a correctness one.

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1

fix_commits:
  - cf2b51b

harden_results:
  mutation_score: "n/a — frontend only; the bug-line gate stands in its place"
  arch_check: "n/a — no backend module changed"
  bug_line_mutation_confirmed: true
  bug_line_evidence: |
    `worthAskingAgain` reverted to its old behaviour (`return failureCount < 1`,
    which is what `retry: 1` meant) → the metas suite goes to 1 failed / 33
    passed, and the one that fails is the refusal test. Restored → 34 passed.

    The browser is the other half, and it is the half that matters: before,
    seven 422s and `[role="alert"]` empty with the button enabled; after,
    `alerts: ["Con esos números no se puede crear la meta."]` and
    `submitDisabled: true`.

gap_analysis:
  - feature: "features/009-named-goals"
    category: inadequate_verification
    finding: |
      The test that stood in for the browser rejected with `new Error(...)`.
      The client never throws that — `http.interceptors.response` throws
      `ApiError`, which carries the status. So the test exercised a shape the
      app cannot produce, and the retry policy that broke the feature could not
      be reached from it.

      Worse, `renderPage` built its QueryClient with `retry: false` while the
      app shipped `retry: 1`. The one setting that caused the defect was the
      one the test replaced.
    closed_by: |
      The metas page test now builds its client with the app's own
      `worthAskingAgain`, and rejects with a real `ApiError(422, …)`. Reverting
      the predicate turns it red.

followups: []
---

# The create form never shows the refusal the server gave it

## What makes this worth its own artifact

The message was added on 2026-08-13 by fix
`2026-08-13-a-stated-opening-above-the-amount-mints-money`, and that fix's
closure handoff recorded it as **not covered by the browser** with a reason
that turns out to be false:

> "the frontend container does not bind-mount its source
> (docker-compose.dev.yml mounts `./backend/src` only, ADR-0033), so the create
> form's new refusal message is not in the running app."

`docker-compose.dev.yml` mounts only the backend, which is true, but the
**base** `docker-compose.yml` already mounts `./frontend/app`,
`./frontend/components`, `./frontend/lib` and `./frontend/ui`. Confirmed by
`docker inspect quaestor-frontend-1`. The frontend hot-reloads and always did.

So the one exit criterion that would have caught this was waived for a reason
that did not exist, and the vitest test that stands in its place cannot catch
it: it mocks `previewMeta.mockRejectedValue(...)` directly. That proves the
component renders the message **when the query errors**. It does not prove the
query ever errors.

## The shape of the hole

```
the server refuses                  →  422, seven times                      ✓
the client turns it into an error   →  ApiError, same helper the toast uses  ✓
the component renders on isError    →  proven by vitest                      ✓
the screen shows it                 →  never                                 ✗
```

Three of the four links were proven and the chain still did not carry, because
there was a fifth nobody had drawn: **react-query never delivered the error.**
`retry: 1` scheduled a second attempt, `networkMode: 'online'` paused it, and
the query sat at `pending / paused` forever. No data, no error, nothing to
render.

## The fix, and why it is right beyond this bug

A 4xx is the server's **answer**. Asking again returns the same refusal a
second later, and until it lands the screen has nothing to show. Retrying it
buys nothing and costs a round-trip.

```ts
retry: (failureCount, error) =>
  error instanceof ApiError && error.status >= 400 && error.status < 500 &&
  ![408, 429].includes(error.status)
    ? false
    : failureCount < 1
```

408 and 429 stay retried — a timeout and a rate limit *do* get better on their
own. This matches TanStack's own position: the library is deliberately
status-blind (it takes any promise and cannot know an HTTP status exists), and
the maintainer's guidance is that 4xx is handled locally while 5xx is
infrastructure. Verified against the v5 docs and tkdodo.eu rather than from
memory.

## Money

None. The server refuses correctly, so nothing is created and no figure moves.
What was lost is the owner being told *before* he presses the button, in
Spanish, which is what the message existed for.

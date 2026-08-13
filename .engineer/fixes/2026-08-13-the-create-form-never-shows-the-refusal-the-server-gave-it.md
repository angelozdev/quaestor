---
slug: "2026-08-13-the-create-form-never-shows-the-refusal-the-server-gave-it"
title: "The create form's refusal message never reaches the screen, and its Crear button stays enabled"
severity: medium
blocks_user: false
workaround: "press Crear anyway — the refusal arrives as a toast, in English"
status: investigating

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

  Not yet explained: why `preview.isError` stays false when the request the
  component made came back 422. That is the whole of what is left to find.

  ALSO SEEN, filed here rather than lost: one preview POST returned **500**,
  not 422, on a body typed mid-keystroke. A server error where a refusal
  belongs is its own defect and needs its own repro.

feature_refs:
  - "features/009-named-goals"

investigation:
  match_mode: auto
  candidates_considered: 1

fix_commits: []

harden_results:
  mutation_score: null
  arch_check: null
  bug_line_mutation_confirmed: false

gap_analysis: []

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
the server refuses          →  422, seven times      ✓
the client turns it into an error   →  ApiError, same helper the toast uses  ✓
the component renders on isError    →  proven by vitest                      ✓
the screen shows it                 →  never                                 ✗
```

Three of the four links are proven and the chain still does not carry. The
break is between `useQuery` receiving the rejection and `preview.isError`.

## Money

None. The server refuses correctly, so nothing is created and no figure moves.
What is lost is the owner being told *before* he presses the button, in
Spanish, which is what the message existed for.

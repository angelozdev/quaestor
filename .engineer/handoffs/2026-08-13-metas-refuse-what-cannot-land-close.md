---
skill: fix (close)
agent_id: main-session
feature: 009-named-goals
fix_slugs:
  - 2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in
  - 2026-08-13-a-stated-opening-above-the-amount-mints-money
  - 2026-08-13-a-meta-gives-back-money-no-month-ever-gave-it
started: 2026-08-13T1800
ended: 2026-08-13T2330
checkpoint: null
branch: fix/metas-refuse-what-cannot-land
artifacts:
  - .engineer/fixes/2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in.md
  - .engineer/fixes/2026-08-13-a-stated-opening-above-the-amount-mints-money.md
  - .engineer/fixes/2026-08-13-a-meta-gives-back-money-no-month-ever-gave-it.md
  - features/009-named-goals/acs.md
  - features/009-named-goals/spec.md
  - backend/src/quaestor/services/metas.py
  - acceptance/handlers/named_goals.py
  - frontend/app/(app)/metas/create-form.tsx
  - frontend/app/(app)/metas/page.test.tsx
findings_summary: "TWO DEFECTS WERE ASKED FOR AND FIVE WERE CLOSED, ALL ONE SENTENCE: the app took money it could not put anywhere, and gave back money nobody had put in. (1) A contribution into a month before the meta was opened was accepted and read by nothing. (2) A stated opening above the amount was accepted. (3) THE CEILING IN (2) DID NOT CLOSE THE MINT AND THE COMMIT SAID IT DID — an independent verifier found the same money one PATCH or one cancel away, because `released` was bounded by what the meta HOLDS and a stated opening is in `holds` without a month behind it. (4) A SECOND VERIFIER FOUND THE LEDGER MEASURED THE WRONG QUANTITY: nothing took the purchase out of it, so AC-8's 'keep it with another amount' handed back what was already in the thing — five instalments of 1.000.000, a 5.000.000 phone, then 4.000.000 back and a net cost of 1.000.000. AC-39 names it exactly. (5) THE SAME SEAM READ BACKWARDS LOST MONEY: `fold` took the walk's `released` OR the cancellation's, never both, so a meta lowered and cancelled in one month gave back 1,00 of the 4.800.000 the months had put in. THREE ROUNDS, EACH ON A GREEN SUITE, EACH FINDING THE PREVIOUS ROUND'S FIX INCOMPLETE. Mutation could not see any of them — the code and the tests agreed. What found each was an agent told to BREAK the fix, and twice the decisive evidence was a hand-applied mutant on the line the fix had just written. THE OWNER MADE FOUR PRODUCT DECISIONS: refuse a contribution into a month the meta never ran in; refuse a stated opening above the amount; refuse one below zero; and after a purchase, give back what the thing did not eat and nothing more. NINE SCENARIOS ADDED (152 in the feature, from 143), each proven red without the code. MUTATION 188/180/8 = 95.7%, all eight read and judged equivalent."
human_action_needed: yes
human_action_kind: merge
recommended_next: "The owner merges `fix/metas-refuse-what-cannot-land` into `main` (CHARTER §7). Then feature 015 `fund-belongs-to-its-charge`, whose branch is 12 commits behind."
tracker_update: "local — 009 stays done; three fixes closed."
exit_criteria:
  - criterion: "every regression was red on the code as it stood, and is green now"
    verified_by: tool
    met: true
    evidence: "Nine scenarios in three rounds. Round 1: `2 failed, 141 passed` (the two refusals). Round 2, metas.py reverted to HEAD: `4 failed, 143 passed` (the give-backs, the floor, the form). Round 3: each of the four remaining lines mutated by hand and shown to fall to exactly its own scenario. All green after: 152 passed."
  - criterion: "the new refusals do not over-reach"
    verified_by: tool
    met: true
    evidence: "An independent verifier ran an 852-case matrix against the commit and its parent: 0 previously-refused inputs now accepted, and the 96 newly-refused are exactly the intended two classes. Boundary scenarios ship beside each refusal — a past month the meta DID run in still takes a contribution, a stated opening equal to the amount is allowed, and one of exactly zero is allowed, which is what the frontend sends."
  - criterion: "the whole project is green"
    verified_by: tool
    met: true
    evidence: "backend 1190 passed; acceptance 660 passed; vitest 57 files / 551 tests passed; `cd backend && uv run lint-imports` → Contracts: 2 kept, 0 broken."
  - criterion: "verification independence (Principle 7)"
    verified_by: judgment
    met: true
    evidence: "Two fresh verifiers, `cp7-verifier-refusals` and `cp7-verifier-giveback`, each distinct from the implementer (`main-session`) and from each other. Each was told to break the fix, not confirm it. Each found the previous round incomplete on a green suite."
  - criterion: "mutation ran on the code that ships, in isolation, every stage green-gated"
    verified_by: tool
    met: true
    evidence: "`backend/scripts/mutate.py --target backend/src/quaestor/services/metas.py` in a detached worktree at f67fa29, four stages, each proven green on untouched source first. 188 mutants, 180 killed, 8 alive, 95.7%, 29.1 min."
  - criterion: "every survivor was read and judged, not counted"
    verified_by: judgment
    met: true
    evidence: "Eight, all equivalent with reasons: four `frozen=True` on dataclasses built once and only read; two on `funded`'s default, taken only by the pre-start `_Month(ask=0, holds=0)` where `holds` clamps every reader; two on the `if amount else 0` arm no reachable state enters. Separately, each of the four load-bearing lines of the ledger was mutated by hand and killed by exactly one scenario — `- spent`, `- released`, the cancel term, and `stated_opening < 0`."
  - criterion: "the fix is driven in a browser (CHARTER §6)"
    verified_by: human
    met: true
    evidence: |
      Chrome MCP against the sandbox on 2026-08-13. Baseline `Disponible
      $ -13.454.780`.

      THE REFUSAL. A meta of 1.000.000 stating it already held 2.000.000 is
      refused on submit: `a meta cannot already hold more than it costs`.

      THE GIVE-BACK. The same meta stating 600.000 creates and reads
      `pidió $ 80.000 · lleva $ 680.000` — the 600.000 stated cost the month
      nothing (AC-34), and `Disponible` moved by exactly the instalment to
      $ -13.534.780. Cancelling it reads:
        Meta · VERIFY declara (la cancelaste)          − $ 80.000
        Devuelto por VERIFY declara (la cancelaste)      $ -80.000
        Disponible                                       $ -13.454.780
      Back to the baseline to the peso. It gave back the 80.000 August put in
      and not the 680.000 it held. On the code as it stood the screen would
      have read $ -12.854.780 — 600.000 out of nothing.

      NOT COVERED BY THE BROWSER, and said rather than glossed: the frontend
      container does not bind-mount its source (docker-compose.dev.yml mounts
      `./backend/src` only, ADR-0033), so the create form's new refusal message
      is not in the running app. It is covered by vitest instead — 551 tests,
      including the new one bound to the untagged scenario. The refusal itself
      reaches the screen as a toast, in English, which is the project-wide
      language hole already filed.
status: complete
---

# fix — close (three, one seam)

## La frase

**La app tomaba plata que no podía poner en ningún lado, y devolvía plata que
nadie había puesto.** Cinco síntomas, un solo origen: nunca existió la cuenta de
*lo que los meses realmente pusieron*. `holds` no es esa cuenta — lleva dentro
lo que el dueño declaró tener, que no salió de ningún mes, y se queda quieto
después de una compra, cuando la plata ya está en la cosa.

## Lo que costó encontrarlo

| ronda | qué encontró |
|---|---|
| techo al crear | cerró la puerta de entrada y **afirmó** haber cerrado el hueco |
| verificador 1 | el mismo invento, a un `PATCH` o a una cancelación de distancia |
| verificador 2 | la cuenta era la idea correcta contra la cifra equivocada — la compra nunca salía de ella — y la devolución del mismo mes se estaba perdiendo |

**Ninguna suite vio nada, en ninguna ronda.** La mutación tampoco: el código y
las pruebas estaban de acuerdo. Lo que encontró cada uno fue un agente al que se
le pidió *romper* el arreglo, no confirmarlo — y dos veces la evidencia
decisiva fue un mutante aplicado a mano sobre la línea que el arreglo acababa de
escribir.

## Lo que queda

- El dueño mergea la rama a `main` (CHARTER §7). Todos los criterios de
  salida están cumplidos, el navegador incluido.
- Dos cabos menores, con artefacto propio: restaurar una meta cancelada revive
  un aporte que prometía olvidar, y un descuadre de ±1 centavo en metas en
  dólares por convertir mes a mes y topar una sola vez.

---
skill: fix (close)
agent_id: main-session
feature: 009-named-goals
fix_slug: 2026-08-13-a-meta-swallows-what-it-cannot-take
started: 2026-08-13T0900
ended: 2026-08-13T1730
checkpoint: null
branch: fix/meta-keeps-only-what-fits
artifacts:
  - .engineer/fixes/2026-08-13-a-meta-swallows-what-it-cannot-take.md
  - .engineer/fixes/2026-08-13-a-contribution-into-a-month-the-meta-never-ran-in.md
  - .engineer/fixes/2026-08-13-a-stated-opening-above-the-amount-mints-money.md
  - .engineer/consolidation.md
  - CHARTER.md
  - features/009-named-goals/spec.md
  - backend/src/quaestor/services/metas.py
  - backend/src/quaestor/services/funds.py
  - backend/src/quaestor/domain/rules.py
  - backend/tests/domain/test_fund_rules.py
  - acceptance/handlers/named_goals.py
findings_summary: "TWO MONEY DEFECTS, ONE SENTENCE: nothing tied what a meta actually took of a hand contribution to what the month was charged for it. (1) `fold` read the stored contribution row while `_month_of` trimmed it, so an act that shrank the room after the write — lowering the amount, or dating the purchase before the month the row sits in — left the month charged for money that reached no meta and was given back by nothing (`released` stays 0). 2.000.000 of a 3.200.000 contribution. (2) FOUND WHILE VERIFYING (1), AND BIGGER: `_meta_uncovered` measured a linked purchase against `opening + ask` — the fund's shape, which has no hand contributions in it — so a purchase the meta had already covered by hand came back as a gap and the month paid twice. Two metas holding 8.000.000 each against the same 8.000.000 phone left the month 200.000 and -8.333.333. AC-43 decides it: 'only what the meta cannot cover costs the month'. THE INDEPENDENT CP7 VERIFIER IS WHAT FOUND IT, and it found two more the fix does not close, each now filed with the owner's decision already made: a contribution into a month the meta never ran in is accepted and reaches nothing (refuse it), and a stated opening above the amount hands the month 3.000.000 that never entered it (refuse it). SIX SCENARIOS ADDED, all red before and green after — two under AC-14, three under AC-13/AC-43, one in dollars. THE DOLLAR ONE EXISTS BECAUSE THE VERIFIER MUTATED THE LINE THE FIX HAD JUST WRITTEN: hard-coding \"COP\" where the meta's currency belonged reported US$800 as $800 and passed 1.325 green tests, because no test in the project had ever contributed to a meta in another currency. CHARTER §6 was amended the same day — a figure the app converts is tested in another currency whether or not anyone writes it — and C24 records the sweep that is left. MUTATION 169/162/7 = 95.9%; all seven read and judged equivalent, and AN EIGHTH WAS NOT: `_Month.opening` lost its last reader when `_meta_uncovered` moved to `holds`, so it was written five times and read none. Deleted rather than pinned. The survivor feature 009's own CP8 left open in August — closing a meta as of a month before it existed — died this round against the longer ladder."
human_action_needed: yes
human_action_kind: merge
recommended_next: "The owner merges `fix/meta-keeps-only-what-fits` into `main` (CHARTER §7). Then `/engineer.fix` picks up the two filed neighbours, whose product decisions are already recorded."
tracker_update: "local — 009 stays done; fix 2026-08-13-a-meta-swallows-what-it-cannot-take closed."
exit_criteria:
  - criterion: "the regression spec was red on the code as it stood, and is green now"
    verified_by: tool
    met: true
    evidence: "Six scenarios. `./run-acceptance-tests.sh features/009-named-goals` reported `2 failed, 133 passed` for the AC-14 pair and `3 failed, 135 passed` for the AC-13/AC-43 trio, each failing on its own figure. The dollar one failed `contributed 80000, expected 320000000` under a hand-applied \"COP\". All six green after: 139 passed."
  - criterion: "each new assertion can fail on its own, not only the first one pytest reaches"
    verified_by: tool
    met: true
    evidence: "The `money available` lines of both AC-14 scenarios were re-run with the `contributed` assertion removed so they could be reached: `120000000, expected 320000000` and `180000000, expected 500000000`. The independent CP7 verifier repeated the exercise at the services layer and reported two of three assertions red in each."
  - criterion: "the whole project is green"
    verified_by: tool
    met: true
    evidence: "backend 1190 passed; acceptance 647 passed; vitest 57 files / 550 tests passed; `cd backend && uv run lint-imports` → Contracts: 2 kept, 0 broken."
  - criterion: "verification independence (Principle 7)"
    verified_by: judgment
    met: true
    evidence: "CP6 refine ran as `cp6-refiner-independent` and CP7 verify as `cp7-verifier-independent`, both fresh agents distinct from the implementer (`main-session`) and from each other. CP7 is what found the second defect; the implementer's own suites were green on it."
  - criterion: "the bug lines are pinned, not the fix"
    verified_by: tool
    met: true
    evidence: "For defect 1 the CP7 verifier re-inserted the old `fold` line verbatim on the fixed tree: 2 failed, 133 passed — only the two new scenarios, then restored and proved the file byte-identical. For defect 2 the three new scenarios were red on the unmodified code before `_meta_uncovered` was touched. Both spec sets stay red against their own bug and against nothing else."
  - criterion: "mutation ran on the code that ships, in isolation, every stage green-gated"
    verified_by: tool
    met: true
    evidence: "`backend/scripts/mutate.py --target backend/src/quaestor/services/metas.py` in a detached worktree at 779823c, four stages, each proven green on untouched source first. 169 mutants, 162 killed, 7 alive, 95.9%, 23.5 min. The gate earned its keep twice: it refused to score a run whose fourth stage was red."
  - criterion: "every survivor was read and judged, not counted"
    verified_by: judgment
    met: true
    evidence: "Seven equivalent with reasons in the artifact. The eighth, from the first sweep, was not equivalent and was closed by deleting `_Month.opening` rather than by writing a test for a value nothing reads."
  - criterion: "the fix is driven in a browser (CHARTER §6)"
    verified_by: human
    met: true
    evidence: |
      Chrome MCP against the sandbox (SQLite .dev-data/, TRM 3142) on 2026-08-13,
      on the meta the QA sweep had left behind as the reproduction.

      DEFECT ONE. `QA Portatil` wants US$400, holds US$400, asks US$20 — so it
      took US$80 of a US$120 contribution. Reportes now reads
      `Puesto a mano en una meta − $ 251.360`, which is US$80 × 3142. It read
      $377.040 the day before, the whole US$120. The breakdown adds up to the
      peso: 3.000.013 − 89.000 − 150.000 − 5.000.000 − 62.840 − 251.360 −
      10.901.593 = −13.454.780, the figure on screen. The month charges
      62.840 + 251.360 = US$100, exactly what the meta's holdings grew by.

      DEFECT TWO. A US$400 expense on Ahorros USD, linked to `QA Portatil`,
      recorded through the transaction dialog. `Sin fondo que lo cubra` stayed
      at $10.901.593 and the money available stayed at −13.454.780 — the
      purchase cost the month nothing beyond what the meta had already set
      aside, which is AC-43 verbatim. Under the old code it would have added
      max(400 − 300 − 20, 0) = US$80 = $251.360 and the month would have read
      −13.706.140. The purchase itself is visible as
      `Por categoría · Tecnología $ 1.256.800`.

      It also covers the currency: both figures are a dollar meta read in
      pesos, which is what the amended §6 asks for.
status: complete
---

# fix — close

## Los dos defectos, en una frase

Nada ataba **lo que la meta realmente tomó** de un aporte a mano con **lo que
el mes te cobró por él**. `_month_of` decidía qué cabía; otros dos sitios
volvían a la fila guardada o a una fórmula anterior a los aportes.

## Lo que encontró el verificador y el arreglo no había visto

El segundo defecto mueve más plata que el primero y no lo buscaba nadie:
`_meta_uncovered` medía una compra contra `opening + ask`, que es la forma del
fondo — y un fondo no recibe aportes a mano. Dos metas con 8.000.000 cada una
contra el mismo celular de 8.000.000 dejaban el mes en 200.000 y en −8.333.333.

## Lo que la mutación enseñó que no era un puntaje

Un sobreviviente no era equivalente: `_Month.opening` se escribía cinco veces y
no lo leía nadie desde que `_meta_uncovered` pasó a pedir `holds`. **Se borró en
vez de escribirle una prueba**, que es lo que hace falta cuando el mutante
sobrevive porque el valor no llega a ninguna parte.

Y una lección de infraestructura: el suite completo **no es hermético**.
`tests/test_scheduler.py::TestRunOnce::test_run_once_success` corre el job
diario real contra `backend/quaestor.db` en disco, así que en un worktree
recién creado falla con `no such table: recurring_item`. La puerta de la
mutación lo leyó bien: un peldaño rojo hace que todo mutante cuente como
muerto.

## Lo que queda

- El dueño mergea `fix/meta-keeps-only-what-fits` a `main` (CHARTER §7).
  Todos los criterios de salida están cumplidos, el navegador incluido.
- Los dos vecinos filtrados, con la decisión de producto ya tomada.
- En el sandbox queda el movimiento `VERIFY doble cobro` (US$400 sobre
  Ahorros USD, ligado a `QA Portatil`), que es la reproducción del segundo
  defecto. Se deja como se dejaron las demás filas `VERIFY`.

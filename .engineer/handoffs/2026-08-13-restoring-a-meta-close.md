---
skill: fix (close)
agent_id: main-session
feature: 009-named-goals
fix_slugs:
  - 2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget
started: 2026-08-13T1745
ended: 2026-08-13T1935
checkpoint: null
branch: fix/restore-gives-back-what-it-already-gave-back
artifacts:
  - .engineer/fixes/2026-08-13-restoring-a-meta-revives-a-contribution-it-promised-to-forget.md
  - .engineer/fixes/2026-08-13-the-create-form-never-shows-the-refusal-the-server-gave-it.md
  - docs/adr/0055-restaurar-una-meta-abre-una-vida-nueva-y-los-aportes-de-la-anterior-quedan-marcados-como-devueltos.md
  - backend/src/quaestor/migrations/versions/0018_a_restored_meta_leaves_its_old_contributions_given_back.py
  - backend/src/quaestor/services/metas.py
  - backend/src/quaestor/services/month_aggregate.py
  - backend/src/quaestor/domain/models.py
  - backend/tests/services/test_metas.py
  - features/009-named-goals/acs.md
  - features/009-named-goals/spec.md
  - acceptance/handlers/named_goals.py
  - frontend/app/(app)/metas/meta-actions.tsx
  - frontend/app/(app)/metas/page.test.tsx
  - .engineer/consolidation.md
findings_summary: "THE FIX WAS BROKEN TWICE BY AN INDEPENDENT VERIFIER, ON A GREEN SUITE, BOTH TIMES LOSING MONEY — and both regressions were introduced by the fix itself, not pre-existing. (1) A contribution dated AFTER the cancellation month was stamped as given back although that month's give-back provably never included it: the fold sums rows dated at or before the cancellation, so a September contribution on a meta cancelled in August took the meta from 2.785.714,29 to 1.785.714,29. A MILLION NOBODY RETURNED, LOST. (2) Restoring in a month BEHIND the cancellation cleared `cancelled_month`, so no month gave anything back, while the stamp took the contribution out of the months that still ran — July fell from 1.833.333,34 to 833.333,34. Closed by bounding the stamp (`_given_back_by`) and by refusing the restore. BOTH WERE REPRODUCED BY THE IMPLEMENTER BEFORE BEING ACCEPTED. THE ORIGINAL DEFECT WAS THE MIRROR PAIR THE SAME SEAM ALWAYS MAKES: restoring re-read a contribution the cancellation had already handed back (a meta holding 2.000.000 when August put in 1.000.000), and left one made in an earlier month listed and read by nothing. `meta_contribution` gains `returned_month`, nullable, written by the RESTORE and never by the cancellation — stamping at cancellation would rewrite the very month whose give-back included it, breaking AC-27 to fix AC-29. ADR-0055 supersedes one clause of ADR-0046; migration 0018 is additive with no backfill. A GUARD SHIPPED WITH NO TEST AT ALL: `if row.returned_month is None` protects an earlier life's stamp, and removing it left all 1.190 backend tests green. THE VERIFIER ALSO PROVED THREE MUTANTS SURVIVED THE FIRST COMMIT — stamping `today`, stamping `1970-01`, and overwriting — because the acceptance handler asserted only that a stamp EXISTS, not which month it carries. A SEPARATE DEFECT WAS FOUND IN THE BROWSER AND FILED: the create form never shows the refusal it was given and never disables `Crear`, with the server answering 422 seven times — hidden until now because THIS MORNING'S CLOSURE HANDOFF WAIVED THE BROWSER CRITERION ON A FALSE CLAIM (the frontend container does bind-mount its source; the mounts are in the BASE compose file, not the dev override). Mutation 197/189/8 = 95.9%, all eight read and judged equivalent against the code rather than carried over from the earlier sweep."
human_action_needed: yes
human_action_kind: merge
recommended_next: "The owner merges `fix/restore-gives-back-what-it-already-gave-back` into `main` (CHARTER §7). Then pick between feature 011 `monthly-report` (in-progress at CP1.5, needs nobody) and feature 015 `fund-belongs-to-its-charge` (ready, needs the owner present for the migration rehearsal)."
tracker_update: "local — 009 stays done; one fix closed, one filed."
exit_criteria:
  - criterion: "every regression was red on the code as it stood, and is green now"
    verified_by: tool
    met: true
    evidence: |
      Two rounds. Round 1, the pin: `2 failed, 153 passed` — the restored meta
      holding 200000000 where 100000000 was required, and the missing column.
      Round 2, the verifier's two findings, each reproduced on the implementer's
      own script before being accepted and each pinned by a service test that
      goes red against its own line alone (1 failed, 1 passed, twice). A guard
      scenario shipped with the pin and was green by design: a meta never
      cancelled goes on counting its contributions.
  - criterion: "the new refusals and the new filter do not over-reach"
    verified_by: judgment
    met: true
    evidence: |
      The verifier's failed-attack list is the evidence: a meta never cancelled,
      a meta cancelled and never restored (its month still reads its charge, its
      contribution AND its give-back exactly as before the fix — AC-27 held), two
      metas where only one is restored, `_room_left` after a restore offering
      exactly 4.000.000 of a 99.000.000 ask, and `remove_contribution` on a
      stamped row moving `free` by 0,00. Forty-plus month readings with the
      money-available identity matching exactly.
  - criterion: "the whole project is green"
    verified_by: tool
    met: true
    evidence: "backend 1194 passed; acceptance 663 passed (exit 0, spec-coverage 0 unbound); vitest 57 files / 553 tests passed; `cd backend && uv run lint-imports` → Contracts: 2 kept, 0 broken; ruff clean; `pnpm exec tsc --noEmit` clean."
  - criterion: "verification independence (Principle 7)"
    verified_by: judgment
    met: true
    evidence: "`cp7-verifier-restore`, distinct from the implementer (`main-session`), told to break the fix rather than confirm it. It returned BROKEN with two money findings, both regressions the implementer had introduced, each with a runnable reproduction printing the wrong figure beside the right one. It worked in its own worktrees and left the main checkout untouched."
  - criterion: "mutation ran on the code that ships, in isolation, every stage green-gated"
    verified_by: tool
    met: true
    evidence: "`backend/scripts/mutate.py --target backend/src/quaestor/services/metas.py` in a detached worktree at e9d7cc0 — the FINAL commit, after an earlier sweep against d70b3ad was killed for describing code that no longer existed. Three stages, each proven green on untouched source first. 197 mutants, 189 killed, 8 alive, 95.9%."
  - criterion: "every survivor was read and judged, not counted"
    verified_by: judgment
    met: true
    evidence: |
      Eight, each adjudicated against the source rather than carried over from
      the morning's sweep of the same module: four `frozen=True` on dataclasses
      built once and only read; two on `funded`'s default, reachable only through
      the pre-start `_Month(ask=0, holds=0)` where `holds=0` clamps the single
      reader that touches it; two on `progress = … if amount else 0`, whose else
      arm no state reaches because all three writers pass `_validate_spec`. Each
      claim was checked by grep, not asserted. None of the fix's own lines
      survived.
  - criterion: "the bug-line gate holds on every load-bearing line"
    verified_by: tool
    met: true
    evidence: |
      Five, each mutated by hand: the stamping loop, the aggregate's
      `returned_month IS NULL` filter, the second-cancellation guard, the
      `row.year_month <= cancelled_month` bound, and the backward-restore
      refusal. Each killed by exactly its own test. The guard's mutant left the
      ENTIRE 1.190-test backend suite green before its test existed, which is
      why the test exists.
  - criterion: "the fix is driven in a browser (CHARTER §6)"
    verified_by: human
    met: true
    evidence: |
      Chrome MCP against the sandbox on 2026-08-13, after `alembic upgrade head`
      inside `quaestor-api-1` (the `.dev-data` sqlite file copied to
      `quaestor.pre-0018.db` first).

      A meta `VERIFY restaura` of $5.000.000 for December reads
      `Te pediría $ 1.000.000 al mes.` and creates at
      `Lleva $ 1.000.000 · pide $ 1.000.000 · 20% del camino`.
      Ponerle plata $1.000.000 → `Lleva $ 2.000.000 · 40%`.
      Cancelar, then Traer de vuelta → **`Lleva $ 1.000.000 · 20% del camino`**.
      On the code as it stood it would have read $ 2.000.000 · 40%.

      Ver aportes reads
      `Agosto 2026  ~~$ 1.000.000~~  Te lo devolvimos al cancelar la meta.`
      Quitar on that row left `Lleva $ 1.000.000 · 20%` unchanged — no figure
      moved, which is what ADR-0055 requires.

      THE FRONTEND HALF IS COVERED HERE, not deferred to vitest as this
      morning's handoff did: that handoff's reason was wrong and is corrected in
      place. The container bind-mounts `frontend/app|components|lib|ui` from the
      BASE compose file.
status: complete
---

# fix — close (restaurar una meta)

## La frase

**Cancelar devuelve lo que los meses pusieron; restaurar tiene que saber
exactamente qué se devolvió.** Ni más ni menos. El arreglo falló las dos
veces por el mismo lado: la primera dando por devuelto de menos, la segunda
dando por devuelto de más.

## Las tres rondas

| ronda | qué encontró |
|---|---|
| el defecto original | restaurar volvía a cobrar el aporte que la cancelación ya había devuelto (2.000.000 donde agosto puso 1.000.000), y dejaba huérfano el de un mes anterior |
| verificador, F1 | un aporte fechado **después** del mes de la cancelación se marcaba devuelto sin que ese mes lo hubiera devuelto — septiembre perdía 1.000.000 |
| verificador, F2 | restaurar **antes** del mes de la cancelación borraba el mes que devolvía, y julio perdía 1.000.000 |

Las dos del verificador son regresiones que introdujo el propio arreglo: el
commit padre daba las cifras correctas. Las reprodujo el implementador antes de
aceptarlas.

## Lo que ninguna suite podía ver

- El guardián `if row.returned_month is None` protege el sello de una vida
  anterior. **Sin él, las 1.190 pruebas seguían verdes.**
- El manejador de aceptación preguntaba si el aporte tenía sello, no **cuál**.
  Tres formas de sellarlo mal pasaban todo: el mes de hoy, `"1970-01"`, y pisar
  el anterior.

## Lo que se encontró de paso, y se archivó aparte

El handoff de la mañana dio por cumplido el criterio del navegador diciendo que
el contenedor del frontend no monta su código. **Es falso** — el
`docker-compose.yml` base monta `frontend/app`, `components`, `lib` y `ui`; solo
el override de dev es del backend. Correr la prueba costó diez minutos y destapó
un defecto real: el formulario de crear nunca muestra la negativa ni deshabilita
`Crear`, con el servidor devolviendo 422 siete veces.

Su prueba de vitest no podía verlo: simula el rechazo, así que prueba que el
componente pinta el mensaje **cuando la consulta falla**, no que la consulta
falle alguna vez.

## Lo que queda

- El dueño mergea la rama a `main` (CHARTER §7).
- `main` acumula commits sin subir.
- Un fix abierto nuevo: el del formulario de crear.

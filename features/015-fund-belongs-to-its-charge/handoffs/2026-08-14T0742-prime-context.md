---
skill: prime-context
agent_id: main-session
feature: 015-fund-belongs-to-its-charge
started: 2026-08-14T0730
ended: 2026-08-14T0742
checkpoint: null
artifacts: []
findings_summary: "Primed 015 two days after its discuss promoted it. THE FEATURE WAS FOUND, NOT WRITTEN: the owner asked to open a discuss for the per-charge fund, and the discuss had already happened on 2026-08-12 mid-CP5 of feature 014 — `feature.md` exists at `status: ready` on branch `fund-belongs-to-its-charge`, never merged, and the folder in `main` was an empty untracked leftover. THE BLOCKER THE DISCUSS NAMED IS CLEARED: it required 014 merged before implementation, and 014 shipped (afb05f3). The branch was 27 commits behind `main`, forked at 5aa164f mid-014, so `main` was merged in (06396d4) before loading any code — reading the pointers off the stale branch would have shown `funds.py` without 014's `FundCharge` breakdown, which is exactly what this feature displays. Clean merge, no conflicts: the branch's only commit adds files under `features/015-*`. LOADED: feature.md, the discuss handoff, CHARTER.md, manifest.yml, and every pointer — `services/funds.py` (`_settled_by_spending`, `_obligations`, `_charge_month_for`, `_ask_from_obligations`, `_refuse_a_second_fund`, `_crowded`, `_warning`), `services/month.py:91` (where `recurring_id` is already read), `domain/models.py` (`Fund` with `uq_fund_category`, `RecurringItem`, `RecurringOccurrence`), ADR-0043, ADR-0054, `recurring/page.tsx` (911 lines, where the mark goes), `funds/page.tsx` (440 lines, `FundCharges` renders 014's breakdown). CONFIRMED AGAINST THE RUNNING DATABASE, read-only: fund 1 on 🛡️ Auto Insurance is `from_recurring` since 2026-08 with no anchor, and the category holds exactly the two annual charges the feature.md quotes — Seguro del Carro 7.000.000 (2026-07-01, yearly) and SOAT carro 447.300 (2027-05-02, yearly). The owner's live complaint — wanting to save for the Seguro without the SOAT riding along — is the same one the discuss recorded. NOTHING NEW WAS ADDED to feature.md's pointers."
human_action_needed: no
recommended_next: "/engineer.discover-acs"
tracker_update: "none — no roadmap item matches; `fund-mixed-interval-categories` is legitimately shipped by 014 (the arithmetic worked; the warning lied), and `link-a-payment-to-the-charge-it-settled` stays planned and out of scope."
status: complete
---

# prime-context — 015 fund-belongs-to-its-charge

## Lo que hubo que arreglar antes de cargar nada

La rama salió de `5aa164f`, a mitad de la 014, y quedó 27 commits detrás de
`main`. Cargar los punteros de código desde ahí habría mostrado `funds.py` sin
el desglose que la 014 construyó — justo lo que esta feature va a mostrar. Se
mergeó `main` primero (`06396d4`), sin conflictos: el único commit de la rama
añade archivos nuevos bajo `features/015-*`.

## Cargado

`feature.md`, el handoff del discuss, `CHARTER.md`, `manifest.yml`, y los
punteros: `services/funds.py`, `services/month.py:91`, `domain/models.py`,
ADR-0043, ADR-0054, `recurring/page.tsx`, `funds/page.tsx`.

## Confirmado contra la base real, en solo lectura

```
fund 1 · 🛡️ Auto Insurance · from_recurring · start 2026-08 · sin anchor
  Seguro del Carro  7.000.000 COP  anual  desde 2026-07-01
  SOAT carro          447.300 COP  anual  desde 2027-05-02
```

Coincide con lo que la `feature.md` cita. El reclamo que el dueño trajo hoy
—querer apartar para el Seguro sin arrastrar el SOAT— es el mismo que el
discuss del 2026-08-12 ya había recogido.

## Sin cambios en los punteros

No se añadió ninguno a `feature.md`.

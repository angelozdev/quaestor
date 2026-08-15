---
slug: 015-fund-belongs-to-its-charge
checkpoint: 4
created: 2026-08-15
status: partial
steps:
  - id: fresh-backup
    description: "Take a fresh pg_dump of the production container before anything touches it"
    owner: human
    command: "just backup"
    evidence: "quaestor-local-2026-08-15.dump written to iCloud QuaestorBackups, 60K, by the owner on 2026-08-15."
    completed: true
    blocking_acs:
      - AC-6

  - id: measure-before
    description: "Record what the single existing fund asks today, read-only, so the after can be compared to it"
    owner: agent
    command: null
    evidence: "Read from production with the PRE-015 code (git worktree at 2722fd9), read-only: 🛡️ Auto Insurance asks 686.063,64 = SOAT carro 49.700,00 + Seguro del Carro 636.363,64. Whole month: income 18.098.101,00 · funds 5.098.513,44 · metas 2.750.000,00 · uncovered 4.620.964,24 · free 5.628.623,32; rates earning 21.063.726,00 · cost 8.816.343,13 · margin 12.247.382,87."
    completed: true
    blocking_acs:
      - AC-6

  - id: rehearse-on-a-restored-copy
    description: "Run the migration against a copy restored from the backup, never against the live database"
    owner: agent
    command: null
    evidence: "pg_restore of the 2026-08-15 dump into a scratch database `rehearsal`, then `alembic upgrade head` (0018 → 0019 → 0020). 0020 reported: charges that got a fund of their own: [SOAT carro, Seguro del Carro]. EVERY figure identical before and after, including rates. The downgrade round-trip to 0018 was run too and the pre-015 code read the same totals afterwards. THE REHEARSAL CAUGHT A DEFECT: month_rates skipped funded obligations BY CATEGORY, so both car charges were counted twice — once by their own fund and once as a loose obligation — moving cost by exactly 58.333.334 + 3.727.500 = 62.060.834. Fixed and pinned by a unit test before the second rehearsal, which came out clean. The scratch database was dropped afterwards."
    completed: true
    blocking_acs:
      - AC-6

  - id: owner-present-migration
    description: "Run the migration against the real data with the owner watching"
    owner: human
    command: null
    evidence: null
    completed: false
    blocking_acs:
      - AC-6

  - id: measure-after
    description: "Confirm the two new funds ask exactly what the old one asked, and that no other figure moved"
    owner: agent
    command: null
    evidence: null
    completed: false
    blocking_acs:
      - AC-6

  - id: browser-pass
    description: "Drive the feature in a browser against the sandbox, reading balances in cents"
    owner: human
    command: null
    evidence: "Driven 2026-08-15 against the SQLite sandbox on http://localhost:3999 (ports 3000 and 3001 were held by unrelated node processes), the owner logging in himself. Eight things touched, not read: the Juntar column with all four refusals in Spanish; marking creates the fund with no form; the fund gets its own row reading 100.000 / 1.100.000 / julio de 2027; a dollar charge reads US$ 50,00 of US$ 600,00 with no pesos in the row; editing the cadence warns BEFORE saving and cancelling changes nothing; the movement offers only the marked charge of its category; accepting the warning removes the fund and leaves every movement untouched; unmarking leaves the charge alive. Read in cents rather than off the screen: asks=5.000 USD-cents with asks_cop=15.710.000 = 5.000 × 3.142, so the conversion happens exactly once; and after linking a 25.000 payment, settled_in(charge)=2.500.000 while spent_in(category)=0 — the AC-9 mirror, proven on real rows. orphan funds: [] and all 34 movements intact."
    completed: true
    blocking_acs:
      - AC-1
      - AC-3
      - AC-4
      - AC-5
      - AC-11
---

# Runbook — 015 fund-belongs-to-its-charge

Dos ceremonias que no son código: **la migración sobre datos reales** y **el
paso por navegador**. Las dos son puertas duras del charter — §7 capa
`migrations/**` a autonomía `low`, y §6 dice que verde no es verificado.

## Fase 1 — La migración (rebanada 4)

### Por qué existe esta fase

La producción es un contenedor Postgres local (ADR-0030). No hay staging, no hay
rollback automático, y el backup es la única red. La migración convierte **un**
fondo en **dos**, y aunque es la migración más chica que este proyecto ha
corrido, toca la plata que el dueño usa todos los días.

### Lo que ya se midió

Leído el 2026-08-15 contra el Postgres de producción, en solo lectura:

```
fund 1 · 🛡️ Auto Insurance · from_recurring   ← el único que migra
fund 2 · ✈️ Flights          · average          ← se queda como está
fund 3 · 🛒 Groceries        · average
fund 4 · 🍽️ Restaurants      · average
fund 5 · ⛽ Gas              · average

anchor_amount: nulo en los cinco  →  no hay nada guardado que repartir
```

### La cifra que no se puede mover

```
antes                        después
🛡️ Auto Insurance 686.063,64  →  🛡️ Seguro del Carro  636.363,64
                                 🛡️ SOAT carro          49.700,00
                                 ──────────────────────────────
                                                      686.063,64
```

Si esa suma cambia, la migración está mal y se restaura del backup.

De 5 filas en Fondos se pasa a 6, no a 8.

### Orden, y por qué ese orden

1. **`just backup`** — lo corre el dueño. Un pg_dump fechado a iCloud Drive.
   Nada empieza sin él (ADR-0030).
2. **Medir antes** — el agente lee, en solo lectura, lo que pide hoy el fondo de
   🛡️ Auto Insurance. Sin este número el «después» no se puede comparar contra
   nada.
3. **Ensayar sobre una copia restaurada** — el agente corre la migración contra
   una copia del backup, nunca contra la base viva. Es donde se descubre un error
   sin costo.
4. **Correrla con el dueño delante** — CHARTER §7. El agente no la corre solo
   contra datos reales, y esto no es una formalidad: es el único paso del plan
   entero que el agente tiene prohibido hacer por su cuenta.
5. **Medir después** — las dos cajas nuevas y ninguna otra cifra del mes.

### Si algo sale mal

Restaurar del dump del paso 1. No hay migración inversa que valga la pena
escribir para una fila.

## Fase 2 — El paso por navegador (CP7)

CHARTER §6: *«Green is not verified. A feature is driven in a browser before it
is called done.»*

Contra el sandbox, no contra producción. **Los saldos se leen en centavos, no de
la pantalla**, que redondea — así se encontraron los tres defectos de la 012 que
ninguna suite veía.

El contenedor del frontend **sí** recarga en caliente: los montajes están en
`docker-compose.yml`, no en el override de dev. No hay excusa para saltar este
paso alegando lo contrario.

Lo que hay que tocar de verdad, no leer:

- marcar un cobro en Recurrentes y ver aparecer su fila en Fondos (AC-1)
- que la fila diga cuánto cuesta, cuándo llega y cuánto pide (AC-3)
- destildar y ver que ningún movimiento cambió (AC-4)
- anotar un gasto a mano y enlazarlo al cobro que saldó (AC-5)
- un cobro en dólares que se lee entero en dólares (AC-11)

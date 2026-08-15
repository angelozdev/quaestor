---
slug: 015-fund-belongs-to-its-charge
checkpoint: 4
created: 2026-08-15
status: open
steps:
  - id: fresh-backup
    description: "Take a fresh pg_dump of the production container before anything touches it"
    owner: human
    command: "just backup"
    evidence: null
    completed: false
    blocking_acs:
      - AC-6

  - id: measure-before
    description: "Record what the single existing fund asks today, read-only, so the after can be compared to it"
    owner: agent
    command: null
    evidence: null
    completed: false
    blocking_acs:
      - AC-6

  - id: rehearse-on-a-restored-copy
    description: "Run the migration against a copy restored from the backup, never against the live database"
    owner: agent
    command: null
    evidence: null
    completed: false
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
    evidence: null
    completed: false
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

---
skill: discover-acs
agent_id: main-session
feature: 013-recurring-charge-keeps-its-price
started: 2026-08-11T1730
ended: 2026-08-11T1745
checkpoint: 2
artifacts:
  - features/013-recurring-charge-keeps-its-price/acs.md
findings_summary: "Edit pass on acs.md after the owner asked for the ACs to be measured against comparable systems. Five sources consulted: GnuCash's split model (amount in the account's commodity, value in the transaction's currency — two figures, rate implicit in the ratio), Firefly III's `foreign amount` field (required when transaction and account currencies differ), Lunch Money's per-transaction historic rate, Stripe/Braintree's presentment-vs-settlement split, and IAS 21 (record in the functional currency at the spot rate of the transaction date). TWO CHANGES CAME OUT OF IT. First, a real contradiction between AC-2 and AC-13 that CP3 would have hit: moving an auto rule to an account in another currency and declining the suggested conversion lands in the state AC-2 forbids. The owner chose refusal over silent mode-switching, consistent with his earlier answer on creating an auto rule; AC-13 now splits by mode. Second, AC-8 is the one criterion that diverges from every system surveyed — all of them keep both figures, Quaestor keeps one, deliberately, because ADR-0031 removed frozen per-transaction rates. Rather than reopen ADR-0031, AC-21 was added: the charge displays its rule's price beside what left, read from the already-linked rule, storing nothing. Without it a July charge of US$32,10 reads as 141.240 COP in December against a real price of 99.900 — 41% high, and the first case where the app knows the true peso figure and hides it. AC-13's design was independently validated: Firefly III has open defects (#3675, #9925) at exactly this point — transactions left in the wrong currency after their source account changes."
human_action_needed: yes
recommended_next: "/engineer.atdd to formalize as Given/When/Then specs — after the owner approves the amended acs.md."
tracker_update: "none — no status change; acs.md amended in place, AC IDs preserved."
exit_criteria:
  - criterion: "acs.md exists with numbered ACs, each carrying Priority and Type"
    verified_by: file
    met: true
    evidence: "AC-1..AC-21; frontmatter ac_count 21, high_priority_count 14, reviewed 2026-08-11"
  - criterion: "AC IDs preserved across the edit pass"
    verified_by: inspection
    met: true
    evidence: "AC-13 rewritten in place, AC-21 appended, nothing renumbered"
  - criterion: "every AC is written in domain language"
    verified_by: inspection
    met: true
    evidence: "AC-13 and AC-21 name la regla, el modo, el informe, la casilla del monto. The industry comparison naming GnuCash/Firefly III/IAS 21 sits in an italic note beside AC-8, not inside an AC's behaviour statement."
  - criterion: "internal contradictions between ACs resolved"
    verified_by: human
    met: true
    evidence: "AC-2 vs AC-13 surfaced with the Opal case and decided by the owner: an auto rule moving across currencies is refused unless the conversion is accepted or the rule is switched to manual. The app never changes the mode by itself."
  - criterion: "divergences from established practice are deliberate and recorded"
    verified_by: inspection
    met: true
    evidence: "AC-8 keeps one figure where GnuCash, Firefly III, Lunch Money and IAS 21 keep two. The note beside AC-8 records the survey, names ADR-0031 as the reason, and points at AC-21 as the compensation."
  - criterion: "the owner has reviewed and approved the ACs"
    verified_by: human
    met: true
    evidence: "Approved by the owner on 2026-08-11 after the industry review was presented: «apruebo, sigue con CP3». The two changes the review produced — AC-13 split by mode, AC-21 added — were his own calls, made before the approval."
status: complete
---

# discover-acs (revisión) — resumen del handoff

El dueño pidió medir los criterios contra otros sistemas. Salieron dos cosas.

## Una contradicción entre dos criterios propios

Opal se cobra sola en 9,99 USD sobre DolarApp. Se mueve a Nu, en pesos, y se
borra la conversión sugerida: AC-13 lo permitía y AC-2 lo prohibía. CP3 se
habría tropezado ahí.

El dueño eligió **rechazar el guardado** en vez de que la app cambie el modo
sola — coherente con lo que ya había respondido para el caso de crear. AC-13
ahora se parte según el modo.

## El criterio donde Quaestor está solo

**Todos los sistemas mirados guardan dos cifras**: GnuCash (amount y value, con
la tasa implícita en la razón), Firefly III (un «foreign amount» obligatorio),
Lunch Money (la tasa histórica de cada movimiento), IAS 21 (la tasa del día de
la transacción). Quaestor guarda una, y es a propósito: ADR-0031 quitó las tasas
congeladas.

En vez de reabrir ADR-0031 se agregó **AC-21**: el cobro muestra el precio de su
regla al lado de lo que salió, leyéndolo de la regla ya enlazada. No guarda
nada. Sin eso, un cobro de julio por US$32,10 se lee como **141.240 COP** en
diciembre contra un precio real de 99.900 — 41% de más, y la primera vez que la
app conoce la cifra verdadera y no la enseña.

## Lo que la comparación confirmó

AC-13 apunta a un punto donde Firefly III tiene defectos abiertos: movimientos
que quedan en la moneda equivocada al cambiarles la cuenta de origen
([#3675](https://github.com/firefly-iii/firefly-iii/issues/3675),
[#9925](https://github.com/firefly-iii/firefly-iii/issues/9925)). Sugerir en vez
de reescribir es la versión segura.

Y el caso tiene nombre en la industria de pagos: Hevy Pro cobra en pesos
(*presentment*), DolarApp debita en dólares (*settlement*). AC-5 y AC-8 son esa
separación, aplicada.

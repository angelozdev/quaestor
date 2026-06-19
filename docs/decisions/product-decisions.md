# Quaestor — Architecture Decision Records

**Fecha:** 2026-06-16
**Contexto:** sesión de revisión de producto sobre `docs/superpowers/specs/2026-06-16-quaestor-general-design.md`. Cada ADR registra un caso decidido, su alternativa descartada y la consecuencia en los sub-specs. Los specs P0–P7 fueron actualizados para reflejar estas decisiones.

> Formato: **Estado · Contexto · Decisión · Alternativas descartadas · Consecuencias.** Numeración estable; no se renumera al agregar.

---

## ADR-001 — El driver es backend propio + agent-native (no solo los 3 dolores)

**Estado:** aceptado

**Contexto.** Lunch Money ya funciona. Construir un sistema entero para single-user solo se justifica si el motor es más que "tres features que a LM le faltan".

**Decisión.** El driver primario es **(B) propiedad + agent-native**: DB propia, backend propio, hablarle a un agente sobre *mi* schema sin depender de la API de un tercero. Los 3 dolores (Por-pagar, metas, reportes) son la **prueba de valor de la v1**, no la justificación del sistema. El **presupuesto** es el diferenciador de producto explícito (ver ADR-002).

**Alternativas descartadas.** (A) Resolver solo los 3 dolores con un script sobre la API de LM → no da propiedad ni independencia del proveedor.

**Consecuencias.** Justifica el build completo (P0–P7). Prioriza el camino MCP/services sobre la UI (ver ADR-008). El presupuesto recibe inversión de diseño desproporcionada (P4).

---

## ADR-002 — Presupuesto híbrido: sobres con rollover + safe-to-spend

**Estado:** aceptado · **Reemplaza** el presupuesto plano del spec original (§6, P4)

**Contexto.** El spec original modelaba presupuesto estilo LM: categoría×mes, monto vs gasto real, % usado. Eso es exactamente lo que el usuario ya tiene en LM; no diferencia.

**Decisión.** Presupuesto **híbrido**:
- **Sobres por categoría con rollover.** Cada categoría tiene un sobre (`Budget` por mes); lo no gastado **se arrastra** al sobre del mes siguiente.
- **Safe-to-spend global** (ver ADR-003): un número de cabecera que integra recurrentes + planned + metas, algo que LM estructuralmente no hace.

**Alternativas descartadas.** Envelope/rollover puro estilo YNAB (compite en terreno donde YNAB ya gana, no diferencia); presupuesto plano de LM (no diferencia).

**Consecuencias.** P4 se reescribe (es el diferenciador). `Budget` gana semántica de rollover. Nuevo service `safe_to_spend`. P4 ahora **depende de P3** (necesita planned + recurrentes para "comprometido"). P5 y el dashboard muestran ambos números.

---

## ADR-003 — safe-to-spend = plata no asignada

**Estado:** aceptado

**Contexto.** Con dos capas (sobres + número global) hay riesgo de **contar la misma plata dos veces**: lo no gastado que rueda en un sobre Y cuenta como "libre". Se necesita una sola fuente de verdad.

**Decisión.** Cascada de asignación. El ingreso baja en capas:

```
ingreso forecast del mes
  − comprometido (recurrentes auto + planned + aportes de meta propuestos)
  − asignado a sobres discrecionales (con rollover)
  = SAFE TO SPEND = plata que NO has asignado a ningún sobre
```

- **safe-to-spend** = plata sin asignar (análogo a "Ready to Assign").
- **sobres** = plata ya asignada (con memoria/rollover).
- Una vez asignas a un sobre, sale del safe-to-spend → nada se cuenta dos veces.

**Alternativas descartadas.** safe-to-spend = "lo que sobra después de repartir todo" (cojín) → tiende a ~0, pierde valor como número de cabecera.

**Consecuencias.** Define la fórmula de `safe_to_spend` en P4. Depende del ADR-004 (de dónde sale el ingreso) y del ADR-014 (contar una vez).

---

## ADR-004 — El ingreso del safe-to-spend es forecast (esperado)

**Estado:** aceptado

**Contexto.** safe-to-spend depende de cuánta plata hay. Con ingreso variable, un forecast miente hasta que la plata llega; con cash-on-hand no puedes planear el mes hasta que cae el sueldo.

**Decisión.** **Forecast (esperado).** El ingreso esperado del mes sale **de los recurrentes `income` que tocan el mes** (sueldo, freelance fijo), **sin override teclado** (A2). Alimenta el safe-to-spend desde el día 1 → permite planear el mes de entrada. Un ingreso atípico (prima, bono) se registra como ingreso suelto y cuenta al postear, no se anticipa.

**Alternativas descartadas.** Cash-on-hand estilo YNAB (solo plata que ya entró) → más honesto pero no deja planear; se reconsidera si el ingreso se vuelve muy irregular. Override teclado por mes (A2) → fricción manual recurrente, se evitó.

**Consecuencias.** P4 lee el ingreso esperado de los recurrentes de tipo `income` del mes. El forecast se corrige a real conforme las tx postean, contando cada ingreso una sola vez (ADR-014).

---

## ADR-005 — Sobregiro de sobre come del safe-to-spend; rollover solo positivo

**Estado:** aceptado

**Contexto.** ¿Qué pasa cuando una categoría gasta más que su sobre?

**Decisión.** El exceso **come del safe-to-spend** (el pozo sin asignar). El **rollover arrastra solo saldo positivo**: un sobre sobregirado se absorbe en el pozo global y **resetea a 0** el mes siguiente (no arrastra negativo).

**Alternativas descartadas.** Arrastrar el negativo al mes siguiente (estilo YNAB estricto) → castiga doble y complica la lectura para single-user.

**Consecuencias.** Define `rollover_in = max(saldo_previo, 0)` en P4. Detalle de implementación; los tests de P4 lo fijan.

---

## ADR-006 — Metas flexibles (propone + confirmas), no ahorro forzado

**Estado:** aceptado · **Cambia** la postura del spec original (§6, P4: aporte auto-transferido en rollover)

**Contexto.** El spec original hacía que `cerrar_mes` auto-creara la `GoalContribution` + transferencia: la meta se pagaba sola como un recibo. Riesgo: un mes apretado mete un transfer automático que te deja en rojo.

**Decisión.** **Ahorro flexible.** El rollover **propone** el aporte como una obligación `planned` (aparece en "Por pagar"); tú la **confirmas** con el monto real (o la omites si el mes vino flojo). No mueve plata sola.

**Alternativas descartadas.** Ahorro forzado / auto-transfer (disciplina máxima, pero pelea con meses irregulares y rompe el balance).

**Consecuencias.** P4: el hook de rollover pasa de `aplicar_aportes_meta` (auto-transfer) a `proponer_aportes_meta` (crea `planned`). `GoalContribution` se registra al **confirmar**, no en el rollover. Reusa la maquinaria `planned`/`confirmar_pago` de P3 (ver ADR-007). P3 expone un seam post-confirm para que P4 registre la contribución sin que P3 conozca metas.

---

## ADR-007 — "Por pagar" es la cola única de confirmación

**Estado:** aceptado

**Contexto.** Tras ADR-006, tres cosas distintas necesitan confirmación: recurrentes manuales (luz, agua), pagos sueltos (le debo a un amigo) y aportes de meta.

**Decisión.** Las tres convergen en **"Por pagar"** como única cola de confirmación. Todas son tx `planned` que `confirmar_pago` vuelve `posted`.

**Alternativas descartadas.** Flujos separados por tipo → tres mentales distintos para la misma acción ("confirmar una obligación").

**Consecuencias.** `por_pagar` (P3) lista los tres orígenes. El dashboard mínimo (ADR-008) se centra en este widget. P4 enlaza sus aportes propuestos a la cola de P3.

---

## ADR-008 — Frontend v1 mínimo (MCP-first); CRUD completo a backlog

**Estado:** aceptado · **Recorta** el alcance del spec original (§8, P6: UI completa en v1)

**Contexto.** El driver es agent-native (ADR-001). Un Next.js completo (10 rutas, CRUD de todo) en v1 es semanas de un producto distinto que compite con el motor. El chat hace mal **revisar** (dashboards, tablas), bien **registrar**.

**Decisión.** **MCP-first.** v1 del frontend = **dos vistas read-first**: dashboard con el widget "Por pagar" + el reporte mensual. El resto de CRUD se opera por agente; las demás pantallas quedan **documentadas como backlog**, no borradas.

**Alternativas descartadas.** UI completa en v1 (máximo tiempo hasta usarlo); MCP-only sin UI (pierde las dos vistas que el chat hace mal).

**Consecuencias.** P6 se recorta a v1 mínimo + backlog. Orden de construcción del frontend: dashboard/Por-pagar y reporte primero; el resto cuando haga falta.

---

## ADR-009 — Arranque en frío limpio (sin backfill por ahora)

**Estado:** aceptado

**Contexto.** Reportes con drift MoM, USD share y rollover de sobres necesitan historia para servir. Arrancar vacío los deja decorativos ~2-3 meses.

**Decisión.** **Arranque limpio, sin backfill por ahora.** Se acepta reportes flojos los primeros meses. El **importer CSV se mantiene en alcance** (P5) por si se decide backfillear historial de LM luego (exportar LM → mapear al CSV propio → importar una vez).

**Alternativas descartadas.** Backfill inmediato vía CSV (instant historia, pero trabajo ahora); migrador de LM dedicado (sobreingeniería para un import único, ya descartado en el spec).

**Consecuencias.** P5 nota que el importer sigue disponible para backfill diferido; el reporte degrada con elegancia cuando no hay mes previo.

---

## ADR-010 — Multi-moneda COP+USD completa

**Estado:** aceptado (confirma decisión del spec)

**Contexto.** El usuario tiene aproximadamente la mitad de sus gastos en USD (no es metadato ocasional).

**Decisión.** **Multi-moneda completa**, tal como la diseña el spec: `currency` + `fx_rate` + `to_base` **congelado** al registrar + tabla `FxRate`. Los agregados históricos quedan estables aunque cambie la tasa.

**Alternativas descartadas.** Registrar solo el COP que cobró la tarjeta y dejar FX como metadato (válido solo si el USD fuera marginal); COP-only.

**Consecuencias.** Sin cambios al modelo FX de P0. Destapa el problema de **de dónde sale la tasa** (ADR-011).

---

## ADR-011 — Tasa FX: auto-fetch diaria + override manual

**Estado:** aceptado · **Cambia** "manual" del spec original (§5, P0)

**Contexto.** Con USD ~50% del volumen, mantener la tasa a mano es fricción constante y olvidable; una tasa vieja deja el `to_base` chueco.

**Decisión.** Un **job diario** en el VPS pega a una API FX gratis y guarda la tasa en `FxRate`. `fijar_tasa_fx` queda como **override manual / respaldo** si la API falla. El `to_base` se sigue congelando al registrar.

**Alternativas descartadas.** Solo manual (fricción); que el agente busque la tasa al registrar (menos reproducible, depende del cliente MCP).

**Consecuencias.** P7 agrega el job programado (junto al rollover). P0 expone el hook de actualización de tasa que el job invoca. Consistencia histórica intacta (to_base congelado).

---

## ADR-012 — Recurrentes: auto para fijo, manual para variable (asimetría intencional)

**Estado:** aceptado (confirma decisión del spec)

**Contexto.** Tras ADR-006/007, metas y recurrentes manuales pasan por confirmación. Los recurrentes **auto** son lo único que aún postea solo. ¿Inconsistencia?

**Decisión.** Es a propósito: **confirmas donde hay una decisión real, automatizas donde no la hay.** Arriendo/Netflix = monto fijo, nada que decidir → auto-postea. Luz/agua = varía → manual, confirmas. La asimetría es feature.

**Alternativas descartadas.** Todo por "Por pagar" (forzar confirmación donde no hay elección = fricción, no control).

**Consecuencias.** Sin cambios a P3 en esto. Refuerza el guard de ADR-014 (un auto-recurrente que postea no debe mover el safe-to-spend si ya estaba comprometido).

---

## ADR-013 — Auth: /mcp tras Tailscale; frontend público con contraseña

**Estado:** aceptado · **Endurece** el spec original (§4: todo público tras HTTPS con token estático)

**Contexto.** Un `APP_TOKEN` estático es lo único entre internet y lectura/escritura total del historial financiero. No expira ni rota. El usuario opera el MCP desde sus propios equipos.

**Decisión.** El endpoint sensible `/mcp` queda **fuera de internet público**, detrás de **Tailscale** (red privada); el usuario lo alcanza desde sus dispositivos. El **frontend sigue público** detrás de contraseña + HTTPS. El `APP_TOKEN` estático se mantiene (ya no expuesto en el punto crítico).

**Alternativas descartadas.** Token estático público tal cual (un leak = acceso total, sin botón de pánico) — válido solo si se necesitaran clientes MCP en la nube; tokens rotables + expiración (overkill para una persona).

**Consecuencias.** P7 agrega Tailscale para `/mcp`; Caddy sigue público para el frontend. P2 documenta que el transporte vive en la red privada. **Trade-off:** clientes MCP en la nube (claude.ai web) no alcanzan `/mcp`; si se necesitaran, se revisa.

---

## ADR-014 — safe-to-spend cuenta cada obligación una sola vez

**Estado:** aceptado · **Guard crítico**

**Contexto.** Una obligación existe primero como esperada/`planned` y luego como `posted`. Si el safe-to-spend la resta en ambos estados, el número miente y se pierde la confianza.

**Decisión.** safe-to-spend cuenta cada obligación **exactamente una vez**, esté `planned` o ya `posted`. Cuando un recurrente auto se postea o un `planned` se confirma, la plata pasa de "esperada" a "real" pero el safe-to-spend **no se mueve** — ya estaba descontada.

**Alternativas descartadas.** Sumar planned + posted por separado (double-count).

**Consecuencias.** P4 define "comprometido" como la unión (sin doble conteo) de obligaciones del mes en cualquier estado. Tests de P4 lo verifican explícitamente.

---

## ADR-015 — Cuenta origen de los aportes de meta: global (Settings)

**Estado:** aceptado (caso A3)

**Contexto.** El aporte a una meta es una transferencia interna: la meta define la cuenta **destino** (ahorro), pero faltaba definir la cuenta **origen** de la que sale la plata.

**Decisión.** **Una cuenta origen global** en `Settings` (`default_source_account_id`). Todos los aportes de meta salen de ahí. No importa la cuenta puntual; se prefiere simple.

**Alternativas descartadas.** Cuenta origen por meta (`Goal.source_account_id`) → config de más por meta; elegir al confirmar en "Por pagar" → flexible pero innecesario para este usuario.

**Consecuencias.** `Settings` gana `default_source_account_id` (FK Account). `proponer_aportes_meta` crea la propuesta `planned` con esa cuenta como origen; al confirmar, la transferencia sale de ahí. Si se quisiera por-meta luego, se agrega sin romper.

---

## ADR-016 — Sobres opcionales (no "cada peso un trabajo")

**Estado:** aceptado (caso A4)

**Contexto.** ¿Toda categoría con gasto debe tener sobre (YNAB "every dollar a job"), o solo algunas?

**Decisión.** **Sobres opcionales.** Solo las categorías que el usuario quiera disciplinar llevan `Budget`; el resto gasta **directo del safe-to-spend**. Esto es lo que mantiene al safe-to-spend como número de cabecera con sentido: si todo estuviera asignado, tendería a 0 (la gracia que ADR-002/003 buscaban se perdería).

**Alternativas descartadas.** "Cada peso un trabajo" (todas las categorías con sobre) → safe-to-spend ≈ 0, y obliga a presupuestar todo cada mes (pesado).

**Consecuencias — corrige la fórmula del safe-to-spend.** El gasto en categorías **sin sobre** debe restarse del pozo (si no, el número sobreestima la plata libre). Fórmula completa (ADR-003/005/014/016):
```
safe_to_spend = ingreso_forecast
              − comprometido                          # obligaciones, contadas 1 vez (ADR-014)
              − Σ amount_assigned (categorías con sobre, este mes)
              − Σ gasto_no_presupuestado               # gasto posted en categorías SIN sobre
              − Σ sobregiro                            # por sobre: max(gastado − (asignado + rollover_in), 0)
```
- El `rollover_in` (plata de meses previos arrastrada al sobre) **no** suma al safe-to-spend de este mes (ya está en el sobre) y **protege** contra contar sobregiro falso.
- Las interacciones rollover × sobregiro × no-presupuestado las **fijan los tests de P4**.

---

## ADR-017 — `cerrar_mes` se dispara automático (scheduler diario, idempotente)

**Estado:** aceptado (caso A5)

**Contexto.** El rollover (`cerrar_mes`) materializa el mes: postea recurrentes `auto`, manda manuales + aportes de meta a "Por pagar". Si depende de que el usuario lo corra a mano y se le olvida, "Por pagar" queda vacío → rompe el dolor #1 ("¿qué me falta por pagar?").

**Decisión.** **Automático, sin disparo manual relevante.** El `scheduler` (que ya corre diario para FX, ADR-011) **asegura cada día que el mes actual esté cerrado**: el día 1 materializa el mes; los demás días son no-op (idempotencia, P3); un día 1 perdido **se auto-cura** en la siguiente corrida. No es un cron mensual frágil sino un "ensure" diario.

**Alternativas descartadas.** Manual ("cierra junio") → frágil, depende de la memoria. Híbrido auto + manual → el usuario eligió auto puro; el disparo manual no se necesita (y la idempotencia ya cubre re-correr si algún día hiciera falta).

**Consecuencias.** P7: el `scheduler` corre, diario, FX + `ensure_mes_cerrado(mes_actual)`. `cerrar_mes` sigue siendo el service que invoca (P3); deja de ser una tool MCP de cara al usuario (se opera solo). La idempotencia de P3 es ahora **requisito de robustez**, no solo de corrección.

---

## ADR-018 — Mecanismo del aporte de meta flexible (revisado y aceptado)

**Estado:** aceptado (casos B1, B2 — mecanismos propuestos por el asistente y validados por el usuario)

**Contexto.** El aporte flexible (ADR-006) requiere: proponer como `planned`, confirmar moviendo plata real (transfer a ahorro) y registrar el aporte — sin que P3 (dueño de "Por pagar"/confirmar) sepa qué es una meta. El mecanismo concreto no estaba decidido por el usuario; lo propuso el asistente y se revisó.

**Decisión.**
- **B1 — registro del aporte (dos registros):** se mantiene `goal_id` FK en `Transaction` + un **hook post-confirm** en P3 que escribe la fila `GoalContribution` al confirmar. Se descartó "derivar los aportes de los transfers etiquetados" (una sola fuente de verdad) — el usuario prefirió el registro explícito.
- **B2 — movimiento de plata (un solo confirmar):** `confirmar_pago` de P3 **materializa transferencias planeadas** (par real vía `transferir`) como capacidad **genérica** — no específica de metas. Un solo verbo de confirmación para todo (pago de una cuenta o transfer de dos). Se descartó un `confirmar_aporte` propio de P4 (dos caminos de confirmación).

**Alternativas descartadas.** B1: aportes derivados de transfers con `goal_id` (menos maquinaria, pero el usuario eligió registro explícito). B2: P4 dueño de su confirmación (P3 intacto, pero dos caminos).

**Consecuencias.** Sin cambios respecto a lo ya escrito en P3/P4 (el mecanismo descrito allí queda confirmado). `confirmar_pago` que materializa transfers planeados queda como capacidad reutilizable más allá de metas.

---

## ADR-019 — Reporte mensual retrospectivo (titular = neto + desempeño de sobres; safe-to-spend al pie)

**Estado:** aceptado (caso C1) · **Cambia** el rol del safe-to-spend en el reporte (§9, P5: era "número de cabecera")

**Contexto.** Dos superficies muestran números del mes: el **dashboard** (vivo, mes actual, headline = safe-to-spend "cuánto me queda") y el **reporte** (`/reports`, selector de mes). El spec original ponía **safe-to-spend como número de cabecera del reporte**. Pero safe-to-spend es *forward-looking* ("lo que me queda por gastar"): en un mes ya cerrado es solo el sobrante, un titular raro. Riesgo: reporte ≈ dashboard con date-picker → redundante.

**Decisión.** El reporte mensual es **retrospectivo puro** y responde *"¿cómo me fue?"*. Su **titular es el neto del mes + el desempeño de los sobres** (cuántos en verde/rojo, cuánto rollover generaste para el mes siguiente) — justo lo que LM no cuenta. El **safe-to-spend baja a dato de cierre al pie** ("cerraste con $X libres"), no es el titular. El dashboard sigue dueño del safe-to-spend en vivo. Roles separados, cero redundancia.

**Alternativas descartadas.** (B) safe-to-spend congelado como titular del reporte → reporte ≈ dashboard histórico, poco valor extra y titular sin sentido en meses cerrados. (C) sin titular, todas las secciones planas (estilo LM) → pierde el "de un vistazo".

**Consecuencias.** P5: el `safe_to_spend` del `ReporteMensual` pasa de "número de cabecera" a **cierre al pie**; el titular se arma con `neto` + un **resumen de desempeño de sobres** (verde/rojo + rollover total generado). El renderer markdown ordena: neto → sobres → metas → … → safe-to-spend al cierre. El dashboard (P6) no cambia (sigue mostrando safe-to-spend arriba, en vivo).

---

## ADR-020 — Motor de recurrencia genérico (intervalo cada-N) + materialización diaria due-driven

**Estado:** aceptado (caso C2) · **Reemplaza** el `frequency` enum + `due_day` y la llave `(recurring_id, period)` del spec original (§5, P3)

**Contexto.** El spec modelaba `frequency ∈ {monthly, weekly, biweekly, yearly}` con un `due_day` (día-del-mes) y una occurrence con llave única `(recurring_id, period=YYYY-MM)` → **una sola occurrence por recurrente por mes**. Eso choca con cualquier frecuencia sub-mensual: un recurrente semanal cae ~4 veces/mes, uno quincenal 2. Tal como estaba, semanal/quincenal disparaban una sola vez. Además el usuario pidió **variedad real**: mensual, cada 3 y 4 meses, semestral, anual, semanal, cada 2 semanas, etc.

**Decisión.** **Motor genérico cada-N**, anclado a fecha:
- `RecurringItem` reemplaza `frequency` + `due_day` por **`interval_unit ∈ {day, week, month, year}` + `interval_count` (≥1)**, anclado en `start_date`. Cada vencimiento = `start_date + k × intervalo`; clamp fin de mes para unit `month`/`year` (día 31 → 30/28). Cubre todo: mensual=`1 month`, trimestral=`3 month`, cada-4-meses=`4 month`, semestral=`6 month`, anual=`12 month`, semanal=`1 week`, quincenal/cada-2-semanas=`2 week`.
- La occurrence se llavea por **`(recurring_id, due_date)`** (no por `period`). Más preciso y sigue idempotente.
- **Materialización due-driven (no eager):** el `scheduler` diario (ADR-011/017) materializa cada día las occurrences con `due_date ≤ hoy` aún no creadas. Un **auto** postea en su fecha real (no el mes entero por adelantado → el balance no adelanta gastos); un **manual** se genera `planned` para el mes en curso, visible en "Por pagar". Días perdidos se auto-curan.

**Alternativas descartadas.** (A) Solo mensual/anual (quincenal = 2 recurrentes separados) → simple pero parte ítems y no da la variedad pedida. Materialización **eager** (todo el mes de golpe al cerrar) → el balance de hoy adelanta gastos futuros, justo lo que un sistema "¿cuánto me queda?" debe evitar.

**Consecuencias.** P3 se rediseña: `RecurringItem` con intervalo cada-N; occurrence por `due_date`; se **separa** la **materialización diaria de recurrentes** (due-driven, cualquier intervalo) del **cierre mensual** (rollover de sobres + propuesta de aportes de meta, que siguen siendo por `period` calendario, ADR-022). `domain/rules.py` cambia `toca_periodo`/`fecha_vencimiento` por un generador de fechas por intervalo. P7: el scheduler diario corre FX + materializar-vencidos(hoy) + ensure cierre mensual. Idempotencia ahora por `(recurring_id, due_date)`.

---

## ADR-021 — Tarjeta de crédito por causación (gasto al comprar; pago de extracto = transferencia)

**Estado:** aceptado (caso C3)

**Contexto.** `Account.type` ya incluye `credit`. Con débito/efectivo la plata sale al instante; con **tarjeta de crédito** compras hoy y el dinero sale del banco semanas después (al pagar el extracto). Faltaba decidir cuándo ese gasto golpea presupuesto y safe-to-spend.

**Decisión.** **Por causación (estilo YNAB).** El gasto con tarjeta cuenta **el día de la compra** contra el sobre de su categoría y baja el safe-to-spend en ese momento. Dos reglas firmes lo sostienen:
1. El **pago del extracto es una transferencia** (cuenta débito → cuenta tarjeta), **nunca un gasto** — si no, se contaría dos veces.
2. El safe-to-spend y los sobres cuentan los gastos de **todas las cuentas, incluida la tarjeta**, en la fecha de compra.

La cuenta de tarjeta queda como una cuenta normal con **saldo negativo = deuda**; el pago la sube hacia cero sin volver a tocar el presupuesto.

**Alternativas descartadas.** Criterio de caja (el gasto con tarjeta no toca presupuesto hasta pagar el extracto) → el safe-to-spend se infla durante el mes y revienta de golpe al pagar; deshonesto para un sistema cuyo norte es "¿cuánto me queda?".

**Consecuencias.** El **modelo actual ya soporta esto sin cambios estructurales**. Se documentan las dos reglas firmes en P0 (semántica de cuenta `credit`), §5/§6 del general y P4 (el `gastado`/`gasto_no_presupuestado` del safe-to-spend agregan **todas las cuentas**; el pago de extracto, al ser `transfer`, ya está excluido de gasto).

---

## ADR-022 — Período de presupuesto = mes calendario

**Estado:** aceptado (caso C4) · confirma el supuesto del motor

**Contexto.** Todo el sistema está cableado a `YYYY-MM`: cierre mensual, sobres, rollover, safe-to-spend. La alternativa era presupuestar por **ciclo de pago** (ej. del 15 al 14, anclado a cuándo entra el sueldo), útil para quien vive "de quincena a quincena".

**Decisión.** **Mes calendario** (1 → fin de mes). El presupuesto, los sobres y el safe-to-spend se reinician el día 1. Es como razona la mayoría y como ya está construido el motor entero.

**Alternativas descartadas.** Ciclo de pago configurable (15 → 14) → rompe el supuesto `YYYY-MM` que atraviesa P3/P4/P5; habría que re-llavear cierre, rollover y reportes a rangos arbitrarios. Caro, y el **rollover de sobres ya cubre** el caso (lo que sobra de la primera quincena queda disponible para la segunda dentro del mismo mes calendario).

**Consecuencias.** Ninguna al modelo (confirma lo existente). Nota: la **materialización de recurrentes** es por fecha (due-driven, ADR-020), pero el **cierre/rollover de presupuesto y la propuesta de aportes** siguen siendo por mes calendario.

---

## ADR-023 — Grupo de categoría como entidad propia

**Estado:** aceptado (caso C5) · **Cambia** `Category.group_name` (string) del spec original (§5, P0)

**Contexto.** La categoría siempre fue entidad (tabla `Category`) y el reporte por categoría ya existe. El "grupo" (contenedor que junta categorías: "Esenciales" → Mercado, Arriendo) estaba como **texto libre** (`group_name`). El usuario quiere estructura y reportes por categoría **y por grupo**.

**Decisión.** El grupo pasa a ser **entidad propia `CategoryGroup`**; cada `Category` apunta a un grupo por **FK (`group_id?`)**. Se gana: renombrar el grupo en un solo lugar, orden fijo (y color a futuro), cero typos/duplicados fantasma, y rollups de reporte por grupo limpios.

**Alternativas descartadas.** Grupo como texto libre → permite agrupar en reportes, pero renombrar obliga a tocar cada categoría, los typos crean grupos duplicados y no hay orden/color. Para un usuario que quiere reportes por grupo, la entidad vale su CRUD mínimo.

**Consecuencias.** P0: nueva entidad `CategoryGroup` (`name`, `sort_order`, `archived`) + servicios `crear_grupo`/`listar_grupos`; `Category.group_name` → `group_id?` (FK); `crear_categoria` recibe `group_id`. §5 del general agrega la fila `CategoryGroup` y cambia `Category`. P5: `SeccionCategoria` resuelve el nombre del grupo por FK y habilita rollup por grupo. P6: `/categories` y `/category-groups` (backlog) gestionan ambos.

---

## ADR-024 — Maestros y alcance v1: categoría opcional, settings mínimo, importer sin UI (confirmaciones)

**Estado:** aceptado (caso C5, cierres menores) · confirma supuestos del spec

**Contexto.** Barrido final de maestros/alcance: tres puntos que el spec ya asumía pero no estaban registrados como decisión.

**Decisión.**
- **Categoría opcional al registrar.** `Transaction.category_id` sigue nullable: puedes registrar "gasté 30 mil" sin categoría. El gasto sin sobre cae en `gasto_no_presupuestado` del safe-to-spend (ADR-016). Baja fricción con el agente; el reporte muestra cuánto quedó sin categorizar.
- **Settings mínimo.** Solo `base_currency=COP` (fija) y `default_source_account_id` (ADR-015). No se agregan perillas para un solo usuario; una preferencia real futura = una fila más, no un panel.
- **Importer como service, sin UI en v1.** `importar_csv` (formato propio) queda en P5 como contrato testeado, pero se arranca limpio (ADR-009) y el frontend v1 **no** trae pantalla `/import` (ADR-008). Usable por MCP/endpoint si hace falta puntualmente.

**Alternativas descartadas.** Forzar categoría siempre (fricción); panel de settings configurable (config que nadie tocará); pantalla `/import` en v1 (UI para algo que no se usa al arrancar limpio).

**Consecuencias.** Ninguna estructural — confirma lo existente. P5 mantiene el importer disponible (backfill diferido); P6 deja `/import` y el grueso de `/settings` en backlog.

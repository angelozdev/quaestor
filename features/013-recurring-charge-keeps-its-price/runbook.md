# Runbook — 013, la migración de los dos precios

Fase 4 del plan. Toca **datos reales**: CHARTER §7 exige al dueño presente, y el
manifiesto topa `backend/src/quaestor/migrations/**` en autonomía `low`.

Nada de esto se marca hecho sin la evidencia que cada paso pide.

## Qué escribe

```
Hevy Pro    30,22 USD/año  →   99.900 COP/año    · sigue en DolarApp · pasa a manual
Smart Fit   37,20 USD/mes  →  120.000 COP/mes    · sigue en DolarApp · pasa a manual
```

Los precios van **escritos en el cuerpo de la migración**, no calculados.
Convertir daría 94.951 y 116.882, porque la tasa que escribió las cifras viejas
(≈3.306) no existe en ninguna parte.

## Qué NO escribe

Ninguna otra regla. Ningún movimiento ya registrado. Ningún saldo. La migración
empareja por **nombre + monto actual + moneda actual**; si algo no cuadra
exactamente, esa fila se deja como está.

---

## Pasos

### 1. Respaldo fresco

- [x] **human** — `just backup`
- `evidence:` `QuaestorBackups/quaestor-local-2026-08-12.dump`, 58.582 bytes, 2026-08-12 08:04
- `command:` `just backup`
- `evidence:` la ruta del `.dump` con la fecha de hoy en iCloud Drive

> Sin esto no se sigue. Es el mismo respaldo que salvó la reparación de las 31
> filas negativas de Lunch Money el 2026-08-09.

**Corrido entero el 2026-08-12.** Los pasos 3 y 7 encontraron dos defectos que
ninguna suite veía: uno que habría reventado la migración contra Postgres, y uno
que habría hecho que deshacerla encendiera cobro automático.

### 2. Leer el estado de partida, sin escribir

- [x] **agent** — leer las dos reglas y anotar monto, moneda, cuenta y modo
- `evidence:` `regla|1|Smart Fit|3720|USD|manual` y `regla|30|Hevy Pro|3022|USD|manual`, las dos en 💵 DolarApp (USD). **Las dos ya estaban en manual**, no en automático como suponía la migración — ver el paso 7
- `evidence:` las dos filas, pegadas literalmente en el registro de la fase

> Si alguno de los cuatro campos no es el esperado, **parar** y decírselo al
> dueño. Un precio distinto significa que lo cambió a mano desde el 2026-08-09 y
> el número cargado ya no es el correcto.

### 3. Ensayar sobre una copia restaurada

- [x] **agent** — restaurar el respaldo del paso 1 en una base aparte y correr
      la migración ahí
- `evidence:` base `quaestor_rehearsal`, restaurada del dump de hoy. **El ensayo falló la primera vez** con `column "mode" is of type recurringmode but expression is of type character varying`: en Postgres `mode` es un enum nativo y la migración lo trataba como texto. Verde en SQLite, roja en producción — exactamente lo que este paso existe para encontrar. Corregido con un `cast` explícito; segunda corrida limpia
- `evidence:` las dos reglas leídas después, con precio, cuenta y modo

> Es la mitad del `validation_method` que ninguna suite cubre. Aquí es donde se
> descubre si el emparejamiento por nombre falla.

### 4. Comprobar que no movió nada más

- [x] **agent** — sobre la copia: contar reglas, contar movimientos, y leer el
      saldo de cada cuenta antes y después
- `evidence:` `diff` de 29 líneas antes/después: **cambian dos, y solo dos**. Los nueve saldos iguales, los tres conteos iguales (17 reglas, 671 movimientos, 62 ocurrencias), y las otras quince reglas iguales — incluida `Smart Fit anual` (2651 USD), la vecina que el emparejamiento por nombre podría haber atrapado
- `evidence:` los tres conteos y los nueve saldos, iguales a los de antes

> **Nueve saldos, no la suma de los movimientos.** Seis de las nueve cuentas no
> cuadran con esa suma y ninguna es un error.

### 5. Correr sobre producción, con el dueño delante

- [x] **human** — presente mientras corre — «perfecto», 2026-08-12
- [x] **agent** — aplicar la migración
- `evidence:` `just migrate` → `Running upgrade 0016 -> 0017`; `alembic_version` = `0017`. `diff` de producción: las mismas dos líneas, nada más
- `evidence:` la salida de Alembic con la revisión aplicada

### 6. El dueño lo mira en la app

- [x] **human** — abrir Recurrentes y ver las dos reglas
- `evidence:` Hevy Pro `$ 99.900 ≈ US$ 31.80`, Smart Fit `$ 120.000 ≈ US$ 38.19`, las dos manuales en DolarApp. `Smart Fit anual` sigue en `US$ 26.51`
- `evidence:` confirmación explícita de que Hevy Pro dice 99.900 COP, Smart Fit
  120.000 COP, las dos en DolarApp y las dos esperando aprobación

> Lo que se comprueba aquí no es que la migración corrió — eso lo dice Alembic —
> sino que el dueño reconoce sus propios cobros. La feature 012 encontró cuatro
> defectos con toda la suite verde justamente así.

### 7. Saber deshacerlo

- [x] **agent** — dejar escrito el `downgrade` y probarlo sobre la copia del
      paso 3
- `evidence:` `alembic downgrade 0016` sobre la copia → `diff` contra el estado de partida: **idéntico**. Antes de eso el `downgrade` ponía las dos en `auto`, suponiendo que de ahí venían; el paso 2 mostró que ya estaban en `manual`, así que deshacer habría **encendido** cobro automático que nunca estuvo encendido. Ahora devuelve precio y moneda y no toca el modo, y `tests/db/test_migration_0017.py` lo fija en seis pruebas
- `evidence:` las dos reglas de vuelta a 30,22 USD y 37,20 USD, automáticas

> El camino de vuelta se prueba antes de necesitarlo, no cuando hace falta.

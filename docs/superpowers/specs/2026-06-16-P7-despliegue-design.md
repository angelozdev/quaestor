# Quaestor — P7 Despliegue (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** todos (P0, P1, P2, P3, P4, P5, P6) — empaqueta lo que ellos producen
**Parte de:** `2026-06-16-quaestor-general-design.md` (ver §4 Despliegue y auth, §3 Arquitectura)

---

## Objetivo

Poner Quaestor en línea: un **VPS self-hosted**, **single-user**, con dominio + HTTPS. El **frontend y `/api/*` son públicos** detrás de Caddy; el **`/mcp` no se expone a internet** — vive detrás de **Tailscale** (red privada, ADR-013) y solo lo alcanzan los equipos del usuario. Que el browser sirva el frontend por HTTPS, que `curl` a la API con token responda, que Claude Code se conecte al `/mcp` **por Tailscale**, que un **job diario** mantenga la tasa FX fresca (ADR-011), y que la DB esté respaldada en continuo y sea restaurable.

## Alcance

- `docker-compose.yml`: servicios `api`, `mcp`, `frontend`, `caddy`, **`tailscale`** (sidecar que sirve `/mcp` en la red privada) y **`scheduler`** (job diario de FX). La DB (`quaestor.db`) vive en un **volumen persistente compartido por `api` y `mcp`**.
- `Caddyfile`: un dominio, enrutado por path. HTTPS automático (Let's Encrypt). **Solo publica frontend + `/api/*`; `/mcp` no sale a internet** (lo sirve Tailscale).
- **Scheduler diario (ADR-011/017):** el `scheduler` corre, **cada día**, dos jobs: (a) **FX** — pega a una API gratis y actualiza `usd_cop` en `FxRate` (`python -m quaestor.jobs.fx_fetch` → `fijar_tasa_fx`); (b) **`ensure_mes_cerrado`** — asegura que el mes actual esté cerrado (`cerrar_mes(mes_actual)`, idempotente): el día 1 lo materializa, los demás días son no-op, un día perdido se auto-cura. El rollover se opera **solo**, no a mano.
- Variables de entorno (`.env`, no commiteado): `APP_TOKEN`, hash de contraseña del frontend, dominio, ruta de la DB, config de Litestream, **`TS_AUTHKEY`** (Tailscale), **`FX_API_URL`/`FX_API_KEY`** (proveedor de tasa).
- Backups con **Litestream** (replicación continua a un bucket) + restauración; mínimo alterno: cron `sqlite3 .backup` diario.
- Pasos de deploy (`git pull && docker compose up -d --build`) y cómo conectar Claude Code al `/mcp` **por Tailscale**.
- Postura de seguridad: API pública solo con token; **`/mcp` fuera de internet (Tailscale)**; solo Caddy publica 80/443.

**Fuera de alcance:** CI/CD, orquestación multi-nodo, alta disponibilidad, Postgres (el general lo deja como migración futura por connection string). Single-writer SQLite es suficiente para single-user.

## Aporte al modelo de datos

**Ninguno.** P7 no define entidades, campos ni migraciones. Solo empaqueta y despliega artefactos de P0–P6. Su única relación con los datos es operativa: **dónde vive** `quaestor.db` (volumen), **quién lo escribe** (api + mcp, un solo proceso a la vez en la práctica) y **cómo se respalda/restaura**. Las migraciones las corre el backend al arrancar (responsabilidad de P0); P7 solo garantiza que el archivo persista entre reinicios.

## Componentes

| Componente | Qué es | Imagen / base |
|---|---|---|
| `api` | FastAPI servido por uvicorn (P1), escucha `:8000` interno | Python 3.12 + uv |
| `mcp` | MCP streamable-HTTP (P2), escucha `:9000` interno | Python 3.12 + uv |
| `frontend` | Next.js App Router (P6), `:3000` interno | node, build standalone |
| `caddy` | Reverse proxy + HTTPS auto, único que publica `80/443` al host (frontend + `/api/*`) | `caddy:2` |
| `tailscale` | Sidecar que une el VPS al tailnet y **sirve `/mcp`** en la red privada (`tailscale serve` → `mcp:9000`). No publica puertos al host | `tailscale/tailscale` |
| `scheduler` | Jobs diarios: fetch de tasa FX → `FxRate` + `ensure_mes_cerrado` (cerrar_mes idempotente del mes actual, ADR-017) | Python 3.12 + uv (reusa imagen `api`) |
| `litestream` | Sidecar (o proceso dentro de `api`) replicando la DB | `litestream/litestream` |
| volumen `quaestor-data` | Persiste `quaestor.db` (+ `-wal`, `-shm`) | named volume Docker |

`api` y `mcp` montan **el mismo volumen** en la misma ruta (`/data/quaestor.db`) → comparten el archivo SQLite. `frontend` y `caddy` no tocan la DB.

## Interfaz pública

Los artefactos versionados del sub-proyecto (en la raíz del repo):

### `docker-compose.yml` (forma)
```yaml
services:
  api:
    build: ./backend
    command: uv run uvicorn quaestor.api:app --host 0.0.0.0 --port 8000
    environment: [APP_TOKEN, DB_PATH, FRONTEND_PASSWORD_HASH]
    volumes: ["quaestor-data:/data"]
    expose: ["8000"]            # solo red interna, sin "ports:"
    restart: unless-stopped
  mcp:
    build: ./backend
    command: uv run python -m quaestor.mcp   # streamable-HTTP en :9000
    environment: [APP_TOKEN, DB_PATH]
    volumes: ["quaestor-data:/data"]
    expose: ["9000"]
    restart: unless-stopped
  frontend:
    build: ./frontend
    environment: [API_INTERNAL_URL=http://api:8000, FRONTEND_PASSWORD_HASH, APP_TOKEN]
    expose: ["3000"]
    restart: unless-stopped
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]   # único que publica al host (frontend + /api/*)
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on: [api, frontend]
    restart: unless-stopped
  tailscale:                       # /mcp NO sale a internet: se sirve por el tailnet
    image: tailscale/tailscale
    hostname: quaestor-mcp
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_SERVE_CONFIG=/config/ts-serve.json   # serve https /mcp -> http://mcp:9000
      - TS_STATE_DIR=/var/lib/tailscale
    volumes: ["tailscale-state:/var/lib/tailscale", "./ts-serve.json:/config/ts-serve.json:ro"]
    cap_add: ["NET_ADMIN"]
    depends_on: [mcp]
    restart: unless-stopped
  scheduler:                       # job diario de FX (ADR-011)
    build: ./backend
    command: ["./scripts/cron.sh"]  # crond diario: fx_fetch + ensure_mes_cerrado (idempotente)
    environment: [DB_PATH, FX_API_URL, FX_API_KEY]
    volumes: ["quaestor-data:/data"]
    restart: unless-stopped
volumes:
  quaestor-data:
  caddy-data:
  caddy-config:
  tailscale-state:
```

### `Caddyfile` (forma)
```caddy
{$DOMAIN} {
    encode gzip
    handle /api/* {
        reverse_proxy api:8000
    }
    # /mcp NO se enruta aquí: lo sirve el sidecar Tailscale en la red privada (ADR-013).
    handle {
        reverse_proxy frontend:3000
    }
}
```
HTTPS automático: Caddy obtiene y renueva el cert de Let's Encrypt para `$DOMAIN` solo. El puerto 80 redirige a 443.

### `.env.example` (documentado; el `.env` real **no se commitea**)
```dotenv
DOMAIN=quaestor.tudominio.com
APP_TOKEN=                 # bearer estático para API + MCP (genera 32+ bytes aleatorios)
FRONTEND_PASSWORD_HASH=    # hash (bcrypt/argon2) de la contraseña de login del frontend
DB_PATH=/data/quaestor.db
# Tailscale (sirve /mcp en red privada, ADR-013)
TS_AUTHKEY=                # auth key del tailnet (reusable, etiquetada)
# Tasa FX (job diario, ADR-011)
FX_API_URL=                # endpoint del proveedor de tasa usd_cop
FX_API_KEY=                # si el proveedor lo exige
# Litestream
LITESTREAM_BUCKET=s3://quaestor-backups/quaestor.db
LITESTREAM_ACCESS_KEY_ID=
LITESTREAM_SECRET_ACCESS_KEY=
LITESTREAM_ENDPOINT=       # para R2/Backblaze; vacío para AWS S3
```
`.env` y `quaestor.db*` van en `.gitignore`. `.env.example` sí se commitea, con valores vacíos.

## Lógica y reglas clave

**Un solo escritor SQLite.** SQLite admite un escritor a la vez. `api` y `mcp` comparten el archivo; en single-user los escritos son esporádicos y cortos, así que el bloqueo de SQLite (con **WAL** activo) los serializa sin problema. Reglas:
- **Modo WAL obligatorio** en la conexión (lo fija P0 en `db.py`): permite lecturas concurrentes mientras hay un escritor y reduce contención entre `api` y `mcp`.
- WAL implica **tres archivos**: `quaestor.db`, `quaestor.db-wal`, `quaestor.db-shm`. Deben vivir todos en el **mismo volumen** y la misma ruta para ambos servicios; nunca montar la DB por separado ni copiarla en caliente sin checkpoint.
- `busy_timeout` razonable (p. ej. 5s) para que el segundo escritor espere en vez de fallar con "database is locked".
- No correr más de una réplica de `api` ni de `mcp`. Single-writer es una invariante, no una limitación a esquivar.

**HTTPS y red.** Solo `caddy` publica puertos al host (`80`, `443`) → frontend + `/api/*`. `api`/`mcp`/`frontend` usan `expose` (visibles solo en la red interna de Docker, no en el host). **`/mcp` no entra por Caddy:** el sidecar `tailscale` lo sirve (`tailscale serve` → `mcp:9000`) **solo dentro del tailnet** (ADR-013); ningún puerto de `mcp` toca internet. El usuario alcanza `/mcp` por la MagicDNS del tailnet desde sus equipos.

**Auth (resumen de §4 del general, P1/P2 lo implementan).** API y MCP exigen `Authorization: Bearer $APP_TOKEN`; sin token → 401. Caddy **no** termina la auth, solo enruta; el token lo valida el servicio destino. El frontend valida la contraseña (contra `FRONTEND_PASSWORD_HASH`) y guarda sesión; del lado servidor adjunta `APP_TOKEN` a sus llamadas a la API. **Defensa en capas para `/mcp` (ADR-013):** primero Tailscale (el endpoint ni existe fuera del tailnet), luego el bearer token. El token estático deja de ser lo único que protege el punto sensible.

**Backups — Litestream (recomendado).** Replica `quaestor.db` en continuo (lee el WAL) a un bucket S3/R2/Backblaze. Config en `litestream.yml`:
```yaml
dbs:
  - path: /data/quaestor.db
    replicas:
      - url: ${LITESTREAM_BUCKET}
```
Restauración en limpio: `litestream restore -o /data/quaestor.db ${LITESTREAM_BUCKET}` antes de arrancar `api`/`mcp` (idealmente como paso de un entrypoint: si no existe la DB, restaurar; luego arrancar). **Mínimo alterno** si no hay bucket: cron diario `sqlite3 /data/quaestor.db ".backup /data/backups/quaestor-$(date +%F).db"` (usa la API de backup, segura en caliente) con retención de N días.

**Deploy.** Desde el VPS, en el repo: `git pull && docker compose up -d --build`. Compose reconstruye las imágenes cambiadas y reinicia con cero pérdida del volumen. Las migraciones de P0 corren al arrancar `api`. Primer arranque: crear `.env`, apuntar el DNS del dominio al VPS, `docker compose up -d` y esperar a que Caddy emita el cert.

**Conectar Claude Code al MCP por Tailscale (ADR-013).** El equipo del usuario debe estar en el **mismo tailnet** (Tailscale instalado y logueado). El MCP server es streamable-HTTP servido por el sidecar Tailscale en la **MagicDNS** del VPS (`https://quaestor-mcp.<tailnet>.ts.net/mcp`), no en el dominio público. En la config de MCP de Claude Code:
```jsonc
{ "mcpServers": {
  "quaestor": {
    "type": "http",
    "url": "https://quaestor-mcp.<tu-tailnet>.ts.net/mcp",
    "headers": { "Authorization": "Bearer <APP_TOKEN>" }
  }
}}
```
No hay shim stdio local: el cliente habla HTTPS al VPS **por la red privada del tailnet**, con el header de auth como segunda capa. **Trade-off:** clientes MCP en la nube (claude.ai web) no están en el tailnet → no alcanzan `/mcp`; si se necesitaran, se revisa la postura (ADR-013).

## Errores/Riesgos

- **"database is locked"** por dos escritores simultáneos (api + mcp) → mitigado con WAL + `busy_timeout`; si persiste, indica un escrito largo (revisar transacciones de P3 rollover, que deben ser cortas y atómicas).
- **WAL no incluido en un backup manual** → un `cp` crudo del `.db` sin checkpoint pierde datos del WAL. Por eso Litestream (sigue el WAL) o `sqlite3 .backup` (hace checkpoint), nunca `cp` en caliente.
- **`APP_TOKEN` o `.env` filtrados** → con `/mcp` ya fuera de internet (Tailscale), el token filtrado solo da acceso a la API pública; aun así rotar (cambiar env + reiniciar + actualizar config de Claude Code). `.env` fuera de git.
- **Sidecar Tailscale caído** → `/mcp` inalcanzable (el agente no opera), pero **nada se expone a internet**: falla cerrada, no abierta. Reiniciar `tailscale`; verificar `TS_AUTHKEY` válida.
- **API FX caída o sin respuesta** → el job diario no actualiza la tasa; el backend usa la **última vigente** y el `to_base` se congela igual. Override manual con `fijar_tasa_fx` si hace falta. No bloquea registros (ADR-011).
- **Cert no emite** (DNS mal apuntado, puerto 80 cerrado en el firewall del VPS) → Caddy reintenta; verificar `A`/`AAAA` del dominio y que `80/443` estén abiertos en el VPS.
- **Volumen borrado** (`docker compose down -v`) → pérdida de la DB. Documentar que `-v` destruye datos; la red de seguridad es Litestream.
- **Servicio expuesto por error** (`ports:` en api/mcp) → bypass de Caddy y del TLS. Solo `caddy` lleva `ports:`.
- **Restauración no probada** = backup inexistente. El criterio de listo exige restaurar de verdad.

## Testing y criterio de "listo"

Verificación manual (single-user, sin CI):
1. `docker compose up -d --build` levanta los **servicios** (api, mcp, frontend, caddy, tailscale, scheduler) y quedan `healthy`/`running` (`docker compose ps`).
2. `https://$DOMAIN/` sirve el **frontend por HTTPS** con cert válido (no warning de browser).
3. `curl -H "Authorization: Bearer $APP_TOKEN" https://$DOMAIN/api/accounts` responde 200; **sin** el header responde 401. **`https://$DOMAIN/mcp` NO responde** (no está enrutado en Caddy → confirma que `/mcp` no es público).
4. **Por Tailscale:** `curl https://quaestor-mcp.<tailnet>.ts.net/mcp ...` y, end-to-end, **Claude Code (en el tailnet) conecta** al `/mcp`, lista las tools y ejecuta una (p. ej. registrar un gasto). Un equipo **fuera del tailnet** no alcanza el endpoint.
5. **Scheduler:** tras una corrida hay tasa `usd_cop` para hoy en `FxRate`; y `ensure_mes_cerrado` deja el mes actual cerrado (recurrentes posteados/propuestos), siendo no-op en la segunda corrida (idempotente). `fijar_tasa_fx` manual sigue como override.
6. El volumen **persiste**: `docker compose restart` mantiene los datos.
7. **Backup restaurable:** `litestream restore` (o la copia diaria) reconstruye `quaestor.db` en un directorio limpio y el `api` arranca sobre esa DB con los datos intactos. (No es backup hasta que la restauración se prueba.)

"Listo" = los 7 puntos pasan.

## Integración con otros sub-proyectos

- **P0 Core:** provee `db.py` con **WAL** y `busy_timeout`, y corre migraciones al arrancar. P7 solo persiste el archivo y comparte el volumen.
- **P1 API + Auth:** define el servicio `api` y valida `APP_TOKEN`. P7 lo construye, lo expone solo en la red interna y lo enruta `/api/*` vía Caddy.
- **P2 MCP:** define el servicio `mcp` (streamable-HTTP) y su auth por bearer. P7 **no** lo enruta por Caddy: lo sirve el sidecar `tailscale` en el tailnet (ADR-013) y documenta cómo conecta Claude Code por la MagicDNS.
- **P3 Motor temporal:** sus escritos (rollover, confirmar pago) deben ser cortos/atómicos para no chocar con el single-writer; no requiere artefacto de deploy propio.
- **P4 / P5:** sin artefactos de deploy propios; viajan dentro de `api`/`mcp`. P5 (importer) puede generar escritos grandes (CSV bulk) → otra razón para WAL + `busy_timeout`.
- **P6 Frontend:** define el servicio `frontend`; P7 lo construye, lo enruta como catch-all en Caddy y le pasa `API_INTERNAL_URL=http://api:8000` (red interna) + el hash de contraseña.

**Convenciones transversales respetadas:** P7 no toca dinero, signo ni `posted`/`planned` (no manipula datos); su responsabilidad es que el **único `quaestor.db`** —fuente de verdad de todo el sistema— persista, esté protegido por token detrás de HTTPS, y sea respaldado y restaurable.

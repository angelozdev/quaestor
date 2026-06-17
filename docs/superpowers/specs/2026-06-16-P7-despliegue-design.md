# Quaestor — P7 Despliegue (sub-proyecto)

**Fecha:** 2026-06-16
**Depende de:** todos (P0, P1, P2, P3, P4, P5, P6) — empaqueta lo que ellos producen
**Parte de:** `2026-06-16-quaestor-general-design.md` (ver §4 Despliegue y auth, §3 Arquitectura)

---

## Objetivo

Poner Quaestor en línea: un **VPS self-hosted**, **single-user**, con dominio + HTTPS, donde corren los cuatro servicios (API, MCP, frontend, reverse proxy) detrás de Caddy. Que el browser sirva el frontend por HTTPS, que `curl` a la API con token responda, que Claude Code se conecte al `/mcp` remoto, y que la DB esté respaldada en continuo y sea restaurable. Nada corre en la laptop salvo el browser y el cliente MCP apuntando a la URL remota.

## Alcance

- `docker-compose.yml`: servicios `api`, `mcp`, `frontend`, `caddy`. La DB (`quaestor.db`) vive en un **volumen persistente compartido por `api` y `mcp`**.
- `Caddyfile`: un dominio, enrutado por path. HTTPS automático (Let's Encrypt).
- Variables de entorno (`.env`, no commiteado): `APP_TOKEN`, hash de contraseña del frontend, dominio, ruta de la DB, config de Litestream.
- Backups con **Litestream** (replicación continua a un bucket) + restauración; mínimo alterno: cron `sqlite3 .backup` diario.
- Pasos de deploy (`git pull && docker compose up -d --build`) y cómo conectar Claude Code al `/mcp` remoto.
- Postura de seguridad: nada expuesto sin token; solo Caddy publica 80/443.

**Fuera de alcance:** CI/CD, orquestación multi-nodo, alta disponibilidad, Postgres (el general lo deja como migración futura por connection string). Single-writer SQLite es suficiente para single-user.

## Aporte al modelo de datos

**Ninguno.** P7 no define entidades, campos ni migraciones. Solo empaqueta y despliega artefactos de P0–P6. Su única relación con los datos es operativa: **dónde vive** `quaestor.db` (volumen), **quién lo escribe** (api + mcp, un solo proceso a la vez en la práctica) y **cómo se respalda/restaura**. Las migraciones las corre el backend al arrancar (responsabilidad de P0); P7 solo garantiza que el archivo persista entre reinicios.

## Componentes

| Componente | Qué es | Imagen / base |
|---|---|---|
| `api` | FastAPI servido por uvicorn (P1), escucha `:8000` interno | Python 3.12 + uv |
| `mcp` | MCP streamable-HTTP (P2), escucha `:9000` interno | Python 3.12 + uv |
| `frontend` | Next.js App Router (P6), `:3000` interno | node, build standalone |
| `caddy` | Reverse proxy + HTTPS auto, único que publica `80/443` | `caddy:2` |
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
    ports: ["80:80", "443:443"]   # único servicio publicado
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on: [api, mcp, frontend]
    restart: unless-stopped
volumes:
  quaestor-data:
  caddy-data:
  caddy-config:
```

### `Caddyfile` (forma)
```caddy
{$DOMAIN} {
    encode gzip
    handle /api/* {
        reverse_proxy api:8000
    }
    handle /mcp* {
        reverse_proxy mcp:9000
    }
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

**HTTPS y red.** Solo `caddy` publica puertos al host (`80`, `443`). `api`/`mcp`/`frontend` usan `expose` (visibles solo en la red interna de Docker, no en el host). Todo tráfico externo entra por Caddy con TLS.

**Auth (resumen de §4 del general, P1/P2 lo implementan).** API y MCP exigen `Authorization: Bearer $APP_TOKEN`; sin token → 401. Caddy **no** termina la auth, solo enruta; el token lo valida el servicio destino. El frontend valida la contraseña (contra `FRONTEND_PASSWORD_HASH`) y guarda sesión; del lado servidor adjunta `APP_TOKEN` a sus llamadas a la API.

**Backups — Litestream (recomendado).** Replica `quaestor.db` en continuo (lee el WAL) a un bucket S3/R2/Backblaze. Config en `litestream.yml`:
```yaml
dbs:
  - path: /data/quaestor.db
    replicas:
      - url: ${LITESTREAM_BUCKET}
```
Restauración en limpio: `litestream restore -o /data/quaestor.db ${LITESTREAM_BUCKET}` antes de arrancar `api`/`mcp` (idealmente como paso de un entrypoint: si no existe la DB, restaurar; luego arrancar). **Mínimo alterno** si no hay bucket: cron diario `sqlite3 /data/quaestor.db ".backup /data/backups/quaestor-$(date +%F).db"` (usa la API de backup, segura en caliente) con retención de N días.

**Deploy.** Desde el VPS, en el repo: `git pull && docker compose up -d --build`. Compose reconstruye las imágenes cambiadas y reinicia con cero pérdida del volumen. Las migraciones de P0 corren al arrancar `api`. Primer arranque: crear `.env`, apuntar el DNS del dominio al VPS, `docker compose up -d` y esperar a que Caddy emita el cert.

**Conectar Claude Code al MCP remoto.** El MCP server es streamable-HTTP en `https://$DOMAIN/mcp`. En la config de MCP de Claude Code (laptop):
```jsonc
{ "mcpServers": {
  "quaestor": {
    "type": "http",
    "url": "https://quaestor.tudominio.com/mcp",
    "headers": { "Authorization": "Bearer <APP_TOKEN>" }
  }
}}
```
No hay shim stdio local: el cliente habla HTTPS directo al VPS con el header de auth.

## Errores/Riesgos

- **"database is locked"** por dos escritores simultáneos (api + mcp) → mitigado con WAL + `busy_timeout`; si persiste, indica un escrito largo (revisar transacciones de P3 rollover, que deben ser cortas y atómicas).
- **WAL no incluido en un backup manual** → un `cp` crudo del `.db` sin checkpoint pierde datos del WAL. Por eso Litestream (sigue el WAL) o `sqlite3 .backup` (hace checkpoint), nunca `cp` en caliente.
- **`APP_TOKEN` o `.env` filtrados** → acceso total single-user. `.env` fuera de git; rotar token si se sospecha fuga (cambiar env + reiniciar + actualizar la config de Claude Code).
- **Cert no emite** (DNS mal apuntado, puerto 80 cerrado en el firewall del VPS) → Caddy reintenta; verificar `A`/`AAAA` del dominio y que `80/443` estén abiertos en el VPS.
- **Volumen borrado** (`docker compose down -v`) → pérdida de la DB. Documentar que `-v` destruye datos; la red de seguridad es Litestream.
- **Servicio expuesto por error** (`ports:` en api/mcp) → bypass de Caddy y del TLS. Solo `caddy` lleva `ports:`.
- **Restauración no probada** = backup inexistente. El criterio de listo exige restaurar de verdad.

## Testing y criterio de "listo"

Verificación manual (single-user, sin CI):
1. `docker compose up -d --build` levanta los **4 servicios** y quedan `healthy`/`running` (`docker compose ps`).
2. `https://$DOMAIN/` sirve el **frontend por HTTPS** con cert válido (no warning de browser).
3. `curl -H "Authorization: Bearer $APP_TOKEN" https://$DOMAIN/api/accounts` responde 200; **sin** el header responde 401.
4. `curl https://$DOMAIN/mcp ...` y, end-to-end, **Claude Code conecta** al `/mcp` remoto, lista las tools y ejecuta una (p. ej. registrar un gasto).
5. El volumen **persiste**: `docker compose restart` mantiene los datos.
6. **Backup restaurable:** `litestream restore` (o la copia diaria) reconstruye `quaestor.db` en un directorio limpio y el `api` arranca sobre esa DB con los datos intactos. (No es backup hasta que la restauración se prueba.)

"Listo" = los 6 puntos pasan.

## Integración con otros sub-proyectos

- **P0 Core:** provee `db.py` con **WAL** y `busy_timeout`, y corre migraciones al arrancar. P7 solo persiste el archivo y comparte el volumen.
- **P1 API + Auth:** define el servicio `api` y valida `APP_TOKEN`. P7 lo construye, lo expone solo en la red interna y lo enruta `/api/*` vía Caddy.
- **P2 MCP:** define el servicio `mcp` (streamable-HTTP) y su auth por bearer. P7 lo enruta `/mcp*` y documenta cómo conecta Claude Code remoto.
- **P3 Motor temporal:** sus escritos (rollover, confirmar pago) deben ser cortos/atómicos para no chocar con el single-writer; no requiere artefacto de deploy propio.
- **P4 / P5:** sin artefactos de deploy propios; viajan dentro de `api`/`mcp`. P5 (importer) puede generar escritos grandes (CSV bulk) → otra razón para WAL + `busy_timeout`.
- **P6 Frontend:** define el servicio `frontend`; P7 lo construye, lo enruta como catch-all en Caddy y le pasa `API_INTERNAL_URL=http://api:8000` (red interna) + el hash de contraseña.

**Convenciones transversales respetadas:** P7 no toca dinero, signo ni `posted`/`planned` (no manipula datos); su responsabilidad es que el **único `quaestor.db`** —fuente de verdad de todo el sistema— persista, esté protegido por token detrás de HTTPS, y sea respaldado y restaurable.

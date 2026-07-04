# Quaestor Production Launch Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take Quaestor from "code-complete for P7" to "live, verified, backed up, taggable production deployment" on a single VPS.

**Architecture:** Pure operational plan; no new application code. Phases: (A) one small env-template patch, (B) secret generation on host, (C) infrastructure provisioning (VPS, DNS, bucket, tailnet), (D) first boot of the existing `docker-compose.yml` stack, (E) seven end-to-end verification checks from the P7 plan's Task 14 (the spec's "done" criteria, including the explicit restore drill required by ADR-0012), (F) tag + verification report commit.

**Tech Stack:** Docker + Compose v2 on Debian-slim VPS, Caddy 2 (auto-TLS via Let's Encrypt), Tailscale sidecar, Litestream → S3-compatible bucket (AWS S3 / Cloudflare R2 / Backblaze B2), SQLite WAL + busy_timeout, existing `quaestor-backend:latest` + `quaestor-frontend:latest` images.

## Global Constraints

These apply to **every** task.

- **ADR-0011 (network):** `/mcp` MUST NOT appear in the public Caddy listener. It is served ONLY by the Tailscale sidecar on the tailnet hostname. `mcp` service has no `ports:`. Public domain returns 404 on `/mcp`. Tailscale down → MCP unreachable, fail closed.
- **ADR-0012 (backups):** "An untested backup is no backup." Task 15 (restore drill) is non-optional; the deployment is not "done" until restore-from-bucket succeeds and accounts/transactions are observed intact.
- **ADR-0010 (single-VPS):** One host, no HA. `docker compose down -v` deletes the named volume and loses data — Litestream is the only safety net.
- **Secrets:** `.env` is gitignored, never committed. All secret material (APP_TOKEN, SESSION_SECRET, FRONTEND_PASSWORD_HASH, TS_AUTHKEY, LITESTREAM_*, ANTHROPIC_API_KEY, FX_API_KEY) is generated locally and stored in the operator's password manager; only non-secret values land in `.env` on the VPS.
- **Naming + copy:** All code, identifiers, comments, env var names, and runbook prose in English (ADR-0001). UI strings stay in their original language.
- **Commit cadence:** Every task that modifies tracked files ends in a commit. No "WIP" commits. No fixup commits inside a task.
- **Reuse, don't reinvent:** No new ADRs, no new files outside what's listed, no changes to `docker-compose.yml` / `Caddyfile` / `ts-serve.json` / `litestream.yml` / `Dockerfile`s. The infra is already specced (P7 plan tasks 6-12) and verified-dev (2026-06-22 report).

---

## Phase A — Env template patch

### Task 1: Add `ANTHROPIC_API_KEY` to root `.env.example`

The P7 deploy runbook (`docs/runbooks/deploy.md` step 7) references `ANTHROPIC_API_KEY` as a required prod env var for `/api/chat`, but the root `.env.example` only documents `DOMAIN`, `APP_TOKEN`, `SESSION_SECRET`, `FRONTEND_PASSWORD_HASH`, `DB_PATH`, `TS_AUTHKEY`, `FX_API_URL`, `FX_API_KEY`, `LITESTREAM_*`. The backend `.env.example` has it. Bring the root template in sync.

**Files:**
- Modify: `.env.example`

**Interfaces:**
- Produces: a new section in `.env.example` documenting `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `CHAT_MAX_ITERATIONS`, `CHAT_REQUEST_TIMEOUT_S` (same as backend `.env.example`, minus `ANTHROPIC_BASE_URL` which is internal).

- [ ] **Step 1: Append the chat env block to `.env.example`**

Open `.env.example` and append after the Litestream block:

```dotenv
# --- Chat endpoint (ADR-0014) -----------------------------------------
# Anthropic API key for /api/chat (never commit a real value).
ANTHROPIC_API_KEY=
# LiteLLM provider + model. Defaults shown; change only if using a non-Anthropic provider.
LLM_PROVIDER=litellm
LLM_MODEL=anthropic/claude-sonnet-4-6
CHAT_MAX_ITERATIONS=8
CHAT_REQUEST_TIMEOUT_S=120
```

- [ ] **Step 2: Verify the file still parses**

Run: `python3 -c "from dotenv import dotenv_values; print(sorted(dotenv_values('.env.example').keys()))"`
Expected: a sorted key list including `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `CHAT_MAX_ITERATIONS`, `CHAT_REQUEST_TIMEOUT_S`, plus all existing keys. No `ValueError`.

If `python-dotenv` is not installed, eyeball the file: each new line is `KEY=value` or a `#` comment; no syntax errors.

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "ops(env): document ANTHROPIC_API_KEY + chat settings in prod env template"
```

---

## Phase B — Secret generation (on operator machine)

### Task 2: Generate auth secrets and store in password manager

Generate the three operator-only secrets. None of these go to `.env.example` (those stay empty). Output goes to the operator's password manager (1Password / Bitwarden / keepassxc). The values are later pasted into the VPS `.env` file in Task 7.

**Files:** None. Operator action only.

**Interfaces:**
- Produces: three secret strings, each ≥ 32 bytes of entropy, recorded in the password manager under "Quaestor prod".

- [ ] **Step 1: Generate `APP_TOKEN`**

Run:
```bash
python3 -c "import secrets; print('APP_TOKEN=' + secrets.token_urlsafe(32))"
```
Expected: a single line `APP_TOKEN=<64-char-urlsafe>`. Save the value (not the line) under "Quaestor prod / APP_TOKEN".

- [ ] **Step 2: Generate `SESSION_SECRET`**

Run:
```bash
python3 -c "import secrets; print('SESSION_SECRET=' + secrets.token_urlsafe(32))"
```
Expected: another `SESSION_SECRET=<64-char-urlsafe>` line. Save under "Quaestor prod / SESSION_SECRET".

- [ ] **Step 3: Generate `FRONTEND_PASSWORD_HASH`**

Pick the operator password you'll type into the `/login` form (use a unique password; this gates the only public surface). Then:

```bash
python3 -c "from passlib.hash import bcrypt; print('FRONTEND_PASSWORD_HASH=' + bcrypt.hash('YOUR_CHOSEN_PASSWORD'))"
```
Expected: a line `FRONTEND_PASSWORD_HASH=$2b$12$...` (60-char bcrypt). Save both the chosen plaintext (under "Quaestor prod / frontend login password") and the hash (under "Quaestor prod / FRONTEND_PASSWORD_HASH").

If `passlib` is not installed:
```bash
uv tool run --from passlib passlib-cli hash --type bcrypt YOUR_CHOSEN_PASSWORD
```

- [ ] **Step 4: Verify no secret values are committed**

Run from the repo root:
```bash
grep -rn -E '(APP_TOKEN|SESSION_SECRET|FRONTEND_PASSWORD_HASH)=[^"$]' . \
  --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.git \
  --exclude-dir=.dev-data --exclude='*.md' --exclude='*.example' \
  --exclude='.env.local' --exclude='package-lock.json' || echo "OK: no live secrets in tracked files"
```
Expected: `OK: no live secrets in tracked files`. If anything prints, investigate before proceeding.

---

## Phase C — Infrastructure provisioning

### Task 3: Provision a VPS

Any Debian 12 / Ubuntu 24.04 VPS works. Minimum: 1 vCPU, 1 GB RAM, 20 GB SSD. Provider: Hetzner / DigitalOcean / Vultr / equivalent. Snapshot policy is the operator's choice; this plan assumes one exists or you accept the risk.

**Files:** None. Operator action + one Linux install + one firewall config.

**Interfaces:**
- Produces: a VPS reachable over SSH as `deploy@<VPS_IP>`, with Docker Engine + Compose v2 installed, ports 22/80/443 open, all other inbound ports closed.

- [ ] **Step 1: Create the VPS and note its public IPv4 + IPv6**

After creation, record `<VPS_IPv4>` and `<VPS_IPv6>` in the password manager under "Quaestor prod / VPS".

- [ ] **Step 2: Install Docker Engine + Compose v2**

SSH in:
```bash
ssh deploy@<VPS_IPv4>
```
Then run the official Docker install for Debian: https://docs.docker.com/engine/install/debian/. Confirm:
```bash
docker --version          # expected: Docker version 24+ (or whatever the script installed)
docker compose version    # expected: Docker Compose version v2.x
```

- [ ] **Step 3: Open 80 and 443, close everything else inbound**

Using the provider's firewall (cloud firewall panel) OR `ufw` on the host:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # Caddy HTTP-01 + ACME
sudo ufw allow 443/tcp     # Caddy HTTPS
sudo ufw enable
sudo ufw status verbose
```
Expected: `22`, `80`, `443` ALLOW IN; everything else DENY IN.

- [ ] **Step 4: Smoke-test SSH + Docker**

From your laptop (not the VPS):
```bash
ssh deploy@<VPS_IPv4> 'docker run --rm hello-world | tail -1'
```
Expected: a line containing `Hello from Docker!`. If it hangs, the firewall or Docker install is broken — fix before proceeding.

---

### Task 4: Configure DNS

Point a real domain at the VPS. Pick a domain you control (no need to be a fancy TLD; `.com`, `.net`, or even a subdomain of an existing domain works).

**Files:** None. DNS provider action.

**Interfaces:**
- Produces: an A record (and optionally AAAA) for `$DOMAIN` → `<VPS_IPv4>` (and `<VPS_IPv6>`), resolvable from the public internet.

- [ ] **Step 1: Create the A record**

In the DNS provider's panel:
- Host: `$DOMAIN` (e.g. `quaestor.example.com`)
- Type: A
- Value: `<VPS_IPv4>`
- TTL: 300 (5 min, so re-points are fast during testing)

If you have IPv6, also add an AAAA record with the IPv6 address.

- [ ] **Step 2: Verify propagation**

Run from your laptop:
```bash
dig +short $DOMAIN A
dig +short $DOMAIN AAAA   # if you added one
```
Expected: one or two lines containing the VPS IPs. If empty, wait 5 min and retry; if still empty after 30 min, the record is wrong.

- [ ] **Step 3: Verify the VPS responds**

```bash
curl -sI --resolve $DOMAIN:443:<VPS_IPv4> https://$DOMAIN/ -k | head -1
```
Expected: any response (probably connection refused or bad cert — Caddy isn't up yet). The point is DNS resolves.

---

### Task 5: Provision an S3-compatible bucket for Litestream

ADR-0012: backups go to S3 / R2 / Backblaze. Pick one; the runbook shows the same env vars for all three.

**Files:** None. Cloud-console action.

**Interfaces:**
- Produces: a bucket URL (`LITESTREAM_BUCKET=s3://<bucket>/<prefix>` or `s3://<bucket>`), plus `LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY`. For R2 / Backblaze, also `LITESTREAM_ENDPOINT=https://<accountid>.r2.cloudflarestorage.com`.

- [ ] **Step 1: Create the bucket**

Example for AWS S3:
```bash
aws s3api create-bucket --bucket quaestor-prod-backups --region us-east-1 \
  --create-bucket-configuration LocationConstraint=us-east-1
```
For R2 / Backblaze, use the provider's web UI. Name the bucket `quaestor-prod-backups` (or similar).

- [ ] **Step 2: Create a scoped access key**

Create an IAM user / R2 token / B2 application key with `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, `s3:DeleteObject` on this bucket only. Save under password manager:
- `LITESTREAM_ACCESS_KEY_ID`
- `LITESTREAM_SECRET_ACCESS_KEY`
- `LITESTREAM_BUCKET=s3://quaestor-prod-backups/quaestor.db`
- `LITESTREAM_ENDPOINT=` (empty for AWS S3; otherwise the provider endpoint)

- [ ] **Step 3: Smoke-test write + read**

From your laptop (with the AWS CLI configured for the new key):
```bash
echo "litestream-smoke-test" > /tmp/smoke.txt
aws s3 cp /tmp/smoke.txt s3://quaestor-prod-backups/smoke.txt
aws s3 cp s3://quaestor-prod-backups/smoke.txt - | cat
```
Expected: prints `litestream-smoke-test`. If not, the key lacks `s3:PutObject` or the bucket policy blocks it.

```bash
aws s3 rm s3://quaestor-prod-backups/smoke.txt
```
Clean up the test file.

---

### Task 6: Provision a Tailscale tailnet + reusable auth key

ADR-0011: `/mcp` lives on the tailnet only.

**Files:** None. Tailscale admin action.

**Interfaces:**
- Produces: a reusable auth key (`tskey-auth-...`) tagged so you can revoke it later. Also a tailnet name (`<tailnet>.ts.net`) the operator knows.

- [ ] **Step 1: Create the tailnet (if not already)**

Go to https://login.tailscale.com/admin/settings/keys. If the operator already has a tailnet, reuse it; otherwise create one (free personal plan is fine for single-user).

- [ ] **Step 2: Generate a reusable auth key**

In the keys page:
- Description: `quaestor-prod-mcp-sidecar`
- Reusable: ON (the sidecar may restart and re-auth)
- Ephemeral: OFF
- Pre-approved: ON
- Tags: `tag:quaestor` (optional; lets you scope ACLs later)

Copy the resulting `tskey-auth-...` value. Save under password manager as `TS_AUTHKEY`. Note your tailnet name (`<tailnet>` in `https://<TS_HOSTNAME>.<tailnet>.ts.net`).

- [ ] **Step 3: Pick a tailnet hostname**

The default is `quaestor-mcp`. Confirm `TS_HOSTNAME=quaestor-mcp` in the `.env` you'll create in Task 7, or pick another (e.g. `quaestor-prod`) — if you change it, edit `ts-serve.json` in the repo too (the JSON key is a literal string, not a runtime expansion; see the runbook note in `docs/runbooks/deploy.md`).

---

## Phase D — First deploy

### Task 7: Clone repo + populate `.env` on the VPS

**Files:**
- Modify: VPS-side `/root/quaestor/.env` (created, not committed).

**Interfaces:**
- Consumes: `APP_TOKEN`, `SESSION_SECRET`, `FRONTEND_PASSWORD_HASH` (from Task 2); `TS_AUTHKEY` (from Task 6); `LITESTREAM_*` (from Task 5); `DOMAIN`, `LETSENCRYPT_EMAIL` (from Tasks 4 + operator).
- Produces: a VPS-side `.env` with all values filled. The gitignored file is never committed.

- [ ] **Step 1: SSH in and clone**

```bash
ssh deploy@<VPS_IPv4>
sudo apt install -y git       # if not already
sudo git clone <REPO_URL> /root/quaestor
cd /root/quaestor
```
Expected: working tree clean.

- [ ] **Step 2: Copy `.env.example` to `.env`**

```bash
cp .env.example .env
chmod 600 .env
```

- [ ] **Step 3: Fill every secret in `.env`**

Open `.env` in your editor of choice (`nano`, `vim`, `vi`). Fill:
- `DOMAIN=$DOMAIN` (from Task 4)
- `LETSENCRYPT_EMAIL=` (your email; Let's Encrypt renewal notices)
- `APP_TOKEN=` (from Task 2)
- `SESSION_SECRET=` (from Task 2)
- `FRONTEND_PASSWORD_HASH=` (from Task 2)
- `TS_AUTHKEY=` (from Task 6)
- `TS_HOSTNAME=quaestor-mcp` (or your custom value; sync `ts-serve.json` if custom)
- `FX_API_URL=https://api.frankfurter.app/latest?base=USD&symbols=COP` (default; or your provider)
- `FX_API_KEY=` (empty if no key needed)
- `LITESTREAM_BUCKET=` (from Task 5)
- `LITESTREAM_ACCESS_KEY_ID=` (from Task 5)
- `LITESTREAM_SECRET_ACCESS_KEY=` (from Task 5)
- `LITESTREAM_ENDPOINT=` (empty for AWS; endpoint URL otherwise)
- `ANTHROPIC_API_KEY=` (operator's Anthropic key — save under "Quaestor prod / ANTHROPIC_API_KEY")
- `LLM_PROVIDER=litellm`
- `LLM_MODEL=anthropic/claude-sonnet-4-6`
- `CHAT_MAX_ITERATIONS=8`
- `CHAT_REQUEST_TIMEOUT_S=120`

Save. Verify no placeholders remain:
```bash
grep -nE '=$|^[A-Z_]+=$' .env
```
Expected: no lines print (every variable has a value or a comment).

- [ ] **Step 4: Validate the compose file**

```bash
docker compose config -q
```
Expected: exit 0 (silent). If it errors, the most common cause is a `$VAR` in `docker-compose.yml` with no value in `.env` — go back to step 3.

---

### Task 8: First boot — bring the stack up

**Files:** None. Docker Compose command only.

**Interfaces:**
- Produces: 7 services (`api`, `mcp`, `frontend`, `caddy`, `tailscale`, `litestream`, `scheduler`) running, Caddy holding a Let's Encrypt cert for `$DOMAIN`.

- [ ] **Step 1: Build and start**

```bash
cd /root/quaestor
docker compose up -d --build
```
Expected: `Network quaestor_default` Created, 7 services `Started`. Build may take 1-3 minutes (cold cache).

- [ ] **Step 2: Watch Caddy get the cert**

```bash
docker compose logs -f caddy
```
Expected within ~30s: a line containing `obtained certificate` and `for $DOMAIN`. If you see `error getting challenge` or `acme: error`, the most common cause is DNS not propagated yet — wait, re-dig, and re-try `docker compose restart caddy`.

Press Ctrl-C after the cert line appears.

- [ ] **Step 3: Confirm all services are running**

```bash
docker compose ps
```
Expected: 7 rows. `api`, `mcp`, `frontend` show `healthy`; `caddy`, `tailscale`, `litestream`, `scheduler` show `running` (no healthcheck). State should not be `Exit` or `Restarting`.

If anything is `Restarting`:
```bash
docker compose logs <service-name> --tail=50
```
Fix the error before continuing.

---

## Phase E — End-to-end verification (P7 Task 14, 7 checks)

### Task 9: Check 1 — services healthy

Already partially done by Task 8 Step 3, but formalize.

**Files:** None. Verification only.

- [ ] **Step 1: Run the full health snapshot**

```bash
docker compose ps --format json | jq -r '.[] | "\(.Name)\t\(.State)\t\(.Health)"'
```
Expected output (7 rows, tab-separated):
```
quaestor-api	running	healthy
quaestor-mcp	running	healthy
quaestor-frontend	running	healthy
quaestor-caddy	running	(none)
quaestor-tailscale	running	(none)
quaestor-litestream	running	(none)
quaestor-scheduler	running	(none)
```
If `jq` is not installed, use plain `docker compose ps` and eyeball.

- [ ] **Step 2: Record the output**

Append to `docs/superpowers/reports/prod-launch-2026-06-25.md` (create the file):
```
## Check 1: services healthy
<output of step 1>
```

---

### Task 10: Check 2 — public HTTPS frontend

**Files:** None. Verification only.

- [ ] **Step 1: curl the public root**

From your laptop (not the VPS):
```bash
curl -sI https://$DOMAIN/ | head -1
```
Expected: `HTTP/2 200`. If `connection refused`, Caddy isn't bound to 443 yet — check `docker compose logs caddy`. If `SSL handshake failed`, the cert isn't issued yet — wait 30s and retry. If `HTTP/2 308` or other redirect, that's fine for the root if the frontend redirects to `/login`; record whatever you got.

- [ ] **Step 2: Verify the cert chain**

```bash
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -subject -issuer
```
Expected: `subject=CN = $DOMAIN` and `issuer=O = Let's Encrypt, CN = R10` (or `R11`, depending on date).

- [ ] **Step 3: Record**

Append to the report:
```
## Check 2: public HTTPS frontend
curl status: <code>
cert subject/issuer: <lines>
```

---

### Task 11: Check 3 — public API auth + `/mcp` not public

**Files:** None. Verification only.

- [ ] **Step 1: API with valid bearer**

From your laptop:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $APP_TOKEN" https://$DOMAIN/api/accounts
```
Expected: `200` (empty list is fine; account count is 0 on a fresh DB).

- [ ] **Step 2: API without bearer**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://$DOMAIN/api/accounts
```
Expected: `401`.

- [ ] **Step 3: `/mcp` must NOT respond on the public domain**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://$DOMAIN/mcp
```
Expected: `404` (Caddy matches `@chat path /api/chat*` and returns 404 for `/mcp`; if not, the Caddyfile is wrong and ADR-0011 is violated — fix before continuing).

- [ ] **Step 4: `/api/chat` also returns 404 on the public listener**

ADR-0014: chat is tailnet-only.
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://$DOMAIN/api/chat
```
Expected: `404`.

- [ ] **Step 5: Record**

Append to the report:
```
## Check 3: public API + /mcp not public
/api/accounts (with bearer): <code>
/api/accounts (no bearer):   <code>
/mcp on $DOMAIN:             <code>
/api/chat on $DOMAIN:        <code>
```

---

### Task 12: Check 4 — tailnet `/mcp` reachable from tailnet, fail-closed from outside

**Files:** None. Verification only, requires a machine on the tailnet.

- [ ] **Step 1: From a machine on the tailnet, reach `/mcp`**

From your laptop (which you should have joined to the tailnet via Tailscale before this step):
```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $APP_TOKEN" \
  https://quaestor-mcp.<YOUR_TAILNET>.ts.net/mcp
```
Expected: `400` or `405` (the MCP protocol responds to a bare GET with a 4xx — anything except a connection error is good). `200` is also fine if you sent a valid JSON-RPC body. A `connection refused` / timeout means Tailscale serve isn't wired — re-check `ts-serve.json` and `tailscale` container logs.

- [ ] **Step 2: From a machine NOT on the tailnet, `/mcp` must be unreachable**

If you have a non-tailnet VPS or a phone with Tailscale off:
```bash
curl -s --max-time 10 -o /dev/null -w "%{http_code}\n" \
  https://quaestor-mcp.<YOUR_TAILNET>.ts.net/mcp
```
Expected: exit code 28 (timeout) or `000` (could not connect). Anything other than a clean 4xx response is the correct fail-closed behavior.

- [ ] **Step 3: Record**

Append to the report:
```
## Check 4: tailnet /mcp
from tailnet: <code>
from outside: <code or timeout>
```

---

### Task 13: Check 5 — scheduler runs end-to-end (idempotent)

**Files:** None. Verification only.

- [ ] **Step 1: First scheduler run**

On the VPS:
```bash
docker compose exec scheduler uv run python -m quaestor.jobs.daily
```
Expected: a single JSON line like
```
{"fx_error": null, "fx_rate": "4150.50", "materialized_count": 0, "month_closed": "2026-06"}
```
(or with `materialized_count > 0` if a recurring item is due today; or with `fx_error` set if the FX provider is down — both are OK; what matters is that the call exited 0).

- [ ] **Step 2: Second scheduler run (idempotency proof)**

Immediately again:
```bash
docker compose exec scheduler uv run python -m quaestor.jobs.daily
```
Expected: same shape of JSON; `materialized_count == 0`; same `month_closed`. A re-run on the same day is a no-op (ADR-0013).

- [ ] **Step 3: Verify the FX rate landed in the DB**

```bash
docker compose exec api uv run python -c "
from quaestor import db
from sqlmodel import Session, select
from quaestor.domain.models import FxRate
with Session(db.engine) as s:
    rows = s.exec(select(FxRate).order_by(FxRate.date.desc()).limit(3)).all()
    for r in rows:
        print(r.date, r.usd_cop)
"
```
Expected: at least one row printed with today's date and a non-zero `usd_cop`.

- [ ] **Step 4: Record**

Append to the report:
```
## Check 5: scheduler
run 1: <json line>
run 2: <json line>
last FX row: <date> <rate>
```

---

### Task 14: Check 6 — volume persists across restart

**Files:** None. Verification only.

- [ ] **Step 1: Record a sentinel**

On the VPS:
```bash
docker compose exec api uv run python -c "
from quaestor import db
from sqlmodel import Session, select
from quaestor.domain.models import Account
with Session(db.engine) as s:
    rows = s.exec(select(Account)).all()
    print('accounts_before:', len(rows))
"
```
Expected: a number ≥ 0 printed.

- [ ] **Step 2: Restart the whole stack**

```bash
docker compose restart
```
Expected: all 7 services come back to `running`/`healthy` within ~30s.

- [ ] **Step 3: Re-check the sentinel**

```bash
docker compose exec api uv run python -c "
from quaestor import db
from sqlmodel import Session, select
from quaestor.domain.models import Account
with Session(db.engine) as s:
    rows = s.exec(select(Account)).all()
    print('accounts_after:', len(rows))
"
```
Expected: same number as Step 1. If lower, the volume wasn't mounted — investigate before continuing.

- [ ] **Step 4: Record**

Append to the report:
```
## Check 6: volume persists
accounts_before: <n>
accounts_after: <n>
```

---

### Task 15: Check 7 — restore drill (ADR-0012 explicit requirement)

This is the most important check. "A backup is not a backup until restore is tested." We restore from the Litestream bucket into a temporary location, mount it in a fresh `quaestor-backend` container, and confirm accounts/transactions are intact.

**Files:** None. Verification only.

- [ ] **Step 1: Confirm Litestream has actually replicated something to the bucket**

```bash
aws s3 ls s3://$LITESTREAM_BUCKET/ --recursive | head -20
# (for AWS; for R2/B2 substitute the equivalent)
```
Expected: at least one entry like `YYYY/MM/DD/HHMMSS.wal` or `generations/<generation>/snapshot.YYYY-MM-DDTHHMMSSZ.db` or similar. If empty, wait 5 minutes (Litestream's initial snapshot interval is 24h per `litestream.yml`, but WAL streams immediately) and re-check.

If still empty after 5 min:
```bash
docker compose logs litestream --tail=30
```
Fix the Litestream config or credentials before proceeding.

- [ ] **Step 2: Stop the stack so the live DB isn't being written**

```bash
docker compose down
```
Expected: all 7 containers stopped; the `quaestor-data` named volume still exists (verify with `docker volume ls | grep quaestor`).

- [ ] **Step 3: Restore the bucket to a fresh directory**

```bash
mkdir -p /tmp/quaestor-restore
docker run --rm \
  -v /tmp/quaestor-restore:/data \
  -e LITESTREAM_BUCKET \
  -e LITESTREAM_ACCESS_KEY_ID \
  -e LITESTREAM_SECRET_ACCESS_KEY \
  -e LITESTREAM_ENDPOINT \
  --env-file /root/quaestor/.env \
  litestream/litestream:latest \
  restore -o /data/quaestor.db "$LITESTREAM_BUCKET"
```
Expected: a line containing `restored` (Litestream's restore summary). Verify the file is there:
```bash
ls -la /tmp/quaestor-restore/quaestor.db
```
Expected: a non-zero file. If 0 bytes, the bucket path is wrong (check `$LITESTREAM_BUCKET`).

- [ ] **Step 4: Verify the -wal and -shm siblings are also restored**

```bash
ls -la /tmp/quaestor-restore/
```
Expected: `quaestor.db`, `quaestor.db-wal`, `quaestor.db-shm` all present and non-zero. Litestream restore writes all three; if only `quaestor.db` is present, the restore was a checkpoint snapshot without WAL, which is also acceptable for a recent snapshot.

- [ ] **Step 5: Mount the restored DB in a temporary container and inspect**

```bash
docker compose run --rm \
  -v /tmp/quaestor-restore:/data \
  -e QUAESTOR_DB=sqlite:////data/quaestor.db \
  -e APP_TOKEN=any \
  api \
  uv run python -c "
from quaestor import db
from sqlmodel import Session, select
from quaestor.domain.models import Account, Transaction
with Session(db.engine) as s:
    accs = s.exec(select(Account)).all()
    txs  = s.exec(select(Transaction)).all()
    print(f'accounts: {len(accs)}, transactions: {len(txs)}')
    for a in accs[:5]:
        print(f'  {a.name} balance={a.balance}')
"
```
Expected: counts printed; balance sums should match what you saw in Task 14 Step 1 (post-restart count).

- [ ] **Step 6: Compare counts to the live pre-restart snapshot**

If you recorded the pre-restart account count from Task 14, the restored count should be ≥ that number (newer writes may have happened if anything was scheduled, but for a fresh deploy it should be equal).

- [ ] **Step 7: Bring the stack back up**

```bash
rm -rf /tmp/quaestor-restore
docker compose up -d
```
Expected: same 7 services back to `running`/`healthy`.

- [ ] **Step 8: Record**

Append to the report:
```
## Check 7: restore drill
litestream replicas found: <list-summary>
restored DB size: <bytes>
-wal / -shm present: yes/no
accounts in restored DB: <n>
transactions in restored DB: <n>
matches live DB: yes/no
```

---

## Phase F — Close-out

### Task 16: Tag v0.7.0

**Files:** None (git operation only).

- [ ] **Step 1: Tag on the VPS or your laptop**

From the repo root (on the machine with the cleanest working tree):
```bash
git tag -a v0.7.0 -m "P7 deployment shipped: prod stack live and verified"
git push origin v0.7.0
```
Expected: tag visible at `https://<your-git-host>/<owner>/quaestor/releases/tag/v0.7.0` (or via `git ls-remote --tags origin | grep v0.7.0`).

- [ ] **Step 2: Verify the tag points at the right commit**

```bash
git show v0.7.0 --stat | head -20
```
Expected: the most recent commit plus the tag message.

---

### Task 17: Commit the P7 verification report

The report started in Task 9 and grew with each check. Commit it now.

**Files:**
- Create: `docs/superpowers/reports/prod-launch-2026-06-25.md`
- Modify (final): same file, after appending a closing summary.

- [ ] **Step 1: Append a closing summary to the report**

Open `docs/superpowers/reports/prod-launch-2026-06-25.md` and append:

```markdown
## Summary

| # | Check | Result |
|---|---|---|
| 1 | Services healthy | PASS / FAIL |
| 2 | Public HTTPS frontend | PASS / FAIL |
| 3 | Public API auth + /mcp 404 | PASS / FAIL |
| 4 | Tailnet /mcp reachable + fail-closed | PASS / FAIL |
| 5 | Scheduler runs (idempotent) | PASS / FAIL |
| 6 | Volume persists across restart | PASS / FAIL |
| 7 | Restore drill (Litestream) | PASS / FAIL |

Deployment: v0.7.0, VPS <IP>, $DOMAIN, tailnet <tailnet>.ts.net
Date: 2026-06-25
Verifier: <operator name>
```

Fill in `PASS` / `FAIL` from the actual results.

- [ ] **Step 2: Commit the report**

```bash
git add docs/superpowers/reports/prod-launch-2026-06-25.md
git commit -m "ops: P7 production verification report (7/7 checks)"
```
Expected: commit created with the report file as its sole change.

- [ ] **Step 3: Bump the tag if any check failed**

If any check failed, do NOT tag v0.7.0 (Task 16 was conditional). Instead:
- Open an issue / branch with the failing check's diagnosis.
- Re-run that single check after the fix; update the report.
- Tag only when all 7 are PASS.

---

## Self-Review

**1. Spec coverage (P7 §Testing + ADR-0012 + deploy runbook):**
- Spec §Testing point 1 (services healthy) → Task 9. ✓
- Spec §Testing point 2 (HTTPS frontend reachable) → Task 10. ✓
- Spec §Testing point 3 (API with/without bearer, /mcp 404) → Task 11. ✓
- Spec §Testing point 4 (tailnet /mcp reachable + fail-closed) → Task 12. ✓
- Spec §Testing point 5 (scheduler idempotent) → Task 13. ✓
- Spec §Testing point 6 (volume persists) → Task 14. ✓
- Spec §Testing point 7 + ADR-0012 (restore tested) → Task 15. ✓
- Deploy runbook step 3 (`ANTHROPIC_API_KEY` referenced but missing from `.env.example`) → Task 1. ✓
- "Done" criterion: tag → Task 16. ✓
- "Done" criterion: report → Task 17. ✓

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later". Every step has literal commands, expected outputs, and explicit pass/fail criteria. No "add validation" hand-waves.

**3. Type / name / URL consistency:**
- `$DOMAIN` used everywhere the public host appears; `<VPS_IPv4>`, `<VPS_IPv6>`, `<YOUR_TAILNET>` are placeholder variables the operator substitutes once.
- `$APP_TOKEN` matches the var name in `.env.example` and `docker-compose.yml`.
- `$LITESTREAM_BUCKET` matches `litestream.yml`.
- `quaestor-mcp` is the default tailnet hostname; if the operator changes it, `ts-serve.json` and `.env` must be updated together (cross-referenced in Task 6 Step 3 and Task 7 Step 3).
- `quaestor-prod-backups` is a placeholder bucket name; operator substitutes in Task 5 and uses the same value in Task 7 Step 3.

**4. Risks / non-blockers:**
- Some verifications depend on operator-side machines (Tailscale-joined laptop, AWS CLI installed). The plan assumes these exist or the operator can install them.
- The FX rate depends on the chosen provider being reachable from the VPS. If `FX_API_URL` is wrong, the scheduler still runs (ADR-0011 says FX failures are non-fatal) but `fx_error` will be set in the report — that is still a PASS for Check 5.
- The `prod` build of the backend image depends on `uv sync --frozen --no-dev` succeeding, which depends on `pyproject.toml` + `uv.lock` being in sync. This was verified in the dev environment; if the prod build fails, the operator must `uv lock` locally and commit the result before re-running Task 8.

**5. ADR / design drift:** None. Plan touches only `.env.example` (Task 1) for code; everything else is operator-side actions against the existing files. No ADR supersession required.
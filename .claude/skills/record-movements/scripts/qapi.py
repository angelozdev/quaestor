#!/usr/bin/env python3
"""Talk to the running Quaestor API, with auth and CSRF already handled.

Every state-changing request needs a bearer token AND a matching CSRF
header/cookie pair, so hand-rolling curl for each call is where the mistakes
live. This wraps that once.

Usage:
    python3 .claude/skills/record-movements/scripts/qapi.py context
    python3 .claude/skills/record-movements/scripts/qapi.py balances
    python3 .claude/skills/record-movements/scripts/qapi.py movements 5 --status posted --limit 10
    python3 .claude/skills/record-movements/scripts/qapi.py precedents uber "cc san diego"
    python3 .claude/skills/record-movements/scripts/qapi.py call GET /transactions/1642
    python3 .claude/skills/record-movements/scripts/qapi.py call POST /transactions --data '{...}'
    python3 .claude/skills/record-movements/scripts/qapi.py batch movimientos.json
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ENV_FILE = REPO_ROOT / "backend" / ".env.local.postgres"
DEFAULT_BASE_URL = "http://localhost:8000/api"
SAFE_METHODS = frozenset({"GET", "HEAD"})


class ApiError(RuntimeError):
    """A non-2xx answer from the API, carrying the body the server sent."""


def read_token(env_file: Path) -> str:
    if not env_file.exists():
        raise SystemExit(f"env file not found: {env_file}")
    for line in env_file.read_text().splitlines():
        if line.startswith("APP_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit(f"APP_TOKEN not found in {env_file}")


def request(method: str, path: str, token: str, base_url: str, body: dict | list | None = None):
    method = method.upper()
    url = f"{base_url}{path if path.startswith('/') else '/' + path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if method not in SAFE_METHODS:
        csrf = secrets.token_hex(24)
        req.add_header("X-CSRF-Token", csrf)
        req.add_header("Cookie", f"quaestor_csrf={csrf}")
    try:
        with urllib.request.urlopen(req) as response:
            payload = response.read().decode()
            return json.loads(payload) if payload.strip() else None
    except urllib.error.HTTPError as exc:
        raise ApiError(f"{method} {path} -> {exc.code} {exc.read().decode()[:400]}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"cannot reach {base_url} — is the stack up? ({exc.reason})") from exc


def money(cents: int, currency: str = "COP") -> str:
    return f"{cents / 100:,.2f} {currency}"


def cmd_context(token: str, base_url: str) -> None:
    accounts = request("GET", "/accounts", token, base_url)
    print("== ACCOUNTS ==")
    for a in accounts:
        flag = " [archived]" if a["archived"] else ""
        print(f"  {a['id']:>3}  {a['name']:<28} {a['type']:<8} {money(a['balance'], a['currency']):>22}{flag}")

    categories = request("GET", "/categories", token, base_url)
    print("\n== CATEGORIES ==")
    for c in categories:
        direction = "INCOME " if c["is_income"] else "expense"
        flags = " [excluded from totals]" if c["exclude_from_totals"] else ""
        print(f"  {c['id']:>3}  {direction}  {c['name']}{flags}")

    recurring = request("GET", "/recurring", token, base_url)
    print("\n== RECURRING ==")
    for r in sorted(recurring, key=lambda r: (r["account_id"], r["id"])):
        every = f"every {r['interval_count']} {r['interval_unit']}"
        print(
            f"  {r['id']:>3}  {r['name']:<24} {r['payee']:<22} "
            f"{money(r['amount'], r['currency']):>18}  cat {r['category_id']}  acct {r['account_id']}  {every}"
        )


def cmd_balances(token: str, base_url: str) -> None:
    for a in request("GET", "/accounts", token, base_url):
        print(f"{a['id']:>3}  {a['name']:<28} {money(a['balance'], a['currency']):>22}")


def cmd_movements(args, token: str, base_url: str) -> None:
    query = [f"account_id={args.account_id}", "sort=date", "order=desc"]
    if args.status:
        query.append(f"status={args.status}")
    if args.date_from:
        query.append(f"date_from={args.date_from}")
    if args.date_to:
        query.append(f"date_to={args.date_to}")
    rows = request("GET", "/transactions?" + "&".join(query), token, base_url)
    for t in rows[: args.limit]:
        kind = t["type"][:3]
        direction = f" {t['transfer_direction']}" if t["transfer_direction"] else ""
        note = f"  | {t['notes']}" if t["notes"] else ""
        print(
            f"{t['id']:>5}  {t['date']}  {t['status'][:7]:<7} {money(t['amount'], t['currency']):>20}  "
            f"cat {str(t['category_id'] or '-'):<3} {kind}{direction}  {t['payee']}{note}"
        )
    print(f"-- {min(len(rows), args.limit)} shown of {len(rows)} matching")


def cmd_precedents(args, token: str, base_url: str) -> None:
    rows = request("GET", "/transactions?sort=date&order=desc", token, base_url)
    for term in args.terms:
        needle = term.lower()
        hits = [
            t
            for t in rows
            if needle in (t["payee"] or "").lower() or needle in (t["notes"] or "").lower()
        ]
        print(f"\n== {term} — {len(hits)} matches ==")
        if not hits:
            print("  (no precedent — this payee is new, ask the owner what it is)")
            continue
        tally = Counter((t["category_id"], t["type"]) for t in hits)
        for (cat, kind), n in tally.most_common():
            print(f"  {n:>3}x  cat {str(cat or '-'):<4} {kind}")
        for t in hits[:4]:
            note = f"  | {t['notes']}" if t["notes"] else ""
            print(
                f"    {t['id']:>5}  {t['date']}  {money(t['amount'], t['currency']):>18}  "
                f"acct {t['account_id']}  cat {t['category_id'] or '-'}  {t['payee']}{note}"
            )


def cmd_call(args, token: str, base_url: str) -> None:
    body = json.loads(args.data) if args.data else None
    result = request(args.method, args.path, token, base_url, body)
    print(json.dumps(result, ensure_ascii=False, indent=2) if result is not None else "(204 no content)")


def cmd_batch(args, token: str, base_url: str) -> None:
    steps = json.loads(Path(args.file).read_text())
    if not isinstance(steps, list):
        raise SystemExit("batch file must hold a JSON array of {method, path, body}")
    done, failed = 0, 0
    for i, step in enumerate(steps, start=1):
        label = step.get("label") or f"{step['method']} {step['path']}"
        try:
            result = request(step["method"], step["path"], token, base_url, step.get("body"))
        except ApiError as exc:
            failed += 1
            print(f"  {i:>3}  FAILED  {label}\n         {exc}")
            if not args.keep_going:
                print(f"\nstopped at step {i}. {done} written, {failed} failed.")
                sys.exit(1)
            continue
        done += 1
        new_id = result.get("id") if isinstance(result, dict) else None
        print(f"  {i:>3}  ok  {'id ' + str(new_id) if new_id else ''}  {label}")
    print(f"\n{done} written, {failed} failed, {len(steps)} total.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("context", help="accounts, categories and recurring items in one read")
    sub.add_parser("balances", help="balance per account")

    movements = sub.add_parser("movements", help="movements of one account, newest first")
    movements.add_argument("account_id", type=int)
    movements.add_argument("--status", choices=["posted", "planned", "skipped"])
    movements.add_argument("--from", dest="date_from")
    movements.add_argument("--to", dest="date_to")
    movements.add_argument("--limit", type=int, default=20)

    precedents = sub.add_parser("precedents", help="how this payee was categorised before")
    precedents.add_argument("terms", nargs="+")

    call = sub.add_parser("call", help="any endpoint, auth and CSRF handled")
    call.add_argument("method")
    call.add_argument("path")
    call.add_argument("--data")

    batch = sub.add_parser("batch", help="run a JSON array of {method, path, body, label}")
    batch.add_argument("file")
    batch.add_argument("--keep-going", action="store_true", help="do not stop at the first failure")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    token = read_token(args.env_file)
    try:
        if args.command == "context":
            cmd_context(token, args.base_url)
        elif args.command == "balances":
            cmd_balances(token, args.base_url)
        elif args.command == "movements":
            cmd_movements(args, token, args.base_url)
        elif args.command == "precedents":
            cmd_precedents(args, token, args.base_url)
        elif args.command == "call":
            cmd_call(args, token, args.base_url)
        elif args.command == "batch":
            cmd_batch(args, token, args.base_url)
    except ApiError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()

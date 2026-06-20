#!/usr/bin/env python3
"""Create a new technical ADR from the template and register it in the index.

Usage:
    uv run .claude/skills/adr/scripts/new_adr.py "Use Alembic for migrations"
"""
from __future__ import annotations

import datetime as _dt
import re
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent          # .claude/skills/adr
REPO_ROOT = SKILL_DIR.parents[2]                            # repo root
TEMPLATE_PATH = SKILL_DIR / "TEMPLATE.md"
ADR_DIR = REPO_ROOT / "docs" / "adr"
README_PATH = ADR_DIR / "README.md"


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_str = re.sub(r"[^a-z0-9]+", "-", ascii_str)
    return ascii_str.strip("-")


def next_number(adr_dir: Path) -> str:
    numbers = [int(p.name[:4]) for p in adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")]
    nxt = (max(numbers) + 1) if numbers else 1
    return f"{nxt:04d}"


def render_template(template_path: Path, number: str, title: str, date: str) -> str:
    text = template_path.read_text(encoding="utf-8")
    text = text.replace("NNNN", number)
    text = text.replace("<short title of the decision>", title)
    text = text.replace("YYYY-MM-DD", date)
    return text


def create_adr(
    title: str, adr_dir: Path, template_path: Path, date: str
) -> tuple[str, Path]:
    slug = slugify(title)
    existing = list(adr_dir.glob(f"[0-9][0-9][0-9][0-9]-{slug}.md"))
    if existing:
        raise SystemExit(f"An ADR with slug '{slug}' already exists: {existing[0]}")
    number = next_number(adr_dir)
    target = adr_dir / f"{number}-{slug}.md"
    target.write_text(
        render_template(template_path, number, title, date), encoding="utf-8"
    )
    return number, target


def update_index(
    readme_path: Path, number: str, title: str, status: str, date: str
) -> None:
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    row = f"| {number} | {title} | {status} | {date} |"
    last_table_idx = None
    for i, line in enumerate(lines):
        if line.startswith("|"):
            last_table_idx = i
    if last_table_idx is None:
        lines.append(row)
    else:
        lines.insert(last_table_idx + 1, row)
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    if len(argv) < 2 or not argv[1].strip():
        raise SystemExit('Usage: new_adr.py "<title>"')
    title = argv[1].strip()
    date = _dt.date.today().isoformat()
    number, target = create_adr(title, ADR_DIR, TEMPLATE_PATH, date)
    update_index(README_PATH, number, title, "proposed", date)
    print(target)


if __name__ == "__main__":
    main(sys.argv)

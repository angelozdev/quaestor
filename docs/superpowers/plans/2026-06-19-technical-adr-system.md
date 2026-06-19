# Technical ADR System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Quaestor a complete, versioned system for recording technical/architecture decisions (ADRs) — separate from the existing product-decision log — with a deterministic scaffolding script and an always-on guardrail so agents record and respect decisions instead of improvising.

**Architecture:** A project-level skill at `quaestor/.claude/skills/adr/` (SKILL.md + TEMPLATE.md + scripts/new_adr.py) drives the workflow. Technical ADRs live one-file-per-decision in `docs/adr/NNNN-slug.md` with a `README.md` index. A root `CLAUDE.md` rule points agents to the skill. The existing product file moves to `docs/decisions/product-decisions.md`.

**Tech Stack:** Python 3.12 (stdlib only) run via `uv`, Markdown, Claude Code skill format.

## Global Constraints

- Skill content and all ADR content are written in **English**. (User-facing chat is Spanish, but artifacts are English.)
- Script is **Python 3.12, standard library only** — no third-party imports.
- ADR numbering: **4-digit zero-padded** (`0001`), **stable — never renumber**; gaps from rejected ADRs are kept.
- Slugs are **ASCII, lowercase, hyphen-separated**, accents stripped.
- The product decision file content stays **byte-for-byte intact**; only its path changes.
- Work happens on branch `docs/adr-system` (already created). Commit after each task.
- Run from repo root: `/Users/angelozdev/me/quaestor`.

---

### Task 1: Migrate product file + scaffold ADR folders and index

**Files:**
- Move: `docs/adr/2026-06-16-quaestor-adrs.md` → `docs/decisions/product-decisions.md`
- Modify: `docs/superpowers/specs/2026-06-16-quaestor-general-design.md` (lines 29, 31, 35 — path references)
- Create: `docs/adr/README.md`

**Interfaces:**
- Produces: `docs/adr/README.md` with a Markdown table whose header separator row is `|------|-------|--------|------|` — `scripts/new_adr.py` (Task 3) appends rows immediately after the last table line.

- [ ] **Step 1: Move the product file with git mv (creates docs/decisions/)**

Run:
```bash
mkdir -p docs/decisions
git mv docs/adr/2026-06-16-quaestor-adrs.md docs/decisions/product-decisions.md
```
Expected: file moved; `docs/adr/` no longer contains the product file.

- [ ] **Step 2: Verify the move**

Run:
```bash
ls docs/decisions/product-decisions.md && ls docs/adr/2026-06-16-quaestor-adrs.md 2>&1 || echo "OLD PATH GONE (good)"
```
Expected: new path lists; old path prints "OLD PATH GONE (good)".

- [ ] **Step 3: Update the 3 path references in the general design spec**

In `docs/superpowers/specs/2026-06-16-quaestor-general-design.md`, replace the 3 occurrences so links point to the new location:
- Lines 29 and 31: `../../adr/2026-06-16-quaestor-adrs.md` → `../../decisions/product-decisions.md`
- Line 35: `docs/adr/2026-06-16-quaestor-adrs.md` → `docs/decisions/product-decisions.md`

- [ ] **Step 4: Verify no stale references remain (outside the new specs)**

Run:
```bash
grep -rn "adr/2026-06-16-quaestor-adrs" --include="*.md" . | grep -v "2026-06-19-technical-adr-system-design.md"
```
Expected: no output (the only remaining mentions are inside the design spec from 2026-06-19, which intentionally describe the move).

- [ ] **Step 5: Create the ADR index**

Create `docs/adr/README.md`:
```markdown
# Architecture Decision Records (technical)

Technical and architecture decisions for Quaestor. Each decision is one file
named `NNNN-slug.md`. Numbering is stable — never renumber; gaps from rejected
ADRs are kept.

**Product decisions** live in `../decisions/product-decisions.md` — do not mix
them in here.

New ADRs are created with the `adr` skill:
`uv run .claude/skills/adr/scripts/new_adr.py "<title>"`.

## Index

| #    | Title | Status | Date |
|------|-------|--------|------|
```

- [ ] **Step 6: Commit**

```bash
git add docs/adr/README.md docs/decisions/product-decisions.md docs/superpowers/specs/2026-06-16-quaestor-general-design.md
git commit -m "docs: separate technical ADRs from product decisions

Move product decision log to docs/decisions/ and scaffold docs/adr/ for
technical ADRs with an index."
```

---

### Task 2: ADR template (Full MADR)

**Files:**
- Create: `.claude/skills/adr/TEMPLATE.md`

**Interfaces:**
- Produces: a template containing exactly these replacement tokens that `new_adr.py` (Task 3) substitutes: `NNNN` (in the title line), `<short title of the decision>` (title text), and `YYYY-MM-DD` (date). These three tokens MUST appear verbatim and `NNNN`/`<short title of the decision>` MUST appear only in the title line.

- [ ] **Step 1: Create the template**

Create `.claude/skills/adr/TEMPLATE.md`:
```markdown
# NNNN. <short title of the decision>

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

What is the issue that motivates this decision? Describe it in 2-4 sentences,
framed as a problem or a question. Link the spec, PR, or issue that prompted it.

## Decision drivers

- <a force or constraint that matters>
- <another force or constraint>

## Considered options

1. <option A>
2. <option B>
3. <option C>

## Decision outcome

Chosen option: **<option X>**, because <justification: how it best satisfies the
decision drivers above>.

### Pros and cons of the options

**<option A>**
- Good, because <pro>
- Bad, because <con>

**<option B>**
- Good, because <pro>
- Bad, because <con>

## Consequences

- Good: <positive outcome of this decision>
- Bad / cost: <negative outcome, follow-up work, or risk this introduces>

## Confirmation

How do we verify this decision is implemented and stays respected? e.g. a test, a
CI check, a code-review checklist item, or a doc reference.
```

- [ ] **Step 2: Verify the template has all sections and tokens**

Run:
```bash
grep -c -E "^## (Context and problem statement|Decision drivers|Considered options|Decision outcome|Consequences|Confirmation)$" .claude/skills/adr/TEMPLATE.md
grep -c "NNNN" .claude/skills/adr/TEMPLATE.md
grep -c "<short title of the decision>" .claude/skills/adr/TEMPLATE.md
```
Expected: first command prints `6`; second prints `1`; third prints `1`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/adr/TEMPLATE.md
git commit -m "feat: add Full MADR template for technical ADRs"
```

---

### Task 3: new_adr.py scaffolding script (TDD)

**Files:**
- Create: `.claude/skills/adr/scripts/new_adr.py`
- Test: `.claude/skills/adr/scripts/test_new_adr.py`

**Interfaces:**
- Consumes: `.claude/skills/adr/TEMPLATE.md` (Task 2), `docs/adr/README.md` (Task 1).
- Produces (functions, all pure-ish with explicit path args so they're testable):
  - `slugify(title: str) -> str`
  - `next_number(adr_dir: Path) -> str`  → 4-digit string
  - `render_template(template_path: Path, number: str, title: str, date: str) -> str`
  - `create_adr(title: str, adr_dir: Path, template_path: Path, date: str) -> tuple[str, Path]`  → `(number, path)`; raises `SystemExit` if an ADR with the same slug already exists
  - `update_index(readme_path: Path, number: str, title: str, status: str, date: str) -> None`
  - `main(argv: list[str]) -> None`

- [ ] **Step 1: Write the failing tests**

Create `.claude/skills/adr/scripts/test_new_adr.py`:
```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import new_adr


def test_slugify_basic():
    assert new_adr.slugify("Use Alembic for migrations") == "use-alembic-for-migrations"


def test_slugify_strips_accents_and_symbols():
    assert new_adr.slugify("Diseño de API: ¿REST o MCP?") == "diseno-de-api-rest-o-mcp"


def test_next_number_empty(tmp_path):
    assert new_adr.next_number(tmp_path) == "0001"


def test_next_number_increments(tmp_path):
    (tmp_path / "0001-foo.md").write_text("x")
    (tmp_path / "0002-bar.md").write_text("x")
    assert new_adr.next_number(tmp_path) == "0003"


def test_create_adr_writes_rendered_file(tmp_path):
    template = tmp_path / "TEMPLATE.md"
    template.write_text(
        "# NNNN. <short title of the decision>\n- **Date:** YYYY-MM-DD\n"
    )
    number, target = new_adr.create_adr("Pick Postgres", tmp_path, template, "2026-06-19")
    assert number == "0001"
    assert target.name == "0001-pick-postgres.md"
    content = target.read_text()
    assert "# 0001. Pick Postgres" in content
    assert "2026-06-19" in content
    assert "NNNN" not in content
    assert "<short title of the decision>" not in content


def test_create_adr_aborts_on_existing_slug(tmp_path):
    template = tmp_path / "TEMPLATE.md"
    template.write_text("# NNNN. <short title of the decision>\n")
    (tmp_path / "0001-pick-postgres.md").write_text("existing")
    with pytest.raises(SystemExit):
        new_adr.create_adr("Pick Postgres", tmp_path, template, "2026-06-19")


def test_update_index_inserts_row_inside_table(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# ADR\n\n## Index\n\n| #    | Title | Status | Date |\n"
        "|------|-------|--------|------|\n"
    )
    new_adr.update_index(readme, "0001", "Pick Postgres", "proposed", "2026-06-19")
    lines = readme.read_text().splitlines()
    sep_idx = next(i for i, l in enumerate(lines) if l.startswith("|---"))
    assert lines[sep_idx + 1] == "| 0001 | Pick Postgres | proposed | 2026-06-19 |"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run --with pytest pytest .claude/skills/adr/scripts/test_new_adr.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'new_adr'` (or collection error), because `new_adr.py` does not exist yet.

- [ ] **Step 3: Write the implementation**

Create `.claude/skills/adr/scripts/new_adr.py`:
```python
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
        if line.lstrip().startswith("|"):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run --with pytest pytest .claude/skills/adr/scripts/test_new_adr.py -v
```
Expected: PASS — 7 passed.

- [ ] **Step 5: End-to-end smoke test of the CLI, then clean up**

Run:
```bash
uv run .claude/skills/adr/scripts/new_adr.py "Use Alembic for migrations"
uv run .claude/skills/adr/scripts/new_adr.py "Pick SQLite as the database"
ls docs/adr/
tail -n 4 docs/adr/README.md
```
Expected: creates `0001-use-alembic-for-migrations.md` and `0002-pick-sqlite-as-the-database.md`; the index shows both rows with status `proposed`.

Then revert the smoke-test artifacts (they are not real decisions):
```bash
rm docs/adr/0001-use-alembic-for-migrations.md docs/adr/0002-pick-sqlite-as-the-database.md
git checkout docs/adr/README.md
```
Expected: `docs/adr/` back to just `README.md`; index table empty again.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/adr/scripts/new_adr.py .claude/skills/adr/scripts/test_new_adr.py
git commit -m "feat: add new_adr.py to scaffold and index technical ADRs"
```

---

### Task 4: The `adr` skill (SKILL.md)

**Files:**
- Create: `.claude/skills/adr/SKILL.md`

**Interfaces:**
- Consumes: `scripts/new_adr.py` (Task 3), `TEMPLATE.md` (Task 2), `docs/adr/README.md` (Task 1).

- [ ] **Step 1: Create SKILL.md**

Create `.claude/skills/adr/SKILL.md`:
```markdown
---
name: adr
description: Record and govern technical and architecture decisions for Quaestor as Architecture Decision Records (ADRs) in docs/adr/. Use when making, proposing, or revisiting an architecturally-significant technical decision — choosing a library or framework, DB schema or migration approach, API/transport design, auth model, testing strategy, module boundaries — or when the user mentions ADR, decision record, or asks "why did we do X".
---

# ADR — Technical Decision Records

Technical decisions for Quaestor are recorded as ADRs in `docs/adr/`, one file per
decision (`NNNN-slug.md`), indexed in `docs/adr/README.md`. Product decisions live
in `docs/decisions/product-decisions.md` — never mix them here.

## When to write an ADR

**Write one for** an architecturally-significant decision:
- library / framework choice
- DB schema shape or migration strategy
- API or transport design (REST / MCP)
- auth model
- testing strategy
- module boundaries
- anything with a high reversal cost or consequences spread across the code

**Do NOT write one for** trivial or easily reversible changes: variable renames,
formatting, local refactors with no contract change, or bug fixes.

## Before proposing a technical change

1. Read `docs/adr/README.md` and the relevant `accepted` ADRs.
2. If a decision is already made, respect it — or write a new ADR that supersedes
   it. Never silently contradict an accepted ADR.

## Create an ADR

```bash
uv run .claude/skills/adr/scripts/new_adr.py "<title>"
```

This picks the next stable number, creates `docs/adr/NNNN-slug.md` from
`TEMPLATE.md` in status `proposed`, and adds a row to the index. Open the printed
file and fill in: context, decision drivers, considered options (with pros/cons),
decision outcome, consequences, confirmation.

## Lifecycle (the `Status` field)

```
proposed ──► accepted ──► (deprecated | superseded by NNNN)
   └───────► rejected
```

- `proposed`: the file IS the live proposal, open for review.
- `accepted` / `rejected`: decided. Update the `Status` field and the index row.
- When a new ADR replaces an old one: set the old one's `Superseded by:` to the
  new number, set the new one's `Supersedes:` to the old number, and update both
  index rows.

## Hard rules

- Numbering is stable — never renumber. Keep gaps from rejected ADRs.
- Do not edit the decision of an `accepted` ADR; supersede it with a new one.
- Keep `docs/adr/README.md` in sync when a status changes.
```

- [ ] **Step 2: Verify frontmatter and triggers**

Run:
```bash
head -3 .claude/skills/adr/SKILL.md
grep -c "Use when" .claude/skills/adr/SKILL.md
```
Expected: first line is `---`, second line starts with `name: adr`; the grep prints `1` (the description contains a "Use when"-style trigger).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/adr/SKILL.md
git commit -m "feat: add adr skill defining the technical decision workflow"
```

---

### Task 5: Root CLAUDE.md guardrail

**Files:**
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: the `adr` skill (Task 4) and `docs/adr/` (Task 1) — references them by path.

- [ ] **Step 1: Create CLAUDE.md**

Create `CLAUDE.md` at the repo root:
```markdown
# Quaestor — agent rules

## Technical decisions

Any architecturally-significant technical decision (library choice, DB schema,
migrations, API/transport design, auth, testing strategy, module boundaries) MUST
be recorded as an ADR in `docs/adr/` using the `adr` skill.

Before proposing a technical change, read the existing ADRs in `docs/adr/` and
respect accepted ones — supersede with a new ADR instead of silently
contradicting them.

Product decisions live in `docs/decisions/product-decisions.md`. Do not mix them
into `docs/adr/`.
```

- [ ] **Step 2: Verify**

Run:
```bash
test -f CLAUDE.md && grep -q "docs/adr/" CLAUDE.md && grep -q "adr.*skill" CLAUDE.md && echo "OK"
```
Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md rule requiring ADRs for technical decisions"
```

---

## Done criteria

- `docs/adr/` contains only `README.md` (empty index); the product log lives at
  `docs/decisions/product-decisions.md`, content intact.
- `.claude/skills/adr/` has SKILL.md, TEMPLATE.md, and a tested `scripts/new_adr.py`.
- Running `uv run .claude/skills/adr/scripts/new_adr.py "<title>"` creates a
  numbered ADR and indexes it.
- `CLAUDE.md` enforces the rule.
- All 5 task commits are on branch `docs/adr-system`.
```

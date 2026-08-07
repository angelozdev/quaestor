#!/usr/bin/env python3
"""spec-coverage — assert every scenario in a feature's IR is bound to a test.

The frontend half of the acceptance pipeline (technical ADR-0045). Where a
backend feature's scenarios are *generated* into pytest, a frontend feature's
scenarios are hand-written as vitest tests — so something has to fail when a
scenario has no test. This is that something.

A scenario is bound when its name appears verbatim as a string in some test
file under the test root. Two tags move a scenario to a different stream rather
than excusing it:

`@browser` — jsdom and happy-dom have no layout engine, so anything about
width, overflow or wrapping is unobservable there. Verified through the Chrome
MCP against the running stack, with the observation recorded in the checkpoint
handoff.

`@backend` — the observable is a figure a service reports, not something a
screen renders, so binding it to a mocked frontend would prove nothing.

Tagging is therefore not a way to skip work, and this tool reports both tagged
sets by name so the handoff can be checked against them.

Usage:
    spec_coverage.py FEATURE_DIR TEST_ROOT

Exit codes:
    0  every unexempt scenario is bound
    1  at least one scenario has no test
    2  input error (missing IR, missing spec.md, unreadable test root)
    3  usage error
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

TEST_SUFFIXES = (".test.ts", ".test.tsx")
UNWALKED_DIRS = frozenset({"node_modules"})
OTHER_STREAM_TAGS = ("@browser", "@backend")
_SCENARIO = re.compile(r"^\s*(?:#+\s*)?Scenario(?:\s+Outline)?:\s*(.+?)\s*$")
_TAG_LINE = re.compile(r"^\s*@[\w-]+(?:\s+@[\w-]+)*\s*$")


class CoverageError(Exception):
    """The inputs this tool needs are missing or unreadable."""


def scenario_names(ir_path: Path) -> list[str]:
    """Every scenario name in the IR, in spec order.

    Raises:
        CoverageError: the IR is missing or is not the shape dae_gherkin emits.
    """
    if not ir_path.is_file():
        raise CoverageError(f"no IR at {ir_path} — run dae_gherkin.py first")
    try:
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        return [s["name"] for s in ir["scenarios"]]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CoverageError(f"{ir_path} is not a dae_gherkin IR: {exc}") from exc


def tagged_scenarios(spec_path: Path) -> dict[str, set[str]]:
    """Scenario names per other-stream tag, keyed by the tag.

    Read from spec.md rather than the IR because dae_gherkin drops tag lines
    as free-form markdown. Tags apply to the next scenario heading, with blank
    and fence lines between them tolerated.

    Raises:
        CoverageError: spec.md is missing.
    """
    if not spec_path.is_file():
        raise CoverageError(f"no spec at {spec_path}")
    found: dict[str, set[str]] = {tag: set() for tag in OTHER_STREAM_TAGS}
    pending: set[str] = set()
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        heading = _SCENARIO.match(line)
        if heading:
            for tag in pending:
                found[tag].add(heading.group(1))
            pending = set()
        elif _TAG_LINE.match(line):
            pending |= {t for t in line.split() if t in OTHER_STREAM_TAGS}
        elif line.strip() and not line.strip().startswith("```"):
            pending = set()
    return found


def test_files(test_root: Path) -> Iterator[Path]:
    """Every test file under the root, without descending into UNWALKED_DIRS."""
    for parent, subdirs, names in os.walk(test_root):
        subdirs[:] = [name for name in subdirs if name not in UNWALKED_DIRS]
        for name in names:
            if name.endswith(TEST_SUFFIXES):
                yield Path(parent) / name


def test_corpus(test_root: Path) -> str:
    """Every test file under the root, concatenated.

    Raises:
        CoverageError: the root does not exist.
    """
    if not test_root.is_dir():
        raise CoverageError(f"no test root at {test_root}")
    parts = [path.read_text(encoding="utf-8", errors="replace") for path in sorted(test_files(test_root))]
    return "\n".join(parts)


def unbound(names: list[str], exempt: set[str], corpus: str) -> list[str]:
    """Scenario names that are neither exempt nor present in the corpus."""
    return [name for name in names if name not in exempt and name not in corpus]


def report(feature_dir: Path, test_root: Path) -> int:
    """Run the check and print its result. Returns the process exit code."""
    names = scenario_names(feature_dir / ".build" / "spec.json")
    tagged = tagged_scenarios(feature_dir / "spec.md")
    exempt = set().union(*tagged.values())
    missing = unbound(names, exempt, test_corpus(test_root))
    covered = len(names) - len(exempt) - len(missing)

    print(f"spec-coverage — {feature_dir.name}")
    print(f"  scenarios      {len(names)}")
    print(f"  bound to tests {covered}")
    for tag in OTHER_STREAM_TAGS:
        print(f"  {tag:14s} {len(tagged[tag])} (evidence required in the handoff)")
    print(f"  unbound        {len(missing)}")

    for tag in OTHER_STREAM_TAGS:
        for name in sorted(tagged[tag]):
            print(f"  {tag}  {name}")
    for name in missing:
        print(f"  UNBOUND   {name}")

    if tagged["@backend"]:
        print("  NOTE: @backend scenarios run as generated pytest — the runner emits that subset")

    return 1 if missing else 0


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 3
    try:
        return report(Path(argv[1]), Path(argv[2]))
    except CoverageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

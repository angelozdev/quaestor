"""Mutation testing over the modules a feature opts in to (DAE Checkpoint 8).

Rewrites one AST node at a time in a target module, runs the test suites
against the rewritten source, and reports which mutants no test noticed.

A surviving mutant is a behaviour the suite cannot tell apart from the real
thing, so it names a hole in the tests rather than a bug in the code.

Suites run as a ladder of `--stage` commands, cheapest first: a mutant killed
by the focused unit files never pays for the full backend run, and one that
survives every rung is only then called a survivor. Feature 008 learned that
the hard way — its first sweep ran the unit stream alone and reported four
survivors the acceptance stream then killed.

A stage that hangs counts as a kill: an infinite fold is a difference the
suite detected, only slowly.

Every stage is proven green against the untouched module before the first
mutant is written. Without that gate a stage that fails for its own reasons
reports every mutant as killed, and the score reads 100% for a suite that
tested nothing. `./run-acceptance-tests.sh` is exactly such a stage: its
ADR-0040 lint gate rejects the reformatting `ast.unparse` performs, so it
must be given `QUAESTOR_SKIP_LINT=1` or replaced by pytest over the
already-generated tests.

Each mutant carries the site index that produced it, so a survivor can be
re-run on its own with `--only` after a test is written to kill it.

The target is copied to `<name>.py.orig` for the length of the sweep and the
copy is removed on the way out. `finally` already restores the target on a
crash or a Ctrl-C; the copy is what survives a kill signal, which matters
because a target may be a file git has never seen.

Usage:
    python3 backend/scripts/mutate.py \\
        --target backend/src/quaestor/domain/rules.py \\
        --stage "uv run pytest -q -x tests/domain/test_rules.py" \\
        --stage "uv run pytest -q -x" \\
        --json .build/mutation.json
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

COMPARE_SWAPS: dict[type[ast.cmpop], list[type[ast.cmpop]]] = {
    ast.Lt: [ast.LtE, ast.Gt],
    ast.LtE: [ast.Lt, ast.GtE],
    ast.Gt: [ast.GtE, ast.Lt],
    ast.GtE: [ast.Gt, ast.LtE],
    ast.Eq: [ast.NotEq],
    ast.NotEq: [ast.Eq],
    ast.Is: [ast.IsNot],
    ast.IsNot: [ast.Is],
    ast.In: [ast.NotIn],
    ast.NotIn: [ast.In],
}

BINOP_SWAPS: dict[type[ast.operator], list[type[ast.operator]]] = {
    ast.Add: [ast.Sub],
    ast.Sub: [ast.Add],
    ast.Mult: [ast.FloorDiv],
    ast.FloorDiv: [ast.Mult],
    ast.Mod: [ast.Mult],
}

BOOLOP_SWAPS: dict[type[ast.boolop], list[type[ast.boolop]]] = {
    ast.And: [ast.Or],
    ast.Or: [ast.And],
}

BUILTIN_SWAPS = {"max": "min", "min": "max", "sum": "len", "sorted": "reversed", "any": "all", "all": "any"}

SYMBOLS = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.And: "and",
    ast.Or: "or",
}

Mutation = tuple[str, str, str, Callable[[ast.AST], ast.AST]]


def _symbol(op: type) -> str:
    return SYMBOLS.get(op, op.__name__)


def _constant_variants(value: object) -> list[object]:
    if isinstance(value, bool):
        return [not value]
    if isinstance(value, int):
        return [1 - value, value + 2] if value in (0, 1) else [0, 1]
    return []


def _compare_mutations(node: ast.Compare) -> list[Mutation]:
    found = []
    for position, op in enumerate(node.ops):
        for replacement in COMPARE_SWAPS.get(type(op), []):

            def apply(target: ast.AST, position: int = position, replacement: type = replacement) -> ast.AST:
                target.ops[position] = replacement()
                return target

            found.append(("compare", _symbol(type(op)), _symbol(replacement), apply))
    return found


def _operator_mutations(node: ast.BinOp | ast.BoolOp, swaps: dict) -> list[Mutation]:
    found = []
    for replacement in swaps.get(type(node.op), []):

        def apply(target: ast.AST, replacement: type = replacement) -> ast.AST:
            target.op = replacement()
            return target

        found.append(("operator", _symbol(type(node.op)), _symbol(replacement), apply))
    return found


def _constant_mutations(node: ast.Constant) -> list[Mutation]:
    found = []
    for variant in _constant_variants(node.value):

        def apply(target: ast.AST, variant: object = variant) -> ast.AST:
            target.value = variant
            return target

        found.append(("constant", repr(node.value), repr(variant), apply))
    return found


def _builtin_mutations(node: ast.Call) -> list[Mutation]:
    swap = BUILTIN_SWAPS[node.func.id]

    def apply(target: ast.AST) -> ast.AST:
        target.func.id = swap
        return target

    return [("builtin", node.func.id, swap, apply)]


def mutations_of(node: ast.AST) -> list[Mutation]:
    """Every single-node rewrite this node admits, in a stable order."""
    if isinstance(node, ast.Compare):
        return _compare_mutations(node)
    if isinstance(node, ast.BinOp):
        return _operator_mutations(node, BINOP_SWAPS)
    if isinstance(node, ast.BoolOp):
        return _operator_mutations(node, BOOLOP_SWAPS)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return [("unary", "not x", "x", lambda target: target.operand)]
    if isinstance(node, ast.Constant):
        return _constant_mutations(node)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BUILTIN_SWAPS:
        return _builtin_mutations(node)
    return []


class _Rewriter(ast.NodeTransformer):
    """Counts every mutation site, and applies the one it was asked for.

    Children are visited before their parent, so the order a site is numbered
    in does not depend on whether an earlier site was applied.
    """

    def __init__(self, wanted: int) -> None:
        self.wanted = wanted
        self.seen = 0
        self.hit: dict | None = None

    def generic_visit(self, node: ast.AST) -> ast.AST:
        node = super().generic_visit(node)
        for kind, before, after, apply in mutations_of(node):
            index = self.seen
            self.seen += 1
            if index != self.wanted:
                continue
            self.hit = {"index": index, "line": getattr(node, "lineno", 0), "kind": kind, "from": before, "to": after}
            return apply(node)
        return node


def count_sites(source: str) -> int:
    """How many mutants this module admits."""
    rewriter = _Rewriter(-1)
    rewriter.visit(ast.parse(source))
    return rewriter.seen


def mutate(source: str, index: int) -> tuple[str, dict]:
    """The module's source with exactly one node rewritten, and what changed."""
    rewriter = _Rewriter(index)
    tree = rewriter.visit(ast.parse(source))
    if rewriter.hit is None:
        raise LookupError(f"no mutation site numbered {index}")
    return ast.unparse(ast.fix_missing_locations(tree)), rewriter.hit


def _run(command: str, cwd: Path, timeout: int) -> tuple[bool, str]:
    env = dict(os.environ)
    env.setdefault("SESSION_SECRET", "x" * 64)
    try:
        done = subprocess.run(  # noqa: S602
            command, shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return done.returncode == 0, "pass" if done.returncode == 0 else "fail"


def write_source(target: Path, text: str) -> None:
    """Write the module and drop the bytecode cache that would otherwise hide it.

    CPython reuses a `.pyc` whenever the source's `(mtime_seconds, size)` pair
    is unchanged. Swapping one operator for another keeps the size identical,
    and a sweep writes far faster than one write per second — so without this
    the next process imports the *previous* module and the mutant is reported
    as survived when no test ever ran against it.
    """
    target.write_text(text)
    cache = target.parent / "__pycache__"
    for stale in cache.glob(f"{target.stem}.*.pyc"):
        stale.unlink(missing_ok=True)


def prove_stages_green(target: Path, original: str, stages: list[str], cwd: Path, timeout: int, log) -> None:
    """Fail loudly unless every stage passes on the target carrying no mutation.

    The probe writes the module round-tripped through `ast.unparse` rather
    than the file as committed. Behaviour is identical, formatting is not —
    so a stage that reacts to the mutator's reformatting instead of to
    behaviour is red here, before it can report a whole sweep as killed.

    Raises:
        RuntimeError: a stage is red with no mutation applied, which would
            make every mutant look killed and the score meaningless.
    """
    write_source(target, ast.unparse(ast.parse(original)))
    try:
        for number, stage in enumerate(stages, start=1):
            passed, note = _run(stage, cwd, timeout)
            print(f"[baseline] {target.name} stage {number}: {note}  ({stage})", file=log, flush=True)
            if not passed:
                raise RuntimeError(
                    f"stage {number} is '{note}' with no mutation applied, so every mutant "
                    f"would count as killed and the score would be meaningless: {stage}"
                )
    finally:
        write_source(target, original)


def sweep(target: Path, stages: list[str], cwd: Path, timeout: int, log, only: list[int] | None = None) -> dict:
    """Rewrite the target one node at a time and record what no stage noticed."""
    original = target.read_text()
    rescue = target.with_suffix(".py.orig")
    rescue.write_text(original)
    prove_stages_green(target, original, stages, cwd, timeout, log)
    total = count_sites(original)
    wanted = range(total) if not only else [index for index in only if 0 <= index < total]
    killed, survivors, skipped = 0, [], 0
    started = time.time()
    try:
        for index in wanted:
            try:
                source, hit = mutate(original, index)
                compile(source, str(target), "exec")
            except (LookupError, SyntaxError, ValueError):
                skipped += 1
                continue
            write_source(target, source)
            verdict, rung = "survived", ""
            for number, stage in enumerate(stages, start=1):
                passed, note = _run(stage, cwd, timeout)
                if not passed:
                    verdict, rung = "killed", f" stage {number} ({note})"
                    break
            if verdict == "survived":
                survivors.append(hit)
            else:
                killed += 1
            print(
                f"[{index + 1}/{total}] {target.name}:{hit['line']} {hit['from']} -> {hit['to']}  {verdict}{rung}",
                file=log,
                flush=True,
            )
            if verdict == "survived":
                print(f"    survivor --only {index}", file=log, flush=True)
    finally:
        write_source(target, original)
        rescue.unlink(missing_ok=True)
    live = killed + len(survivors)
    return {
        "module": str(target),
        "mutants": live,
        "killed": killed,
        "survived": len(survivors),
        "skipped": skipped,
        "score": round(100.0 * killed / live, 1) if live else 100.0,
        "seconds": round(time.time() - started, 1),
        "survivors": survivors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mutation testing for opted-in modules.")
    parser.add_argument("--target", action="append", required=True, help="Module to mutate (repeatable).")
    parser.add_argument("--stage", action="append", required=True, help="Test command, cheapest first (repeatable).")
    parser.add_argument("--cwd", default="backend", help="Directory the stages run from.")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds before a stage counts as a kill.")
    parser.add_argument("--json", help="Where to write the machine-readable report.")
    parser.add_argument("--only", type=int, action="append", help="Sweep only this site index (repeatable).")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    cwd = (root / args.cwd).resolve()
    results = [
        sweep((root / name).resolve(), args.stage, cwd, args.timeout, sys.stderr, args.only) for name in args.target
    ]

    mutants = sum(result["mutants"] for result in results)
    killed = sum(result["killed"] for result in results)
    summary = {
        "mutants": mutants,
        "killed": killed,
        "survived": mutants - killed,
        "score": round(100.0 * killed / mutants, 1) if mutants else 100.0,
        "stages": args.stage,
        "modules": results,
    }
    print(json.dumps(summary, indent=2))  # noqa: T201
    if args.json:
        out = (root / args.json).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

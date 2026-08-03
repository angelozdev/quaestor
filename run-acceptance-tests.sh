#!/bin/sh
# DAE acceptance pipeline runner:
#   spec.md -> dae_gherkin.py -> .build/spec.json (IR)
#           -> acceptance/generator.py -> .build/generated/ (pytest)
#           -> uv run pytest (backend venv, in-memory SQLite)
#
# Usage:
#   ./run-acceptance-tests.sh                          # all features with a spec.md
#   ./run-acceptance-tests.sh features/005-fx-read-time-conversion [more...]
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- locate the portable DAE Gherkin parser (override with $DAE_GHERKIN) ----
if [ -z "${DAE_GHERKIN:-}" ]; then
    DAE_GHERKIN="$(
        ls "$HOME"/.claude/plugins/cache/disciplined-agentic-engineering/engineer/*/scripts/dae_gherkin.py 2>/dev/null \
        | sort -V | tail -n 1
    )" || true
fi
if [ -z "${DAE_GHERKIN:-}" ] || [ ! -f "$DAE_GHERKIN" ]; then
    echo "error: dae_gherkin.py not found — set DAE_GHERKIN to its path" >&2
    exit 1
fi

# --- lint gate (ADR-0040) ---------------------------------------------------
# Runs before generation so a lint failure never leaves stale .build/ output.
# Set QUAESTOR_SKIP_LINT=1 to bypass while iterating; CI and pushes must not.
if [ "${QUAESTOR_SKIP_LINT:-0}" != "1" ]; then
    uv run --project "$ROOT/backend" ruff check "$ROOT/backend/src" "$ROOT/backend/tests" "$ROOT/acceptance"
    uv run --project "$ROOT/backend" ruff format --check "$ROOT/backend/src" "$ROOT/backend/tests" "$ROOT/acceptance"
fi

# --- select feature dirs ----------------------------------------------------
if [ "$#" -gt 0 ]; then
    FEATURE_DIRS="$*"
else
    FEATURE_DIRS=""
    for spec in "$ROOT"/features/*/spec.md; do
        [ -f "$spec" ] || continue
        FEATURE_DIRS="$FEATURE_DIRS $(dirname "$spec")"
    done
    if [ -z "$FEATURE_DIRS" ]; then
        echo "error: no features/*/spec.md found" >&2
        exit 1
    fi
fi

# --- parse + generate per feature ------------------------------------------
GENERATED_DIRS=""
for dir in $FEATURE_DIRS; do
    dir="$(cd "$dir" && pwd)"
    spec="$dir/spec.md"
    if [ ! -f "$spec" ]; then
        echo "error: $spec not found" >&2
        exit 1
    fi
    mkdir -p "$dir/.build"
    python3 "$DAE_GHERKIN" "$spec" "$dir/.build/spec.json"
    python3 "$ROOT/acceptance/generator.py" "$dir"
    GENERATED_DIRS="$GENERATED_DIRS $dir/.build/generated"
done

# --- run --------------------------------------------------------------------
# From backend/ so uv resolves the backend project env (same as `just dev-test`).
cd "$ROOT/backend"
# shellcheck disable=SC2086 — word splitting over generated dirs is intended
exec uv run pytest $GENERATED_DIRS

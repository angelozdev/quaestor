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

# --- parse, then route each feature to its stream (ADR-0045) ----------------
# `acceptance_stream: frontend` binds every scenario to vitest and generates no
# pytest; `mixed` does the same for its untagged scenarios and generates pytest
# for its @backend ones alone. Anything else generates pytest as it always did.
GENERATED_DIRS=""
FRONTEND_FAILED=0
FRONTEND_STREAM=0
for dir in $FEATURE_DIRS; do
    dir="$(cd "$dir" && pwd)"
    spec="$dir/spec.md"
    if [ ! -f "$spec" ]; then
        echo "error: $spec not found" >&2
        exit 1
    fi
    mkdir -p "$dir/.build"
    python3 "$DAE_GHERKIN" "$spec" "$dir/.build/spec.json"

    if grep -qE '^acceptance_stream:[[:space:]]*(frontend|mixed)[[:space:]]*$' "$dir/feature.md" 2>/dev/null; then
        FRONTEND_STREAM=1
        python3 "$ROOT/acceptance/spec_coverage.py" "$dir" "$ROOT/frontend" || FRONTEND_FAILED=1
        if grep -qE '^acceptance_stream:[[:space:]]*mixed[[:space:]]*$' "$dir/feature.md"; then
            python3 "$ROOT/acceptance/generator.py" --tag @backend "$dir"
            GENERATED_DIRS="$GENERATED_DIRS $dir/.build/generated"
        fi
        continue
    fi

    python3 "$ROOT/acceptance/generator.py" "$dir"
    GENERATED_DIRS="$GENERATED_DIRS $dir/.build/generated"
done

# --- run --------------------------------------------------------------------
# spec_coverage.py only checks that a test carrying each scenario's name EXISTS.
# The tests themselves are vitest's, so a frontend stream that never runs them
# would report green over a suite nobody executed.
VITEST_STATUS=0
if [ "$FRONTEND_STREAM" -ne 0 ]; then
    (cd "$ROOT/frontend" && pnpm vitest run) || VITEST_STATUS=$?
fi

# From backend/ so uv resolves the backend project env (same as `just dev-test`).
PYTEST_STATUS=0
if [ -n "$GENERATED_DIRS" ]; then
    cd "$ROOT/backend"
    # shellcheck disable=SC2086 — word splitting over generated dirs is intended
    uv run pytest $GENERATED_DIRS || PYTEST_STATUS=$?
fi

if [ "$FRONTEND_FAILED" -ne 0 ]; then
    echo "spec-coverage failed: a scenario has no test — see the UNBOUND list above" >&2
    exit 1
fi
if [ "$VITEST_STATUS" -ne 0 ]; then
    echo "vitest failed: the scenarios are bound to tests that do not pass" >&2
    exit "$VITEST_STATUS"
fi
exit "$PYTEST_STATUS"

#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<'HELP'
run-acceptance-tests.sh — the DAE acceptance pipeline.

    spec.md -> dae_gherkin.py -> .build/spec.json (IR)
            -> acceptance/generator.py -> .build/generated/ (pytest)
            -> uv run pytest (backend venv, in-memory SQLite)

A feature whose feature.md declares `acceptance_stream: frontend` binds every
scenario to a vitest test instead and generates no pytest; `mixed` does that for
its untagged scenarios and generates pytest for its @backend ones alone
(technical ADR-0045). spec_coverage.py only checks that a test carrying each
scenario's name exists, so the vitest suite is run here too — otherwise a
frontend feature would report green over tests nobody executed.

Usage:
    ./run-acceptance-tests.sh                         every feature with a spec.md
    ./run-acceptance-tests.sh features/005-fx-... [more...]

Environment:
    DAE_GHERKIN         path to the portable parser, when it cannot be found
    QUAESTOR_SKIP_LINT  set to 1 to bypass the lint gate while iterating
HELP
}

newest_installed_gherkin_parser() {
    ls "$HOME"/.claude/plugins/cache/disciplined-agentic-engineering/engineer/*/scripts/dae_gherkin.py \
        2>/dev/null | sort -V | tail -n 1
}

locate_gherkin_parser() {
    parser="${DAE_GHERKIN:-$(newest_installed_gherkin_parser || true)}"
    if [ -z "$parser" ] || [ ! -f "$parser" ]; then
        echo "error: dae_gherkin.py not found — set DAE_GHERKIN to its path" >&2
        return 1
    fi
    echo "$parser"
}

lint_gate() {
    if [ "${QUAESTOR_SKIP_LINT:-0}" != "1" ]; then
        uv run --project "$ROOT/backend" ruff check "$ROOT/backend/src" "$ROOT/backend/tests" "$ROOT/acceptance"
        uv run --project "$ROOT/backend" ruff format --check "$ROOT/backend/src" "$ROOT/backend/tests" "$ROOT/acceptance"
    fi
}

every_feature_with_a_spec() {
    found=""
    for spec in "$ROOT"/features/*/spec.md; do
        [ -f "$spec" ] || continue
        found="$found $(dirname "$spec")"
    done
    if [ -z "$found" ]; then
        echo "error: no features/*/spec.md found" >&2
        return 1
    fi
    echo "$found"
}

declares_stream() {
    grep -qE "^acceptance_stream:[[:space:]]*$2[[:space:]]*$" "$1/feature.md" 2>/dev/null
}

generate_pytest_for() {
    target="$1"
    shift
    python3 "$ROOT/acceptance/generator.py" "$@" "$target"
    GENERATED_DIRS="$GENERATED_DIRS $target/.build/generated"
}

route_feature() {
    dir="$(cd "$1" && pwd)"
    if [ ! -f "$dir/spec.md" ]; then
        echo "error: $dir/spec.md not found" >&2
        return 1
    fi
    mkdir -p "$dir/.build"
    python3 "$GHERKIN" "$dir/spec.md" "$dir/.build/spec.json"

    if ! declares_stream "$dir" '(frontend|mixed)'; then
        generate_pytest_for "$dir"
        return 0
    fi

    FRONTEND_STREAM=1
    python3 "$ROOT/acceptance/spec_coverage.py" "$dir" "$ROOT/frontend" || FRONTEND_FAILED=1
    if declares_stream "$dir" 'mixed'; then
        generate_pytest_for "$dir" --tag @backend
    fi
}

run_frontend_stream() {
    (cd "$ROOT/frontend" && pnpm vitest run)
}

run_backend_stream() {
    cd "$ROOT/backend"
    set -- $GENERATED_DIRS
    uv run pytest "$@"
}

main() {
    case "${1:-}" in
        -h | --help)
            usage
            return 0
            ;;
    esac

    GHERKIN="$(locate_gherkin_parser)"
    lint_gate

    if [ "$#" -gt 0 ]; then
        selected="$*"
    else
        selected="$(every_feature_with_a_spec)"
    fi

    GENERATED_DIRS=""
    FRONTEND_STREAM=0
    FRONTEND_FAILED=0
    for dir in $selected; do
        route_feature "$dir"
    done

    VITEST_STATUS=0
    if [ "$FRONTEND_STREAM" -ne 0 ]; then
        run_frontend_stream || VITEST_STATUS=$?
    fi

    PYTEST_STATUS=0
    if [ -n "$GENERATED_DIRS" ]; then
        run_backend_stream || PYTEST_STATUS=$?
    fi

    if [ "$FRONTEND_FAILED" -ne 0 ]; then
        echo "spec-coverage failed: a scenario has no test — see the UNBOUND list above" >&2
        return 1
    fi
    if [ "$VITEST_STATUS" -ne 0 ]; then
        echo "vitest failed: the scenarios are bound to tests that do not pass" >&2
        return "$VITEST_STATUS"
    fi
    return "$PYTEST_STATUS"
}

main "$@"

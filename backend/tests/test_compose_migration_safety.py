"""ADR-0033: no compose profile may bind-mount backend/src except the sandbox.

The mount is what lets uvicorn autoreload fire on a file write, and the app
lifespan runs `alembic upgrade head`. Mounting src under the postgres or remote
env files therefore migrates real data on every save.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_COMPOSE = REPO_ROOT / "docker-compose.yml"
DEV_COMPOSE = REPO_ROOT / "docker-compose.dev.yml"
JUSTFILE = REPO_ROOT / "justfile"

SRC_MOUNT_SOURCE = "./backend/src"
DEV_OVERRIDE = "docker-compose.dev.yml"

_ASSIGNMENT = re.compile(r"^(\w+) := (.+)$")
_INTERPOLATION = re.compile(r"\{\{(\w+)\}\}")


def _api_volumes(compose_path: Path) -> list[str]:
    document = yaml.safe_load(compose_path.read_text())
    return document["services"]["api"].get("volumes", [])


def _mounts_src(volumes: list[str]) -> bool:
    return any(volume.split(":")[0] == SRC_MOUNT_SOURCE for volume in volumes)


def _just_variables(lines: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for line in lines:
        match = _ASSIGNMENT.match(line)
        if match:
            variables[match.group(1)] = "".join(re.findall(r'"([^"]*)"', match.group(2))) or match.group(2)
    return variables


def _expand(text: str, variables: dict[str, str]) -> str:
    return _INTERPOLATION.sub(lambda m: variables.get(m.group(1), m.group(0)), text)


def _recipe(name: str) -> str:
    lines = JUSTFILE.read_text().splitlines()
    variables = _just_variables(lines)
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
    body = [lines[start]]
    for line in lines[start + 1 :]:
        if line and not line.startswith(("\t", " ")):
            break
        body.append(line)
    return _expand("\n".join(body), variables)


def test_base_compose_does_not_mount_src():
    assert not _mounts_src(_api_volumes(BASE_COMPOSE))


def test_dev_override_restores_the_src_mount():
    assert _mounts_src(_api_volumes(DEV_COMPOSE))


def test_only_the_sqlite_sandbox_layers_the_dev_override():
    assert DEV_OVERRIDE in _recipe("dev-local")
    assert DEV_OVERRIDE not in _recipe("dev-prod")
    assert DEV_OVERRIDE not in _recipe("dev-real")
    assert DEV_OVERRIDE not in _recipe("migrate")


def test_dev_prod_depends_on_the_pending_migration_preflight():
    assert "prod-check-migrations" in _recipe("dev-prod").splitlines()[0]
    assert "check_pending_migrations.py" in _recipe("prod-check-migrations")


def test_migrate_is_gated_on_a_dated_backup():
    body = _recipe("migrate")
    assert "just backup first" in body
    assert "alembic upgrade head" in body

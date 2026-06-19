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

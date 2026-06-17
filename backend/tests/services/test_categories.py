import pytest

from quaestor.domain.errors import ValidationError
from quaestor.services import categories


def test_crear_grupo_y_categoria_enlazada(session):
    grupo = categories.crear_grupo(session, "Essentials", sort_order=1)
    cat = categories.crear_categoria(session, "Groceries", group_id=grupo.id)
    assert cat.group_id == grupo.id
    assert cat.is_income is False


def test_categoria_sin_grupo_es_valida(session):
    cat = categories.crear_categoria(session, "No group")
    assert cat.group_id is None


def test_categoria_con_grupo_inexistente_falla(session):
    with pytest.raises(ValidationError):
        categories.crear_categoria(session, "X", group_id=999)


def test_flags_de_categoria(session):
    cat = categories.crear_categoria(
        session, "Transfers", is_income=False,
        exclude_from_budget=True, exclude_from_totals=True,
    )
    assert cat.exclude_from_budget is True
    assert cat.exclude_from_totals is True


def test_listar_grupos_ordenados(session):
    categories.crear_grupo(session, "Entertainment", sort_order=2)
    categories.crear_grupo(session, "Essentials", sort_order=1)
    nombres = [g.name for g in categories.listar_grupos(session)]
    assert nombres == ["Essentials", "Entertainment"]

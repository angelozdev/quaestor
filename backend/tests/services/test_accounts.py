import pytest

from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType
from quaestor.services import accounts


def test_crear_y_consultar_cuenta(session):
    acc = accounts.crear_cuenta(session, "Bancolombia", AccountType.debit, "COP")
    assert acc.id is not None
    assert accounts.consultar_cuenta(session, acc.id).name == "Bancolombia"


def test_crear_cuenta_acepta_tipo_string(session):
    acc = accounts.crear_cuenta(session, "Tarjeta", "credit", "COP", balance=-50000)
    assert acc.type == AccountType.credit
    assert acc.balance == -50000


def test_crear_cuenta_rechaza_moneda(session):
    with pytest.raises(ValidationError):
        accounts.crear_cuenta(session, "X", AccountType.cash, "EUR")


def test_crear_cuenta_rechaza_nombre_vacio(session):
    with pytest.raises(ValidationError):
        accounts.crear_cuenta(session, "  ", AccountType.cash, "COP")


def test_listar_excluye_archivadas_por_defecto(session):
    a = accounts.crear_cuenta(session, "A", AccountType.debit, "COP")
    accounts.crear_cuenta(session, "B", AccountType.debit, "COP")
    accounts.archivar_cuenta(session, a.id)
    activas = accounts.listar_cuentas(session)
    assert {c.name for c in activas} == {"B"}
    todas = accounts.listar_cuentas(session, incluir_archivadas=True)
    assert {c.name for c in todas} == {"A", "B"}


def test_consultar_inexistente(session):
    with pytest.raises(NotFound):
        accounts.consultar_cuenta(session, 999)

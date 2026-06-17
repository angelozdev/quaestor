from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.errors import MissingRate, NotFound, ValidationError
from quaestor.domain.models import AccountType, TxStatus, TxType
from quaestor.services import accounts, categories, fx, transactions


def _cuenta(session, currency="COP", balance=0, type=AccountType.debit):
    return accounts.crear_cuenta(session, "Cuenta", type, currency, balance=balance)


def test_registrar_gasto_resta_balance(session):
    acc = _cuenta(session, balance=100_000)
    tx = transactions.registrar_gasto(
        session, acc.id, 45_000, "COP", date(2026, 6, 1), "Éxito"
    )
    assert tx.type == TxType.expense
    assert tx.status == TxStatus.posted
    assert tx.amount == 45_000
    assert tx.to_base == 45_000
    assert tx.fx_rate == Decimal("1")
    assert accounts.consultar_cuenta(session, acc.id).balance == 55_000


def test_registrar_ingreso_suma_balance(session):
    acc = _cuenta(session, balance=0)
    transactions.registrar_ingreso(
        session, acc.id, 3_200_000, "COP", date(2026, 6, 1), "Sueldo"
    )
    assert accounts.consultar_cuenta(session, acc.id).balance == 3_200_000


def test_gasto_usd_congela_to_base(session):
    acc = _cuenta(session, currency="USD", balance=0)
    fx.fijar_tasa_fx(session, date(2026, 6, 1), "4150")
    tx = transactions.registrar_gasto(
        session, acc.id, 1200, "USD", date(2026, 6, 1), "Spotify"
    )
    assert tx.fx_rate == Decimal("4150")
    assert tx.to_base == 4_980_000  # congelado
    # cambiar la tasa después no mueve el to_base ya guardado
    fx.fijar_tasa_fx(session, date(2026, 6, 2), "5000")
    assert transactions.consultar_transaccion(session, tx.id).to_base == 4_980_000
    assert accounts.consultar_cuenta(session, acc.id).balance == -1200  # USD cents


def test_gasto_usd_sin_tasa_falla(session):
    acc = _cuenta(session, currency="USD")
    with pytest.raises(MissingRate):
        transactions.registrar_gasto(
            session, acc.id, 1200, "USD", date(2026, 6, 1), "Spotify"
        )


def test_moneda_debe_coincidir_con_cuenta(session):
    acc = _cuenta(session, currency="COP")
    with pytest.raises(ValidationError):
        transactions.registrar_gasto(
            session, acc.id, 1200, "USD", date(2026, 6, 1), "X", fx_rate=Decimal("4150")
        )


def test_monto_no_positivo_falla(session):
    acc = _cuenta(session)
    with pytest.raises(ValidationError):
        transactions.registrar_gasto(session, acc.id, 0, "COP", date(2026, 6, 1), "X")


def test_cuenta_inexistente_falla(session):
    with pytest.raises(NotFound):
        transactions.registrar_gasto(session, 999, 1000, "COP", date(2026, 6, 1), "X")


def test_categoria_inexistente_falla(session):
    acc = _cuenta(session)
    with pytest.raises(ValidationError):
        transactions.registrar_gasto(
            session, acc.id, 1000, "COP", date(2026, 6, 1), "X", category_id=999
        )

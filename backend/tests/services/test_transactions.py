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


def test_transferir_mueve_ambos_balances_y_comparte_grupo(session):
    origen = accounts.crear_cuenta(session, "Débito", AccountType.debit, "COP", balance=1_000_000)
    destino = accounts.crear_cuenta(session, "Ahorros", AccountType.savings, "COP", balance=0)
    leg_from, leg_to = transactions.transferir(
        session, origen.id, destino.id, 500_000, "COP", date(2026, 6, 1)
    )
    assert leg_from.type == TxType.transfer and leg_to.type == TxType.transfer
    assert leg_from.transfer_group_id == leg_to.transfer_group_id
    assert accounts.consultar_cuenta(session, origen.id).balance == 500_000
    assert accounts.consultar_cuenta(session, destino.id).balance == 500_000


def test_transferir_misma_cuenta_falla(session):
    acc = accounts.crear_cuenta(session, "A", AccountType.debit, "COP", balance=100)
    with pytest.raises(Exception):  # TransferImbalance
        transactions.transferir(session, acc.id, acc.id, 50, "COP", date(2026, 6, 1))


def test_transferir_destino_inexistente_es_atomica(session):
    origen = accounts.crear_cuenta(session, "Débito", AccountType.debit, "COP", balance=1_000_000)
    with pytest.raises(NotFound):
        transactions.transferir(session, origen.id, 999, 500_000, "COP", date(2026, 6, 1))
    # no rows created, balance intact
    assert accounts.consultar_cuenta(session, origen.id).balance == 1_000_000
    assert transactions.listar_transacciones(session) == []


def test_pago_extracto_tarjeta_es_transfer_no_gasto(session):
    debito = accounts.crear_cuenta(session, "Débito", AccountType.debit, "COP", balance=1_000_000)
    tarjeta = accounts.crear_cuenta(session, "Visa", AccountType.credit, "COP", balance=-300_000)
    transactions.transferir(session, debito.id, tarjeta.id, 300_000, "COP", date(2026, 6, 5))
    assert accounts.consultar_cuenta(session, tarjeta.id).balance == 0  # debt settled
    gastos = transactions.listar_transacciones(session, type=TxType.expense)
    assert gastos == []  # the payment is NOT an expense


def test_listar_filtra_por_cuenta_tipo_y_rango(session):
    a = accounts.crear_cuenta(session, "A", AccountType.debit, "COP", balance=1_000_000)
    b = accounts.crear_cuenta(session, "B", AccountType.debit, "COP", balance=0)
    transactions.registrar_gasto(session, a.id, 1000, "COP", date(2026, 6, 1), "x")
    transactions.registrar_ingreso(session, a.id, 2000, "COP", date(2026, 6, 15), "y")
    transactions.registrar_gasto(session, b.id, 3000, "COP", date(2026, 7, 1), "z")
    de_a = transactions.listar_transacciones(session, account_id=a.id)
    assert len(de_a) == 2
    gastos_junio = transactions.listar_transacciones(
        session, type=TxType.expense, date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)
    )
    assert len(gastos_junio) == 1
    assert gastos_junio[0].account_id == a.id


def test_listar_filtra_por_tag(session):
    from quaestor.services import tags
    a = accounts.crear_cuenta(session, "A", AccountType.debit, "COP", balance=1_000_000)
    tx = transactions.registrar_gasto(session, a.id, 1000, "COP", date(2026, 6, 1), "x")
    transactions.registrar_gasto(session, a.id, 2000, "COP", date(2026, 6, 2), "y")
    tags.etiquetar(session, tx.id, ["viaje"])
    con_tag = transactions.listar_transacciones(session, tag="viaje")
    assert len(con_tag) == 1 and con_tag[0].id == tx.id

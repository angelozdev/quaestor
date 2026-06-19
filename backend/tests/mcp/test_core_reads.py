from datetime import date

from quaestor.mcp.tools import core
from quaestor.mcp.tools.core import ConsultarTasaInput, ConsultarTxInput
from quaestor.services import accounts, fx, tags


def test_listar_cuentas(session, seeded):
    out = core.listar_cuentas(session)
    assert "Bancolombia" in out and "100000.00" in out and "COP" in out


def test_listar_categorias(session, seeded):
    out = core.listar_categorias(session)
    assert "Mercado" in out


def test_listar_tags(session, seeded):
    tags.create_tag(session, "viaje")
    assert "viaje" in core.listar_tags(session)


def test_consultar_tasa_fx_returns_rate(session):
    fx.set_fx_rate(session, date(2026, 6, 18), "4150")
    out = core.consultar_tasa_fx(session, ConsultarTasaInput(date=date(2026, 6, 18)))
    assert "4150" in out and "2026-06-18" in out


def test_consultar_tasa_fx_missing_returns_text(session):
    out = core.consultar_tasa_fx(session, ConsultarTasaInput(date=date(2026, 6, 18)))
    assert "USD→COP" in out


def test_consultar_transacciones_empty(session, seeded):
    out = core.consultar_transacciones(session, ConsultarTxInput())
    assert out == "No transactions for those filters."


def test_consultar_transacciones_lists_and_totals(session, seeded):
    from quaestor.services import transactions as tx_service

    acc = seeded["account"]
    tx_service.record_expense(session, acc.id, 5_000_000, "COP", date(2026, 6, 18), "Almuerzo")
    tx_service.record_expense(session, acc.id, 3_000_000, "COP", date(2026, 6, 18), "Café")
    out = core.consultar_transacciones(session, ConsultarTxInput(type="expense"))
    assert "Almuerzo" in out and "Café" in out
    assert "Total (COP): 80000.00" in out


def test_consultar_transacciones_filters_by_account_name(session, seeded):
    from quaestor.services import transactions as tx_service

    other = accounts.create_account(session, "Ahorros", "savings", "COP", balance=0)
    tx_service.record_expense(
        session, seeded["account"].id, 1_000_000, "COP", date(2026, 6, 18), "Aquí"
    )
    out = core.consultar_transacciones(session, ConsultarTxInput(account="Ahorros"))
    assert "Aquí" not in out  # filtered to the empty account
    assert other.id is not None


def test_consultar_transacciones_unknown_account_returns_text(session, seeded):
    out = core.consultar_transacciones(session, ConsultarTxInput(account="Nequi"))
    assert "Account 'Nequi' not found" in out

from datetime import date

from quaestor.mcp.tools import core
from quaestor.mcp.tools.core import (
    FijarTasaInput,
    RegistrarGastoInput,
    RegistrarIngresoInput,
    TransferirInput,
)
from quaestor.services import accounts


def test_registrar_gasto_confirms_and_moves_balance(session, seeded):
    out = core.registrar_gasto(
        session,
        RegistrarGastoInput(
            payee="Almuerzo",
            amount=5_000_000,  # 50 mil COP
            account="Bancolombia",
            category="Mercado",
            date=date(2026, 6, 18),
        ),
    )
    assert "Expense recorded" in out
    assert "Almuerzo" in out
    assert "50000.00 COP" in out
    # 100k - 50k = 50k, balance shown post-write
    assert accounts.get_account(session, seeded["account"].id).balance == 5_000_000
    assert "new balance: 50000.00 COP" in out


def test_registrar_gasto_resolves_account_case_insensitively(session, seeded):
    out = core.registrar_gasto(
        session,
        RegistrarGastoInput(payee="Café", amount=800_000, account="bancolombia"),
    )
    assert "Expense recorded" in out


def test_registrar_gasto_unknown_account_returns_guidance(session, seeded):
    out = core.registrar_gasto(
        session,
        RegistrarGastoInput(payee="X", amount=1000, account="Nequi"),
    )
    assert "Account 'Nequi' not found" in out
    assert "Bancolombia" in out  # lists what exists


def test_registrar_gasto_applies_tags(session, seeded):
    core.registrar_gasto(
        session,
        RegistrarGastoInput(
            payee="Viaje", amount=2_000_000, account="Bancolombia", tags=["viaje", "junio"]
        ),
    )
    # tag filter through the read service proves the link was created
    from quaestor.services import transactions as tx_service

    assert len(tx_service.list_transactions(session, tag="viaje")) == 1


def test_registrar_ingreso_increments_balance(session, seeded):
    out = core.registrar_ingreso(
        session,
        RegistrarIngresoInput(
            payee="Sueldo", amount=3_200_000, account="Bancolombia", date=date(2026, 6, 18)
        ),
    )
    assert "Income recorded" in out
    assert accounts.get_account(session, seeded["account"].id).balance == 13_200_000


def test_transferir_confirms_both_balances(session, seeded):
    accounts.create_account(session, "Ahorros", "savings", "COP", balance=0)
    out = core.transferir(
        session,
        TransferirInput(
            from_account="Bancolombia", to_account="Ahorros", amount=4_000_000
        ),
    )
    assert "Transfer" in out
    assert "Bancolombia" in out and "Ahorros" in out
    assert "60000.00 COP" in out  # source 100k - 40k
    assert "40000.00 COP" in out  # destination 0 + 40k


def test_transferir_same_account_returns_imbalance_text(session, seeded):
    out = core.transferir(
        session,
        TransferirInput(
            from_account="Bancolombia", to_account="Bancolombia", amount=1000
        ),
    )
    assert "Could not record the transfer" in out


def test_fijar_tasa_fx_confirms(session):
    out = core.fijar_tasa_fx(session, FijarTasaInput(date=date(2026, 6, 18), usd_cop=4150))
    assert "USD→COP rate for 2026-06-18" in out
    assert "4150" in out


def test_registrar_gasto_unknown_category_returns_guidance(session, seeded):
    out = core.registrar_gasto(
        session,
        RegistrarGastoInput(payee="X", amount=1000, account="Bancolombia", category="NoExiste"),
    )
    assert "Category 'NoExiste' not found" in out


def test_usd_expense_without_rate_returns_missing_rate_text(session):
    accounts.create_account(session, "Amex", "credit", "USD", balance=0)
    out = core.registrar_gasto(
        session,
        RegistrarGastoInput(
            payee="Spotify", amount=1200, account="Amex", currency="USD",
            date=date(2026, 6, 18),
        ),
    )
    assert "USD→COP" in out
    assert "fijar_tasa_fx" in out

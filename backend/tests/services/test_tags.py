from datetime import date
from decimal import Decimal

import pytest

from quaestor.domain.errors import NotFound
from quaestor.domain.models import Account, AccountType, Transaction, TxType
from quaestor.services import tags


def _tx_directa(session):
    acc = Account(name="A", type=AccountType.debit, currency="COP")
    session.add(acc)
    session.commit()
    session.refresh(acc)
    tx = Transaction(
        date=date(2026, 6, 1), payee="Test", type=TxType.expense,
        amount=1000, currency="COP", fx_rate=Decimal("1"), to_base=1000,
        account_id=acc.id,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_crear_tag_es_idempotente(session):
    t1 = tags.crear_tag(session, "viaje")
    t2 = tags.crear_tag(session, "viaje")
    assert t1.id == t2.id
    assert len(tags.listar_tags(session)) == 1


def test_etiquetar_crea_faltantes_y_no_duplica(session):
    tx = _tx_directa(session)
    tags.etiquetar(session, tx.id, ["viaje", "japón"])
    tags.etiquetar(session, tx.id, ["viaje"])  # ya existe -> no duplica link
    nombres = {t.name for t in tags.listar_tags(session)}
    assert nombres == {"viaje", "japón"}


def test_etiquetar_tx_inexistente(session):
    with pytest.raises(NotFound):
        tags.etiquetar(session, 999, ["x"])

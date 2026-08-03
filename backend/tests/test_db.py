import pytest
from quaestor.db import atomic, init_db, make_engine
from quaestor.domain.models import Account, AccountType, Settings
from sqlmodel import Session, select


def test_init_db_creates_settings_singleton():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        settings = s.get(Settings, 1)
        assert settings is not None
        assert settings.base_currency == "COP"


def test_init_db_is_idempotent_for_settings():
    engine = make_engine(memory=True)
    init_db(engine)
    init_db(engine)
    with Session(engine) as s:
        assert len(s.exec(select(Settings)).all()) == 1


def test_atomic_rolls_back_on_error(session):
    with pytest.raises(RuntimeError), atomic(session):
        session.add(Account(name="x", type=AccountType.debit, currency="COP"))
        raise RuntimeError("boom")
    assert session.exec(select(Account)).all() == []

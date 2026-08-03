import pytest
from quaestor.db import init_db, make_engine
from quaestor.services import accounts, categories
from sqlmodel import Session


@pytest.fixture
def engine():
    eng = make_engine(memory=True)
    init_db(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def seeded(session):
    """A COP debit account 'Bancolombia' (100k COP) and a 'Groceries' category."""
    account = accounts.create_account(session, "Bancolombia", "debit", "COP", balance=10_000_000)
    category = categories.create_category(session, "Groceries")
    return {"account": account, "category": category}

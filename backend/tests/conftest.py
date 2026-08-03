import pytest
from quaestor.db import init_db, make_engine
from sqlmodel import Session


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s

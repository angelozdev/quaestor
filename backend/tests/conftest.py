import pytest
from sqlmodel import Session

from quaestor.db import init_db, make_engine


@pytest.fixture
def session():
    engine = make_engine(memory=True)
    init_db(engine)
    with Session(engine) as s:
        yield s

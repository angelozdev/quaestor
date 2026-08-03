"""Daily orchestration: FX + materialize_due + ensure_month_closed, idempotent."""
from __future__ import annotations

from datetime import date as Date

import pytest
from quaestor.domain.models import Account, AccountType, IntervalUnit, RecurringItem, RecurringMode, TxType
from quaestor.jobs import daily
from sqlmodel import Session

from tests.support.recurring import declare_existing


class _StubClient:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def close(self): pass
    def get(self, url, params=None, timeout=None):
        class _R:
            status_code = 200
            def json(self_inner): return self.payload
            def raise_for_status(self_inner): pass
        return _R()


@pytest.fixture
def session(monkeypatch, tmp_path):
    monkeypatch.setenv("QUAESTOR_DB", f"sqlite:///{tmp_path / 'test.db'}")
    from quaestor import db
    db.init_db(db.engine)
    with Session(db.engine) as s:
        yield s


def _make_account(session: Session, name: str = "Bank") -> Account:
    acc = Account(name=name, type=AccountType.debit, currency="COP", balance=0)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def _make_recurring(session: Session, account: Account) -> RecurringItem:
    item = RecurringItem(
        name="Rent", payee="Landlord", type="expense", mode=RecurringMode.manual,
        amount=100000, currency="COP", category_id=None, account_id=account.id,
        interval_unit=IntervalUnit.month, interval_count=1, start_date=Date(2026, 6, 1),
        declared_on=Date(2026, 6, 1),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_run_daily_materializes_due_recurring(session, monkeypatch):
    acc = _make_account(session)
    _make_recurring(session, acc)
    today = Date(2026, 6, 1)

    # Stub the httpx.Client used inside fx_fetch by patching its module symbol.
    from quaestor.jobs import fx_fetch as fx_module
    monkeypatch.setattr(
        fx_module, "httpx",
        type("X", (), {"Client": lambda *a, **kw: _StubClient({"rates": {"COP": 4150}})}),
    )

    result = daily.run_daily(session, today, fx_url="https://example.com", fx_key=None)

    assert result["materialized_count"] == 1
    assert result["month_closed"] == "2026-06"
    assert result["fx_error"] is None


def test_run_daily_is_idempotent(session, monkeypatch):
    acc = _make_account(session)
    _make_recurring(session, acc)
    today = Date(2026, 6, 1)

    from quaestor.jobs import fx_fetch as fx_module
    monkeypatch.setattr(
        fx_module, "httpx",
        type("X", (), {"Client": lambda *a, **kw: _StubClient({"rates": {"COP": 4150}})}),
    )

    daily.run_daily(session, today, "https://example.com", None)
    result2 = daily.run_daily(session, today, "https://example.com", None)

    assert result2["materialized_count"] == 0


def test_fx_failure_does_not_block_other_jobs(session, monkeypatch):
    acc = _make_account(session)
    _make_recurring(session, acc)
    today = Date(2026, 6, 1)

    from quaestor.jobs import fx_fetch as fx_module

    class _BoomClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def close(self): pass
        def get(self, *a, **kw): raise RuntimeError("network down")

    monkeypatch.setattr(fx_module, "httpx", type("X", (), {"Client": lambda *a, **kw: _BoomClient()}))

    result = daily.run_daily(session, today, "https://example.com", None)

    assert result["fx_error"] is not None
    assert "network down" in result["fx_error"]
    assert result["materialized_count"] == 1  # materialize_due still ran


def test_run_daily_reports_the_obligations_that_need_attention(session):
    from quaestor.services import accounts

    good = _make_account(session)
    _make_recurring(session, good)
    bad = accounts.create_account(session, "Nequi", AccountType.debit, "COP", balance=200_000)
    declare_existing(
        session, name="Spotify", payee="Spotify", type=TxType.expense,
        mode=RecurringMode.auto, amount=15_000, currency="COP", category_id=None,
        account_id=bad.id, interval_unit=IntervalUnit.month, interval_count=1,
        start_date=Date(2026, 6, 1),
    )
    accounts.archive_account(session, bad.id)

    result = daily.run_daily(session, Date(2026, 6, 1), fx_url="", fx_key=None)

    assert result["materialized_count"] == 1
    assert any("Spotify" in message for message in result["failures"])
    assert not any("Rent" in message for message in result["failures"])

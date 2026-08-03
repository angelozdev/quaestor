
from quaestor.domain.models import AccountType, GoalContribution, TxType
from quaestor.services import accounts, goals, planned, rollover, transactions
from quaestor.services import settings as settings_svc
from quaestor.services.bootstrap import register_goal_hooks
from sqlmodel import select


def _funded(session):
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    return src, sav


def test_init_db_registers_goal_hooks_once(session):
    # conftest's init_db already ran register_goal_hooks; re-running must not duplicate
    register_goal_hooks()
    register_goal_hooks()
    assert rollover.ROLLOVER_HOOKS.count(goals.propose_goal_contributions) == 1
    assert planned.POST_CONFIRM_HOOKS.count(goals.record_confirmed_contribution) == 1


def test_close_month_then_confirm_full_cycle(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    # close_month fires the registered rollover hook -> a planned proposal lands
    rollover.close_month(session, "2026-06")
    planned_txs = transactions.list_transactions(session, type=TxType.transfer, status="planned")
    assert len(planned_txs) == 1 and planned_txs[0].goal_id == g.id
    # re-running close_month does not duplicate the proposal
    rollover.close_month(session, "2026-06")
    assert len(transactions.list_transactions(session, type=TxType.transfer, status="planned")) == 1
    # confirming fires the registered post-confirm hook -> contribution recorded
    planned.confirm_payment(session, planned_txs[0].id)
    [c] = session.exec(select(GoalContribution)).all()
    assert c.source.value == "confirmed" and c.amount == 200_000
    assert accounts.get_account(session, src.id).balance == 800_000
    assert accounts.get_account(session, sav.id).balance == 200_000
    # re-running close_month after confirmation still does not re-propose for the period
    rollover.close_month(session, "2026-06")
    assert len(session.exec(select(GoalContribution)).all()) == 1

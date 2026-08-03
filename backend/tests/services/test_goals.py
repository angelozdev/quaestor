from datetime import date

import pytest
from quaestor.domain.errors import NotFound, ValidationError
from quaestor.domain.models import AccountType, GoalStatus
from quaestor.services import accounts, goals


def _savings(session, archived=False):
    acc = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    if archived:
        accounts.archive_account(session, acc.id)
    return acc


def test_create_defined_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000,
                          savings_account_id=sav.id, target_amount=1_200_000,
                          deadline=date(2026, 12, 1))
    assert g.id is not None and g.status == GoalStatus.active
    assert g.target_amount == 1_200_000 and g.deadline == date(2026, 12, 1)


def test_create_open_ended_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    assert g.target_amount is None and g.deadline is None


def test_create_goal_only_target_raises(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000,
                          savings_account_id=sav.id, target_amount=500_000)


def test_create_goal_only_deadline_raises(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000,
                          savings_account_id=sav.id, deadline=date(2026, 12, 1))


def test_create_goal_rejects_non_positive_monthly(session):
    sav = _savings(session)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=0, savings_account_id=sav.id)


def test_create_goal_rejects_non_savings_account(session):
    acc = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=0)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=acc.id)


def test_create_goal_rejects_archived_savings(session):
    sav = _savings(session, archived=True)
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=sav.id)


def test_create_goal_rejects_unknown_account(session):
    with pytest.raises(ValidationError):
        goals.create_goal(session, name="x", monthly_amount=100_000, savings_account_id=999)


from quaestor.domain.models import TxType
from quaestor.services import settings as settings_svc
from quaestor.services import transactions


def _funded(session):
    src = accounts.create_account(session, "Checking", AccountType.debit, "COP", balance=1_000_000)
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    settings_svc.update_settings(session, default_source_account_id=src.id)
    return src, sav


def test_goal_contribution_creates_manual_contribution_and_transfer(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    c = goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    assert c.source.value == "manual" and c.amount == 150_000
    assert c.transaction_id is not None
    assert accounts.get_account(session, src.id).balance == 850_000
    assert accounts.get_account(session, sav.id).balance == 150_000


def test_goal_contribution_is_not_expense_or_income(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    assert transactions.list_transactions(session, type=TxType.expense) == []
    assert transactions.list_transactions(session, type=TxType.income) == []
    transfers = transactions.list_transactions(session, type=TxType.transfer, status="posted")
    assert len(transfers) == 2


def test_goal_contribution_stores_both_leg_directions(session):
    from quaestor.domain.models import TransferDirection
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    legs = transactions.list_transactions(session, type=TxType.transfer, status="posted")
    by_account = {leg.account_id: leg.transfer_direction for leg in legs}
    assert by_account[src.id] == TransferDirection.out
    assert by_account[sav.id] == TransferDirection.in_


def test_goal_contribution_without_default_source_is_atomic(session):
    sav = accounts.create_account(session, "Savings", AccountType.savings, "COP", balance=0)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 150_000, date(2026, 6, 15))
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    assert session.exec(select(GoalContribution)).all() == []  # nothing recorded


def test_goal_contribution_reaching_target_marks_reached(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=300_000, deadline=date(2026, 12, 1))
    goals.goal_contribution(session, g.id, 300_000, date(2026, 6, 15))
    from quaestor.domain.models import Goal, GoalStatus
    assert session.get(Goal, g.id).status == GoalStatus.reached


def test_goal_contribution_rejects_bad_amount_and_unknown_goal(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 0, date(2026, 6, 15))
    with pytest.raises(NotFound):
        goals.goal_contribution(session, 999, 100_000, date(2026, 6, 15))


def test_goal_contribution_accepts_a_one_cent_amount(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    contribution = goals.goal_contribution(session, g.id, 1, date(2026, 6, 15))
    assert contribution.amount == 1
    assert accounts.get_account(session, src.id).balance == 999_999
    assert accounts.get_account(session, sav.id).balance == 1


def test_goal_contribution_rejects_an_archived_savings_account(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    accounts.archive_account(session, sav.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 100_000, date(2026, 6, 15))


def test_goal_contribution_rejects_a_missing_savings_account(session):
    from quaestor.domain.models import Goal

    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    session.get(Goal, g.id).savings_account_id = 9999
    session.commit()
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 100_000, date(2026, 6, 15))


def test_goal_contribution_rejects_an_archived_source_account(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    accounts.archive_account(session, src.id)
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 100_000, date(2026, 6, 15))


def test_goal_contribution_rejects_a_dangling_default_source_account(session):
    from quaestor.domain.models import Settings

    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    session.get(Settings, 1).default_source_account_id = 9999
    session.commit()
    with pytest.raises(ValidationError):
        goals.goal_contribution(session, g.id, 100_000, date(2026, 6, 15))


def test_propose_skips_a_goal_whose_only_tx_falls_on_the_first_day(session):
    _src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    proposal = _planned_transfers(session)[0]
    proposal.date = date(2026, 6, 1)
    session.commit()
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    assert len(_planned_transfers(session)) == 1


def test_goals_progress_open_ended_reports_saved(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Buffer", monthly_amount=100_000, savings_account_id=sav.id)
    goals.goal_contribution(session, g.id, 250_000, date(2026, 6, 1))
    [p] = goals.goals_progress(session, today=date(2026, 6, 19))
    assert p.type == "open-ended" and p.saved == 250_000
    assert p.monthly_required is None


def test_goals_progress_defined_reports_on_track_and_eta(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=1_200_000, deadline=date(2026, 12, 1))
    goals.goal_contribution(session, g.id, 200_000, date(2026, 6, 1))
    [p] = goals.goals_progress(session, today=date(2026, 6, 19))
    assert p.type == "defined" and p.remaining == 1_000_000
    assert p.monthly_required == 166_667 and p.on_track is True
    assert p.eta == date(2026, 11, 19)


def test_goals_progress_default_lists_only_active(session):
    _src, sav = _funded(session)
    active = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    paused = goals.create_goal(session, name="B", monthly_amount=100_000, savings_account_id=sav.id)
    from quaestor.domain.models import Goal, GoalStatus
    session.get(Goal, paused.id).status = GoalStatus.paused
    session.commit()
    ids = [p.goal_id for p in goals.goals_progress(session, today=date(2026, 6, 19))]
    assert ids == [active.id]


def test_goals_progress_explicit_ids_include_inactive(session):
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    from quaestor.domain.models import Goal, GoalStatus
    session.get(Goal, g.id).status = GoalStatus.paused
    session.commit()
    ids = [p.goal_id for p in goals.goals_progress(session, goal_ids=[g.id], today=date(2026, 6, 19))]
    assert ids == [g.id]


from quaestor.domain.models import Goal, Transaction, TxStatus


def _planned_transfers(session):
    return list(transactions.list_transactions(session, type=TxType.transfer, status="planned"))


def test_propose_creates_planned_transfer_per_active_goal(session):
    src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    txs = _planned_transfers(session)
    assert len(txs) == 1
    tx = txs[0]
    assert tx.goal_id == g.id and tx.amount == 200_000
    assert tx.account_id == sav.id and tx.date == date(2026, 6, 30)
    # no balance moved by a proposal
    assert accounts.get_account(session, src.id).balance == 1_000_000
    assert accounts.get_account(session, sav.id).balance == 0


def test_propose_skips_paused_and_reached(session):
    _src, sav = _funded(session)
    goals.create_goal(session, name="Active", monthly_amount=100_000, savings_account_id=sav.id)
    paused = goals.create_goal(session, name="Paused", monthly_amount=100_000, savings_account_id=sav.id)
    reached = goals.create_goal(session, name="Reached", monthly_amount=100_000, savings_account_id=sav.id)
    session.get(Goal, paused.id).status = GoalStatus.paused
    session.get(Goal, reached.id).status = GoalStatus.reached
    session.commit()
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    txs = _planned_transfers(session)
    assert len(txs) == 1 and txs[0].payee == "Goal: Active"


def test_propose_is_idempotent_per_goal_period(session):
    _src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    goals.propose_goal_contributions("2026-06", session)  # re-run
    session.commit()
    assert len(_planned_transfers(session)) == 1


def test_proposed_contribution_can_be_deleted_without_moving_balances(session):
    src, sav = _funded(session)
    goals.create_goal(session, name="Korea", monthly_amount=300_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    proposal = _planned_transfers(session)[0]
    transactions.delete_transaction(session, proposal.id)
    assert _planned_transfers(session) == []
    assert accounts.get_account(session, src.id).balance == 1_000_000
    assert accounts.get_account(session, sav.id).balance == 0


def test_skipped_contribution_can_be_deleted_without_moving_balances(session):
    src, sav = _funded(session)
    goals.create_goal(session, name="Korea", monthly_amount=300_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    proposal = _planned_transfers(session)[0]
    planned.skip_payment(session, proposal.id)
    transactions.delete_transaction(session, proposal.id)
    assert transactions.list_transactions(session, type=TxType.transfer) == []
    assert accounts.get_account(session, src.id).balance == 1_000_000
    assert accounts.get_account(session, sav.id).balance == 0


def test_propose_archived_savings_raises(session):
    _src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    accounts.archive_account(session, sav.id)
    with pytest.raises(ValidationError):
        goals.propose_goal_contributions("2026-06", session)


from quaestor.services import planned


@pytest.fixture
def goal_post_confirm_hook():
    # Idempotent: from Task 13 onward init_db registers this hook globally, so only
    # add it here when absent (and only remove what this fixture added). This keeps
    # exactly one registration -> the hook fires once -> one contribution per confirm.
    hook = goals.record_confirmed_contribution
    added = hook not in planned.POST_CONFIRM_HOOKS
    if added:
        planned.register_post_confirm_hook(hook)
    try:
        yield
    finally:
        if added:
            planned.POST_CONFIRM_HOOKS.remove(hook)


def test_record_confirmed_contribution_unit(session):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    tx = Transaction(date=date(2026, 6, 30), type=TxType.transfer, status=TxStatus.posted,
                     amount=200_000, currency="COP",
                     account_id=sav.id, goal_id=g.id)
    session.add(tx)
    session.flush()
    c = goals.record_confirmed_contribution(tx, session)
    session.commit()
    assert c is not None and c.source.value == "confirmed"
    assert c.amount == 200_000 and c.transaction_id == tx.id
    assert len(session.exec(select(GoalContribution)).all()) == 1


def test_record_confirmed_contribution_noop_without_goal_id(session):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    _src, sav = _funded(session)
    tx = Transaction(date=date(2026, 6, 30), type=TxType.transfer, status=TxStatus.posted,
                     amount=100_000, currency="COP",
                     account_id=sav.id)
    session.add(tx)
    session.flush()
    assert goals.record_confirmed_contribution(tx, session) is None
    session.commit()
    assert session.exec(select(GoalContribution)).all() == []


def test_confirm_proposal_records_contribution(session, goal_post_confirm_hook):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.confirm_payment(session, tx.id)
    [c] = session.exec(select(GoalContribution)).all()
    assert c.source.value == "confirmed" and c.amount == 200_000 and c.transaction_id == tx.id
    assert accounts.get_account(session, src.id).balance == 800_000
    assert accounts.get_account(session, sav.id).balance == 200_000


def test_confirm_with_smaller_amount_adjusts_contribution(session, goal_post_confirm_hook):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    _src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.confirm_payment(session, tx.id, amount=120_000)
    [c] = session.exec(select(GoalContribution)).all()
    assert c.amount == 120_000
    assert accounts.get_account(session, sav.id).balance == 120_000


def test_skip_proposal_contributes_nothing(session, goal_post_confirm_hook):
    from quaestor.domain.models import GoalContribution
    from sqlmodel import select
    _src, sav = _funded(session)
    goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id)
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.skip_payment(session, tx.id)
    assert session.exec(select(GoalContribution)).all() == []
    assert accounts.get_account(session, sav.id).balance == 0


def test_confirm_reaching_target_marks_reached(session, goal_post_confirm_hook):
    from quaestor.domain.models import Goal, GoalStatus
    _src, sav = _funded(session)
    g = goals.create_goal(session, name="Trip", monthly_amount=200_000, savings_account_id=sav.id,
                          target_amount=200_000, deadline=date(2026, 12, 1))
    goals.propose_goal_contributions("2026-06", session)
    session.commit()
    tx = _planned_transfers(session)[0]
    planned.confirm_payment(session, tx.id)
    assert session.get(Goal, g.id).status == GoalStatus.reached


def test_list_goals_returns_all_statuses(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    goals.pause_goal(session, g.id)
    goals.create_goal(session, name="B", monthly_amount=100_000, savings_account_id=sav.id)
    names = [x.name for x in goals.list_goals(session)]
    assert names == ["A", "B"]


def test_update_goal_name_and_monthly(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    out = goals.update_goal(session, g.id, name="A2", monthly_amount=150_000)
    assert out.name == "A2" and out.monthly_amount == 150_000


def test_update_goal_to_defined_requires_both(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    with pytest.raises(ValidationError):
        goals.update_goal(session, g.id, target_amount=1_000_000)  # deadline missing


def test_update_goal_to_open_ended_clears_both(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000,
                          savings_account_id=sav.id, target_amount=1_000_000,
                          deadline=date(2026, 12, 1))
    out = goals.update_goal(session, g.id, target_amount=None, deadline=None)
    assert out.target_amount is None and out.deadline is None



def test_pause_then_restore_goal(session):
    sav = _savings(session)
    g = goals.create_goal(session, name="A", monthly_amount=100_000, savings_account_id=sav.id)
    assert goals.pause_goal(session, g.id).status == GoalStatus.paused
    # paused goal drops out of active progress
    assert goals.goals_progress(session) == []
    assert goals.restore_goal(session, g.id).status == GoalStatus.active


def test_pause_goal_not_found(session):
    with pytest.raises(NotFound):
        goals.pause_goal(session, 999)

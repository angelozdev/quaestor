from quaestor.domain.rules import safe_to_spend_calc


def test_cascade_subtracts_every_term():
    free = safe_to_spend_calc(
        income_forecast=1_000_000,
        committed=300_000,
        assigned_envelopes=200_000,
        unbudgeted_spending=100_000,
        overspend=50_000,
    )
    assert free == 350_000


def test_cascade_can_go_negative():
    free = safe_to_spend_calc(
        income_forecast=100_000, committed=200_000,
        assigned_envelopes=0, unbudgeted_spending=0, overspend=0,
    )
    assert free == -100_000

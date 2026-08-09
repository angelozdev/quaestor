"""The metas REST surface, and the link a purchase carries to one.

The router owns no rule — every refusal here already lives in
`services.metas` or `services.transactions`. What these pin is that the
wire reaches those rules at all: before this, a meta could be linked from
the services layer and from nowhere a browser could reach.
"""

import pytest

from tests.support.fx import set_trm

MONTH = {"month": "2026-08"}


@pytest.fixture(autouse=True)
def a_rate(client, auth):
    """Every read path demands a rate on entry and never guesses one (ADR-0031)."""
    set_trm(client, auth)


def _meta(client, auth, name="Celular", amount=800_000_000, target="2026-12", **extra):
    resp = client.post(
        "/api/metas",
        headers=auth,
        params=MONTH,
        json={"name": name, "amount": amount, "target_month": target, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def account(client, auth):
    return client.post(
        "/api/accounts",
        headers=auth,
        json={"name": "Bank", "type": "debit", "currency": "COP"},
    ).json()


def _expense(client, auth, account, category, amount=800_000_000, **extra):
    return client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "category_id": category,
            "account_id": account["id"],
            "amount": amount,
            "currency": "COP",
            "date": "2026-08-15",
            "payee": "Store",
            **extra,
        },
    )


def test_metas_requires_auth(client):
    assert client.get("/api/metas", params=MONTH).status_code == 401


def test_a_created_meta_is_listed_with_what_it_asks(client, auth):
    _meta(client, auth)
    rows = client.get("/api/metas", headers=auth, params=MONTH).json()
    assert [row["name"] for row in rows] == ["Celular"]
    assert rows[0]["asks"] == 160_000_000
    assert rows[0]["holds"] == 160_000_000


def test_the_preview_says_what_the_meta_would_ask_before_it_exists(client, auth):
    resp = client.post(
        "/api/metas/preview",
        headers=auth,
        params=MONTH,
        json={"name": "Celular", "amount": 800_000_000, "target_month": "2026-12"},
    )
    assert resp.json()["asks"] == 160_000_000
    assert client.get("/api/metas", headers=auth, params=MONTH).json() == []


def test_a_cancelled_meta_leaves_the_list_and_comes_back_with_nothing(client, auth):
    later = {"month": "2026-09"}
    meta = _meta(client, auth)
    client.post(f"/api/metas/{meta['id']}/contributions", headers=auth, params=MONTH, json={"amount": 50_000_000})
    assert client.delete(f"/api/metas/{meta['id']}", headers=auth, params=MONTH).status_code == 204
    assert client.get("/api/metas", headers=auth, params=MONTH).json() == []

    client.post(f"/api/metas/{meta['id']}/restore", headers=auth, params=later)
    restored = client.get("/api/metas", headers=auth, params=later).json()
    assert [row["name"] for row in restored] == ["Celular"]
    assert restored[0]["holds"] == 200_000_000


def test_a_cancelled_meta_is_still_reachable_so_it_can_be_restored(client, auth):
    """Archived and never destroyed is worth nothing if it cannot be found."""
    meta = _meta(client, auth)
    assert client.get("/api/metas/archived", headers=auth).json() == []

    client.delete(f"/api/metas/{meta['id']}", headers=auth, params=MONTH)
    assert [row["name"] for row in client.get("/api/metas/archived", headers=auth).json()] == ["Celular"]

    client.post(f"/api/metas/{meta['id']}/restore", headers=auth, params=MONTH)
    assert client.get("/api/metas/archived", headers=auth).json() == []


def test_closing_a_meta_still_running_is_refused_so_its_money_cannot_evaporate(client, auth):
    """Closing releases nothing, so closing a running meta loses what it held.

    The meta is archived with no `cancelled_month`, which drops it from every
    later month's aggregate: the month neither holds it nor hands it back, and
    `consumo + ahorro + libre` silently stops equalling the income. Cancelling
    is the act for a meta the owner no longer wants.
    """
    meta = _meta(client, auth)
    running = client.get("/api/metas", headers=auth, params=MONTH).json()[0]
    assert running["holds"] == 160_000_000

    refused = client.post(f"/api/metas/{meta['id']}/close", headers=auth, params=MONTH)
    assert refused.status_code == 422
    assert "still running" in refused.text
    assert client.get("/api/metas", headers=auth, params=MONTH).json()[0]["holds"] == 160_000_000


def test_restoring_a_meta_that_was_never_cancelled_is_refused(client, auth):
    """Restoring rewrites the start month and drops the stated opening.

    On a running meta that would throw away the history every figure is
    derived from, and the meta would silently restart from zero.
    """
    meta = _meta(client, auth)
    refused = client.post(f"/api/metas/{meta['id']}/restore", headers=auth, params=MONTH)
    assert refused.status_code == 422
    assert "nothing to bring back" in refused.text
    assert client.get("/api/metas", headers=auth, params=MONTH).json()[0]["holds"] == 160_000_000


def test_a_contribution_is_listed_and_can_be_taken_back(client, auth):
    meta = _meta(client, auth)
    made = client.post(
        f"/api/metas/{meta['id']}/contributions",
        headers=auth,
        params=MONTH,
        json={"amount": 50_000_000},
    )
    assert made.status_code == 201
    assert [c["amount"] for c in client.get(f"/api/metas/{meta['id']}/contributions", headers=auth).json()] == [
        50_000_000
    ]

    client.delete(f"/api/metas/contributions/{made.json()['id']}", headers=auth)
    assert client.get(f"/api/metas/{meta['id']}/contributions", headers=auth).json() == []


def test_the_split_names_what_the_month_consumed_and_what_it_saved(client, auth):
    _meta(client, auth)
    split = client.get("/api/metas/split", headers=auth, params=MONTH).json()
    assert split["ahorro"] == 160_000_000
    assert split["year_month"] == "2026-08"


def test_a_month_that_saved_and_cancelled_says_both_and_names_the_meta(client, auth, account, income_category):
    """The month the owner both set money aside and called a meta off.

    `ahorro` nets the two and goes negative; `set_aside` is what was genuinely
    put by. A screen showing only the net would report a month of saving as a month
    of spending.
    """
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "category_id": income_category,
            "account_id": account["id"],
            "amount": 500_000_000,
            "currency": "COP",
            "date": "2026-08-05",
            "payee": "Empresa",
        },
    )
    _meta(client, auth, name="Moto", amount=300_000_000, target="2026-10")
    celular = _meta(client, auth)
    client.post(f"/api/metas/{celular['id']}/contributions", headers=auth, params=MONTH, json={"amount": 320_000_000})
    client.delete(f"/api/metas/{celular['id']}", headers=auth, params=MONTH)

    split = client.get("/api/metas/split", headers=auth, params=MONTH).json()
    assert split["set_aside"] > 0
    assert split["ahorro"] == split["set_aside"] - split["released"]
    assert split["consumo"] + split["ahorro"] + split["libre"] == split["income"]

    assert [row["name"] for row in split["gave_back"]] == ["Celular"]
    assert split["gave_back"][0]["cancelled"] is True
    assert sum(row["released"] for row in split["gave_back"]) == split["released"]


def test_a_live_meta_is_not_marked_cancelled(client, auth):
    _meta(client, auth)
    row = client.get("/api/metas", headers=auth, params=MONTH).json()[0]
    assert row["cancelled"] is False
    assert row["released"] == 0


def test_the_available_breakdown_names_the_metas_and_adds_up(client, auth, account, income_category):
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "category_id": income_category,
            "account_id": account["id"],
            "amount": 500_000_000,
            "currency": "COP",
            "date": "2026-08-05",
            "payee": "Empresa",
        },
    )
    meta = _meta(client, auth)
    client.post(f"/api/metas/{meta['id']}/contributions", headers=auth, params=MONTH, json={"amount": 50_000_000})

    breakdown = client.get("/api/funds/available", headers=auth, params=MONTH).json()
    assert [row["name"] for row in breakdown["metas"]] == ["Celular"]
    assert breakdown["metas"][0]["asks"] == 160_000_000
    assert breakdown["contributed"] == 50_000_000
    assert breakdown["released"] == 0

    claimed = (
        sum(fund["asks"] for fund in breakdown["funds"])
        + sum(meta["asks"] for meta in breakdown["metas"])
        + breakdown["contributed"]
        - breakdown["released"]
    )
    assert breakdown["income"] - claimed - breakdown["uncovered"] == breakdown["free"]


def test_an_expense_reaches_the_meta_through_the_wire(client, auth, account, expense_category):
    meta = _meta(client, auth)
    created = _expense(client, auth, account, expense_category, meta_id=meta["id"])
    assert created.status_code == 201
    assert created.json()["meta_id"] == meta["id"]
    assert client.get("/api/metas", headers=auth, params=MONTH).json()[0]["complete"] is True


def test_money_coming_in_is_refused_a_meta_through_the_wire(client, auth, account, income_category):
    meta = _meta(client, auth)
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "category_id": income_category,
            "account_id": account["id"],
            "amount": 800_000_000,
            "currency": "COP",
            "date": "2026-08-15",
            "payee": "Empresa",
            "meta_id": meta["id"],
        },
    )
    assert resp.status_code == 422
    assert "only money going out" in resp.text


def test_a_cancelled_meta_takes_no_link_through_the_wire(client, auth, account, expense_category):
    meta = _meta(client, auth)
    client.delete(f"/api/metas/{meta['id']}", headers=auth, params=MONTH)
    resp = _expense(client, auth, account, expense_category, meta_id=meta["id"])
    assert resp.status_code == 422
    assert "was cancelled" in resp.text


def test_the_link_can_be_removed_and_moved_through_the_wire(client, auth, account, expense_category):
    celular = _meta(client, auth)
    televisor = _meta(client, auth, name="Televisor", amount=500_000_000)
    tx = _expense(client, auth, account, expense_category, meta_id=celular["id"]).json()

    moved = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"meta_id": televisor["id"]})
    assert moved.json()["meta_id"] == televisor["id"]

    unlinked = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"meta_id": None})
    assert unlinked.json()["meta_id"] is None


def test_an_edit_that_never_mentions_the_meta_leaves_the_link_alone(client, auth, account, expense_category):
    meta = _meta(client, auth)
    tx = _expense(client, auth, account, expense_category, meta_id=meta["id"]).json()
    edited = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"payee": "Otra tienda"})
    assert edited.json()["meta_id"] == meta["id"]


def test_a_running_meta_is_renamed_over_the_wire(client, auth):
    """The screen's `Cambiarle el nombre`. Nothing reached this body before."""
    meta = _meta(client, auth)

    changed = client.patch(f"/api/metas/{meta['id']}", headers=auth, params=MONTH, json={"name": "Telefono"})

    assert changed.status_code == 200
    assert changed.json()["name"] == "Telefono"
    assert [m["name"] for m in client.get("/api/metas", headers=auth, params=MONTH).json()] == ["Telefono"]


def test_a_running_metas_amount_and_month_move_over_the_wire(client, auth):
    """AC-11's own figures: raised to 9.000.000, October asks 1.933.333,34."""
    meta = _meta(client, auth, amount=800_000_000, target="2026-12")

    client.patch(
        f"/api/metas/{meta['id']}",
        headers=auth,
        params={"month": "2026-10"},
        json={"amount": 900_000_000, "target_month": "2026-12"},
    )

    reported = client.get("/api/metas", headers=auth, params={"month": "2026-10"}).json()[0]
    assert reported["amount"] == 900_000_000
    assert reported["asks"] == 193_333_334


def test_lowering_a_meta_below_what_it_holds_completes_it_over_the_wire(client, auth):
    """AC-16's own figures: holding 4.800.000, lowered to 4.000.000, 800.000 comes back."""
    meta = _meta(client, auth, amount=800_000_000, target="2026-12")

    client.patch(
        f"/api/metas/{meta['id']}",
        headers=auth,
        params={"month": "2026-11"},
        json={"amount": 400_000_000},
    )

    reported = client.get("/api/metas", headers=auth, params={"month": "2026-11"}).json()[0]
    assert reported["complete"] is True
    assert reported["released"] == 80_000_000


def test_a_meta_is_created_in_dollars_over_the_wire(client, auth):
    """AC-26's own figure — the create form had no selector for this."""
    meta = _meta(client, auth, name="Curso", amount=200_000, target="2027-01", currency="USD")

    reported = client.get("/api/metas", headers=auth, params=MONTH).json()[0]
    assert meta["currency"] == "USD"
    assert reported["asks"] == 33_334


def test_a_meta_is_told_what_it_already_holds_over_the_wire(client, auth):
    """AC-34's own figure — the create form had no field for this."""
    _meta(client, auth, amount=800_000_000, target="2026-12", stated_opening=300_000_000)

    reported = client.get("/api/metas", headers=auth, params=MONTH).json()[0]
    assert reported["asks"] == 100_000_000
    assert reported["holds"] == 400_000_000


def test_what_the_owner_says_he_already_has_lowers_the_preview_over_the_wire(client, auth):
    """The figure the create form shows before the meta exists."""
    body = {"name": "Celular", "amount": 800_000_000, "target_month": "2026-12"}

    plain = client.post("/api/metas/preview", headers=auth, params=MONTH, json=body).json()
    stated = client.post(
        "/api/metas/preview", headers=auth, params=MONTH, json={**body, "stated_opening": 300_000_000}
    ).json()

    assert (plain["asks"], stated["asks"]) == (160_000_000, 100_000_000)
